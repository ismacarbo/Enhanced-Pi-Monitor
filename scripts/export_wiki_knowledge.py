#!/usr/bin/env python3
"""Export Wiki.js pages as normalized JSON Lines for future ingestion."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PIMONITOR_ROOT = REPOSITORY_ROOT / "PiMonitor"
if str(PIMONITOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PIMONITOR_ROOT))

from knowledge.sources.base import KnowledgeSourceNotConfigured  # noqa: E402
from knowledge.sources.wikijs import (  # noqa: E402
    WikiJSAPIError,
    WikiJSConfig,
    WikiJSConfigurationError,
    WikiJSKnowledgeSource,
)


def _parse_since(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--since must be an ISO-8601 timestamp"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export readable Wiki.js pages to one JSON object per line."
    )
    parser.add_argument("--output", required=True, type=Path, help="Output JSONL path")
    parser.add_argument(
        "--since",
        type=_parse_since,
        help="Only export pages updated at or after this ISO-8601 timestamp",
    )
    parser.add_argument("--url", help="Override WIKIJS_URL for this invocation")
    parser.add_argument("--locale", help="Override WIKIJS_LOCALE")
    parser.add_argument("--timeout", type=float, help="HTTP timeout in seconds")
    return parser


def export_documents(
    output_path: Path, source: WikiJSKnowledgeSource, since=None
) -> int:
    documents = (
        source.get_updated_documents(since) if since else source.list_documents()
    )
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(output_path.parent),
            prefix=".{}-".format(output_path.name),
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_path = Path(output_file.name)
            os.chmod(temporary_path, 0o600)
            for document in documents:
                output_file.write(
                    json.dumps(document.to_dict(), ensure_ascii=False, sort_keys=True)
                )
                output_file.write("\n")
        temporary_path.replace(output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return len(documents)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        current = WikiJSConfig.from_env()
        config = WikiJSConfig(
            base_url=args.url or current.base_url,
            api_token=current.api_token,
            locale=args.locale or current.locale,
            timeout_seconds=(
                args.timeout if args.timeout is not None else current.timeout_seconds
            ),
        )
        count = export_documents(
            args.output, WikiJSKnowledgeSource(config=config), since=args.since
        )
    except (
        KnowledgeSourceNotConfigured,
        WikiJSConfigurationError,
        WikiJSAPIError,
    ) as exc:
        print("Wiki.js export failed: {}".format(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print("Could not write export: {}".format(exc), file=sys.stderr)
        return 3

    print("Exported {} Wiki.js document(s) to {}".format(count, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
