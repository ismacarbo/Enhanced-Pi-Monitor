"""Unit tests for the source-neutral knowledge layer and Wiki.js adapter."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

PIMONITOR_ROOT = Path(__file__).resolve().parents[1]
if str(PIMONITOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PIMONITOR_ROOT))

from knowledge.models import KnowledgeDocument  # noqa: E402
from knowledge.sources.base import (  # noqa: E402
    KnowledgeSource,
    KnowledgeSourceNotConfigured,
)
from knowledge.sources.wikijs import (  # noqa: E402
    WikiJSAPIError,
    WikiJSClient,
    WikiJSConfig,
    WikiJSConfigurationError,
    WikiJSKnowledgeSource,
)

LIST_RESPONSE = {
    "data": {
        "pages": {
            "list": [
                {
                    "id": 42,
                    "path": "Projects/ARES/Overview",
                    "locale": "en",
                    "title": "ARES Overview",
                    "description": "Robot documentation",
                    "contentType": "markdown",
                    "isPublished": True,
                    "isPrivate": False,
                    "createdAt": "2026-08-01T10:00:00.000Z",
                    "updatedAt": "2026-08-29T11:30:00.000Z",
                    "tags": ["project:ares", "topic:ros2"],
                }
            ]
        }
    }
}

PAGE_RESPONSE = {
    "data": {
        "pages": {
            "single": {
                "id": 42,
                "path": "Projects/ARES/Overview",
                "locale": "en",
                "title": "ARES Overview",
                "description": "Robot documentation",
                "content": "# ARES\n\nCanonical Markdown content.",
                "contentType": "markdown",
                "createdAt": "2026-08-01T10:00:00.000Z",
                "updatedAt": "2026-08-29T11:30:00.000Z",
                "tags": [
                    {"tag": "project:ares", "title": "ARES"},
                    {"tag": "topic:ros2", "title": "ROS 2"},
                ],
            }
        }
    }
}


class KnowledgeDocumentTests(unittest.TestCase):
    def test_serializes_to_json_ready_dictionary(self):
        updated_at = datetime(2026, 8, 29, 11, 30, tzinfo=timezone.utc)
        document = KnowledgeDocument(
            id="wikijs:42",
            title="ARES",
            content="# ARES",
            source="wikijs",
            path="Projects/ARES",
            url="http://localhost:3000/Projects/ARES",
            tags=("project:ares", "topic:ros2"),
            updated_at=updated_at,
            metadata={"locale": "en"},
        )

        serialized = document.to_dict()

        self.assertEqual(serialized["tags"], ["project:ares", "topic:ros2"])
        self.assertEqual(serialized["updated_at"], updated_at.isoformat())
        self.assertEqual(serialized["metadata"], {"locale": "en"})

    def test_requires_stable_non_empty_id(self):
        with self.assertRaises(ValueError):
            KnowledgeDocument("", "Title", "Content", "test", "path", "url")


class KnowledgeSourceContractTests(unittest.TestCase):
    def test_abstract_source_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            KnowledgeSource()


class WikiJSConfigurationTests(unittest.TestCase):
    def test_missing_optional_configuration_is_graceful(self):
        config = WikiJSConfig.from_env({})

        self.assertFalse(config.is_configured)
        self.assertIsNone(config.base_url)
        with self.assertRaises(KnowledgeSourceNotConfigured):
            WikiJSClient(config, transport=Mock()).list_pages()

    def test_reads_and_normalizes_environment(self):
        config = WikiJSConfig.from_env(
            {
                "WIKIJS_URL": "https://wiki.example.invalid/",
                "WIKIJS_API_TOKEN": " secret-token ",
                "WIKIJS_LOCALE": "it",
                "WIKIJS_TIMEOUT_SECONDS": "4.5",
            }
        )

        self.assertTrue(config.is_configured)
        self.assertEqual(config.base_url, "https://wiki.example.invalid")
        self.assertEqual(config.graphql_url, "https://wiki.example.invalid/graphql")
        self.assertEqual(config.locale, "it")
        self.assertEqual(config.timeout_seconds, 4.5)
        self.assertNotIn("secret-token", repr(config))

    def test_rejects_unsafe_or_invalid_urls(self):
        for url in (
            "wiki.local",
            "javascript:alert(1)",
            "https://user:pass@wiki",
            "http://wiki:invalid-port",
        ):
            with self.subTest(url=url), self.assertRaises(WikiJSConfigurationError):
                WikiJSConfig(base_url=url)


class WikiJSClientTests(unittest.TestCase):
    def setUp(self):
        self.config = WikiJSConfig(
            base_url="http://localhost:3000",
            api_token="backend-only-token",
            locale="en",
        )

    def test_list_pages_uses_graphql_and_bearer_token(self):
        transport = Mock(return_value=LIST_RESPONSE)
        client = WikiJSClient(self.config, transport=transport)

        pages = client.list_pages()

        self.assertEqual(pages[0]["id"], 42)
        endpoint, payload, headers, timeout = transport.call_args.args
        self.assertEqual(endpoint, "http://localhost:3000/graphql")
        self.assertIn("ListWikiPages", payload["query"])
        self.assertEqual(payload["variables"], {"locale": "en"})
        self.assertEqual(headers["Authorization"], "Bearer backend-only-token")
        self.assertEqual(timeout, 10.0)

    def test_get_page_accepts_namespaced_stable_id(self):
        transport = Mock(return_value=PAGE_RESPONSE)
        page = WikiJSClient(self.config, transport=transport).get_page("wikijs:42")

        self.assertEqual(page["content"], "# ARES\n\nCanonical Markdown content.")
        self.assertEqual(transport.call_args.args[1]["variables"], {"id": 42})

    def test_graphql_errors_are_not_treated_as_data(self):
        transport = Mock(return_value={"errors": [{"message": "Forbidden"}]})

        with self.assertRaisesRegex(WikiJSAPIError, "Forbidden"):
            WikiJSClient(self.config, transport=transport).list_pages()


class WikiJSKnowledgeSourceTests(unittest.TestCase):
    def _source(self):
        def transport(endpoint, payload, headers, timeout):
            if "ListWikiPages" in payload["query"]:
                return LIST_RESPONSE
            return PAGE_RESPONSE

        config = WikiJSConfig(
            base_url="http://localhost:3000", api_token="backend-only-token"
        )
        return WikiJSKnowledgeSource(
            config=config, client=WikiJSClient(config, transport=transport)
        )

    def test_normalizes_full_page_response(self):
        document = self._source().get_document("42")

        self.assertEqual(document.id, "wikijs:42")
        self.assertEqual(document.source, "wikijs")
        self.assertEqual(document.path, "Projects/ARES/Overview")
        self.assertEqual(
            document.url, "http://localhost:3000/Projects/ARES/Overview"
        )
        self.assertEqual(document.tags, ("project:ares", "topic:ros2"))
        self.assertEqual(document.metadata["wikijs_page_id"], 42)
        self.assertEqual(document.updated_at.tzinfo, timezone.utc)

    def test_updated_documents_filters_before_fetching_content(self):
        source = self._source()

        recent = source.get_updated_documents(
            datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)
        )
        future = source.get_updated_documents(
            datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
        )

        self.assertEqual([document.id for document in recent], ["wikijs:42"])
        self.assertEqual(future, [])


if __name__ == "__main__":
    unittest.main()
