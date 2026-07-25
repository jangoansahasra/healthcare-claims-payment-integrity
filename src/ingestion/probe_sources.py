from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from src.ingestion.cms_catalog import USER_AGENT

DEFAULT_RESOLUTION_PATH = Path("data/metadata/cms_source_resolution.json")
DEFAULT_OUTPUT_PATH = Path("data/metadata/cms_source_inventory.json")


def parse_content_range(content_range: str | None) -> int | None:
    """Extract total remote size from a Content-Range header."""
    if not content_range or "/" not in content_range:
        return None

    total = content_range.rsplit("/", maxsplit=1)[-1]
    return int(total) if total.isdigit() else None


def response_metadata(
    response,
    content_length_bytes: int | None,
    size_detection_method: str | None,
) -> dict[str, Any]:
    """Build normalized metadata from an HTTP response."""
    return {
        "http_status": response.status,
        "content_length_bytes": content_length_bytes,
        "content_type": response.headers.get("Content-Type"),
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "size_detection_method": size_detection_method,
    }


def probe_download(
    url: str,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Inspect remote file metadata without downloading its contents."""
    head_request = Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="HEAD",
    )

    with urlopen(head_request, timeout=timeout_seconds) as response:
        content_length = response.headers.get("Content-Length")

        if content_length is not None:
            return response_metadata(
                response,
                int(content_length),
                "head_content_length",
            )

    range_request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Range": "bytes=0-0",
        },
        method="GET",
    )

    with urlopen(range_request, timeout=timeout_seconds) as response:
        total_size = parse_content_range(response.headers.get("Content-Range"))

        if total_size is not None:
            return response_metadata(
                response,
                total_size,
                "range_content_range",
            )

        content_length = response.headers.get("Content-Length")
        if response.status == 200 and content_length is not None:
            return response_metadata(
                response,
                int(content_length),
                "range_fallback_content_length",
            )

        return response_metadata(response, None, None)


def probe_resolved_sources(
    resolution_document: dict[str, Any],
) -> list[dict[str, Any]]:
    """Probe all resolved CMS download URLs."""
    inventory: list[dict[str, Any]] = []

    for source in resolution_document["sources"]:
        remote_metadata = probe_download(source["download_url"])
        inventory.append(
            {
                "source_id": source["source_id"],
                "domain": source["domain"],
                "reporting_year": source["reporting_year"],
                "resource_identifier": source["resource_identifier"],
                "download_url": source["download_url"],
                **remote_metadata,
            }
        )

    return inventory


def build_inventory_document(
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the persisted remote-file inventory."""
    known_sizes = [
        item["content_length_bytes"]
        for item in inventory
        if item["content_length_bytes"] is not None
    ]

    return {
        "inventory_version": 1,
        "probed_at_utc": datetime.now(UTC).isoformat(),
        "source_count": len(inventory),
        "sources_with_known_size": len(known_sizes),
        "known_total_bytes": sum(known_sizes),
        "sources": inventory,
    }


def write_inventory_document(
    document: dict[str, Any],
    output_path: Path,
) -> None:
    """Write the source inventory as formatted JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect resolved CMS files without downloading them."
    )
    parser.add_argument(
        "--resolution",
        type=Path,
        default=DEFAULT_RESOLUTION_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resolution = json.loads(args.resolution.read_text(encoding="utf-8"))
    inventory = probe_resolved_sources(resolution)
    document = build_inventory_document(inventory)
    write_inventory_document(document, args.output)

    total_gib = document["known_total_bytes"] / (1024**3)
    print(f"Probed {document['source_count']} CMS distributions")
    print(
        f"Known sizes: {document['sources_with_known_size']}/{document['source_count']}"
    )
    print(f"Known total size: {total_gib:.2f} GiB")
    print(f"Inventory written to {args.output}")


if __name__ == "__main__":
    main()
