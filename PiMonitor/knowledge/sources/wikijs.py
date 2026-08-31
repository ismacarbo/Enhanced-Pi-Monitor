"""Wiki.js 2.x GraphQL client and knowledge-source adapter."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ..models import KnowledgeDocument
from .base import KnowledgeSource, KnowledgeSourceNotConfigured


class WikiJSConfigurationError(ValueError):
    """Raised when Wiki.js environment settings are malformed."""


class WikiJSAPIError(RuntimeError):
    """Raised when Wiki.js returns a transport, JSON, or GraphQL error."""


JsonTransport = Callable[
    [str, Mapping[str, Any], Mapping[str, str], float], Mapping[str, Any]
]


def _normalize_base_url(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None

    raw = value.strip().rstrip("/")
    parsed = urlsplit(raw)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or not parsed.hostname
    ):
        raise WikiJSConfigurationError("WIKIJS_URL must be an absolute http(s) URL")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise WikiJSConfigurationError("WIKIJS_URL contains an invalid port") from exc
    if parsed.username or parsed.password:
        raise WikiJSConfigurationError("WIKIJS_URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise WikiJSConfigurationError(
            "WIKIJS_URL must not contain a query or fragment"
        )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


@dataclass(frozen=True)
class WikiJSConfig:
    """Runtime configuration for the Wiki.js backend API."""

    base_url: Optional[str] = None
    api_token: Optional[str] = field(default=None, repr=False)
    locale: str = "en"
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        normalized_url = _normalize_base_url(self.base_url)
        normalized_token = self.api_token.strip() if self.api_token else None
        normalized_locale = self.locale.strip() if self.locale else "en"
        try:
            normalized_timeout = float(self.timeout_seconds)
        except (TypeError, ValueError) as exc:
            raise WikiJSConfigurationError(
                "WIKIJS_TIMEOUT_SECONDS must be a number"
            ) from exc
        if normalized_timeout <= 0:
            raise WikiJSConfigurationError("WIKIJS_TIMEOUT_SECONDS must be positive")

        object.__setattr__(self, "base_url", normalized_url)
        object.__setattr__(self, "api_token", normalized_token)
        object.__setattr__(self, "locale", normalized_locale)
        object.__setattr__(self, "timeout_seconds", normalized_timeout)

    @classmethod
    def from_env(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> "WikiJSConfig":
        """Load optional Wiki.js settings without reading a dotenv file."""

        values = os.environ if environ is None else environ
        return cls(
            base_url=values.get("WIKIJS_URL"),
            api_token=values.get("WIKIJS_API_TOKEN"),
            locale=values.get("WIKIJS_LOCALE", "en"),
            timeout_seconds=values.get("WIKIJS_TIMEOUT_SECONDS", "10"),
        )

    @property
    def is_configured(self) -> bool:
        """Whether both the endpoint and backend-only API token are present."""

        return bool(self.base_url and self.api_token)

    @property
    def graphql_url(self) -> Optional[str]:
        """Return the Wiki.js 2.x GraphQL endpoint when a base URL is set."""

        return "{}/graphql".format(self.base_url) if self.base_url else None

    def require_configured(self) -> None:
        """Fail with an actionable error if API access is not ready."""

        missing = []
        if not self.base_url:
            missing.append("WIKIJS_URL")
        if not self.api_token:
            missing.append("WIKIJS_API_TOKEN")
        if missing:
            raise KnowledgeSourceNotConfigured(
                "Wiki.js knowledge source is not configured; set {}".format(
                    " and ".join(missing)
                )
            )


def _default_json_transport(
    endpoint: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> Mapping[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise WikiJSAPIError(
            "Wiki.js HTTP request failed with status {}".format(exc.code)
        ) from exc
    except (URLError, OSError) as exc:
        raise WikiJSAPIError("Could not reach the Wiki.js GraphQL endpoint") from exc

    try:
        decoded = json.loads(body)
    except (TypeError, ValueError) as exc:
        raise WikiJSAPIError("Wiki.js returned invalid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise WikiJSAPIError("Wiki.js returned an unexpected JSON response")
    return decoded


class WikiJSClient:
    """Small read-only client for the Wiki.js 2.x GraphQL page API."""

    LIST_PAGES_QUERY = """
    query ListWikiPages($locale: String) {
      pages {
        list(orderBy: UPDATED, orderByDirection: ASC, locale: $locale) {
          id
          path
          locale
          title
          description
          contentType
          isPublished
          isPrivate
          createdAt
          updatedAt
          tags
        }
      }
    }
    """

    GET_PAGE_QUERY = """
    query GetWikiPage($id: Int!) {
      pages {
        single(id: $id) {
          id
          path
          locale
          title
          description
          content
          contentType
          createdAt
          updatedAt
          tags {
            tag
            title
          }
        }
      }
    }
    """

    def __init__(
        self, config: WikiJSConfig, transport: Optional[JsonTransport] = None
    ) -> None:
        self.config = config
        self._transport = transport or _default_json_transport

    def list_pages(self) -> List[Mapping[str, Any]]:
        """List page metadata; content is fetched separately by stable page ID."""

        data = self._execute(self.LIST_PAGES_QUERY, {"locale": self.config.locale})
        pages = self._read_path(data, "pages", "list")
        if not isinstance(pages, list):
            raise WikiJSAPIError("Wiki.js pages.list returned an unexpected response")
        if not all(isinstance(page, Mapping) for page in pages):
            raise WikiJSAPIError("Wiki.js pages.list contained an invalid page")
        return pages

    def get_page(self, page_id: str) -> Mapping[str, Any]:
        """Retrieve raw source content and metadata for one page."""

        numeric_id = self._numeric_page_id(page_id)
        data = self._execute(self.GET_PAGE_QUERY, {"id": numeric_id})
        page = self._read_path(data, "pages", "single")
        if not isinstance(page, Mapping):
            raise WikiJSAPIError(
                "Wiki.js page {} was not found or is not readable".format(numeric_id)
            )
        return page

    def _execute(
        self, query: str, variables: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.config.require_configured()
        endpoint = self.config.graphql_url
        if endpoint is None:  # Kept explicit for type checkers and defensive use.
            raise KnowledgeSourceNotConfigured("WIKIJS_URL is not configured")

        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(self.config.api_token),
            "Content-Type": "application/json",
            "User-Agent": "Enhanced-Pi-Monitor-Knowledge/1.0",
        }
        try:
            response = self._transport(
                endpoint,
                {"query": query, "variables": dict(variables)},
                headers,
                self.config.timeout_seconds,
            )
        except (WikiJSAPIError, KnowledgeSourceNotConfigured):
            raise
        except Exception as exc:
            raise WikiJSAPIError("Wiki.js request transport failed") from exc

        if not isinstance(response, Mapping):
            raise WikiJSAPIError("Wiki.js returned an unexpected response object")
        errors = response.get("errors")
        if errors:
            messages = []
            if isinstance(errors, list):
                for error in errors:
                    if isinstance(error, Mapping):
                        messages.append(str(error.get("message", "unknown error")))
                    else:
                        messages.append(str(error))
            else:
                messages.append(str(errors))
            raise WikiJSAPIError(
                "Wiki.js GraphQL error: {}".format("; ".join(messages))
            )

        data = response.get("data")
        if not isinstance(data, Mapping):
            raise WikiJSAPIError("Wiki.js response did not contain GraphQL data")
        return data

    @staticmethod
    def _read_path(data: Mapping[str, Any], *parts: str) -> Any:
        current: Any = data
        for part in parts:
            if not isinstance(current, Mapping) or part not in current:
                raise WikiJSAPIError(
                    "Wiki.js response was missing {}".format(".".join(parts))
                )
            current = current[part]
        return current

    @staticmethod
    def _numeric_page_id(page_id: str) -> int:
        raw = str(page_id)
        if raw.startswith("wikijs:"):
            raw = raw[len("wikijs:") :]
        try:
            numeric_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Wiki.js page ID must be a positive integer") from exc
        if numeric_id <= 0:
            raise ValueError("Wiki.js page ID must be a positive integer")
        return numeric_id


class WikiJSKnowledgeSource(KnowledgeSource):
    """Normalize Wiki.js pages into framework-independent documents."""

    source_name = "wikijs"

    def __init__(
        self,
        config: Optional[WikiJSConfig] = None,
        client: Optional[WikiJSClient] = None,
    ) -> None:
        self.config = config or WikiJSConfig.from_env()
        self.client = client or WikiJSClient(self.config)

    def list_documents(self) -> List[KnowledgeDocument]:
        summaries = self.client.list_pages()
        try:
            return [self.get_document(str(summary["id"])) for summary in summaries]
        except KeyError as exc:
            raise WikiJSAPIError("Wiki.js page list is missing a page ID") from exc

    def get_document(self, document_id: str) -> KnowledgeDocument:
        return self._to_document(self.client.get_page(document_id))

    def get_updated_documents(self, since: datetime) -> List[KnowledgeDocument]:
        if not isinstance(since, datetime):
            raise TypeError("since must be a datetime")
        normalized_since = self._as_utc(since)
        documents = []
        for summary in self.client.list_pages():
            if "id" not in summary:
                raise WikiJSAPIError("Wiki.js page list is missing a page ID")
            updated_at = self._parse_datetime(summary.get("updatedAt"), "updatedAt")
            if updated_at >= normalized_since:
                documents.append(self.get_document(str(summary["id"])))
        return documents

    def _to_document(self, page: Mapping[str, Any]) -> KnowledgeDocument:
        try:
            raw_id = int(page["id"])
            title = str(page["title"])
            content = str(page["content"])
            path = str(page["path"]).lstrip("/")
        except (KeyError, TypeError, ValueError) as exc:
            raise WikiJSAPIError(
                "Wiki.js page response is missing required fields"
            ) from exc

        raw_tags = page.get("tags") or []
        tags = []
        for item in raw_tags:
            if isinstance(item, Mapping):
                value = item.get("tag")
            else:
                value = item
            if value is not None and str(value).strip():
                tags.append(str(value).strip())

        base_url = self.config.base_url
        if base_url is None:
            raise KnowledgeSourceNotConfigured("WIKIJS_URL is not configured")
        page_url = "{}/{}".format(base_url, quote(path, safe="/"))

        metadata: Dict[str, Any] = {
            "wikijs_page_id": raw_id,
            "locale": str(page.get("locale") or self.config.locale),
            "description": str(page.get("description") or ""),
            "content_type": str(page.get("contentType") or "markdown"),
        }
        return KnowledgeDocument(
            id="wikijs:{}".format(raw_id),
            title=title,
            content=content,
            source=self.source_name,
            path=path,
            url=page_url,
            tags=tuple(tags),
            created_at=self._parse_datetime(page.get("createdAt"), "createdAt"),
            updated_at=self._parse_datetime(page.get("updatedAt"), "updatedAt"),
            metadata=metadata,
        )

    @staticmethod
    def _parse_datetime(value: Any, field_name: str) -> datetime:
        if not isinstance(value, str) or not value:
            raise WikiJSAPIError(
                "Wiki.js page response has an invalid {}".format(field_name)
            )
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise WikiJSAPIError(
                "Wiki.js page response has an invalid {}".format(field_name)
            ) from exc
        return WikiJSKnowledgeSource._as_utc(parsed)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
