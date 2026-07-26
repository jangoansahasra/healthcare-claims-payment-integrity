from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests
import yaml

DEFAULT_INVENTORY_PATH = Path("data/metadata/cms_source_inventory.json")
DEFAULT_ACQUISITION_PATH = Path("config/acquisition.yml")
DEFAULT_TARGET_ROOT = Path("data/raw/cms")
CHUNK_SIZE_BYTES = 8 * 1024 * 1024


class DownloadError(RuntimeError):
    """Raised when a governed source cannot be downloaded safely."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        content = json.load(file)

    if not isinstance(content, dict):
        raise DownloadError(f"{path} must contain a JSON object")

    return content


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    if not isinstance(content, dict):
        raise DownloadError(f"{path} must contain a YAML mapping")

    return content


def filename_from_url(url: str) -> str:
    """Extract a safe local filename from an official download URL."""
    filename = unquote(Path(urlparse(url).path).name)

    if not filename or filename in {".", ".."}:
        raise DownloadError(f"Unable to determine filename from URL: {url}")

    return filename


def sha256_file(path: Path) -> str:
    """Calculate a streaming SHA-256 checksum."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_SIZE_BYTES), b""):
            digest.update(chunk)

    return digest.hexdigest()


def available_disk_gib(path: Path) -> float:
    """Return available disk space for a destination path."""
    existing_path = path
    while not existing_path.exists():
        existing_path = existing_path.parent

    return shutil.disk_usage(existing_path).free / (1024**3)


def require_free_space(path: Path, minimum_free_gib: float) -> None:
    available = available_disk_gib(path)

    if available < minimum_free_gib:
        raise DownloadError(
            f"Insufficient free space: {available:.2f} GiB available; "
            f"{minimum_free_gib:.2f} GiB required"
        )


def receipt_path(data_path: Path) -> Path:
    return data_path.with_suffix(f"{data_path.suffix}.receipt.json")


def verified_existing_file(data_path: Path) -> bool:
    """Return whether an existing file matches its acquisition receipt."""
    receipt_file = receipt_path(data_path)

    if not data_path.is_file() or not receipt_file.is_file():
        return False

    receipt = load_json(receipt_file)

    return receipt.get("bytes_downloaded") == data_path.stat().st_size and receipt.get(
        "sha256"
    ) == sha256_file(data_path)


def select_inventory_items(
    inventory: dict[str, Any],
    source_ids: set[str],
    years: set[int] | None,
) -> list[dict[str, Any]]:
    """Select explicit source IDs and optional reporting years."""
    selected = [
        item
        for item in inventory["sources"]
        if item["source_id"] in source_ids
        and (years is None or item["reporting_year"] in years)
    ]

    missing_source_ids = source_ids - {
        item["source_id"] for item in inventory["sources"]
    }
    if missing_source_ids:
        missing = ", ".join(sorted(missing_source_ids))
        raise DownloadError(f"Unknown source IDs: {missing}")

    return sorted(
        selected,
        key=lambda item: (item["source_id"], item["reporting_year"]),
    )


def download_distribution(
    item: dict[str, Any],
    target_root: Path,
    session: requests.Session,
    timeout_seconds: int,
    minimum_free_gib: float,
) -> dict[str, Any]:
    """Download one CMS distribution with resume and receipt support."""
    filename = filename_from_url(item["download_url"])
    target_directory = target_root / item["source_id"] / str(item["reporting_year"])
    target_directory.mkdir(parents=True, exist_ok=True)

    data_path = target_directory / filename
    partial_path = data_path.with_suffix(f"{data_path.suffix}.part")

    if verified_existing_file(data_path):
        receipt = load_json(receipt_path(data_path))
        print(f"Verified existing file: {data_path}")
        return receipt

    require_free_space(target_directory, minimum_free_gib)

    resume_bytes = partial_path.stat().st_size if partial_path.exists() else 0
    headers = {"Range": f"bytes={resume_bytes}-"} if resume_bytes else {}

    with session.get(
        item["download_url"],
        headers=headers,
        stream=True,
        timeout=timeout_seconds,
    ) as response:
        response.raise_for_status()

        if resume_bytes and response.status_code == 206:
            mode = "ab"
        else:
            mode = "wb"
            resume_bytes = 0

        with partial_path.open(mode) as file:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE_BYTES):
                if chunk:
                    file.write(chunk)

    actual_size = partial_path.stat().st_size
    expected_size = item.get("content_length_bytes")

    if expected_size is not None and actual_size != expected_size:
        raise DownloadError(
            f"Size mismatch for {filename}: "
            f"expected {expected_size}, received {actual_size}"
        )

    partial_path.replace(data_path)
    checksum = sha256_file(data_path)

    receipt = {
        "receipt_version": 1,
        "acquired_at_utc": datetime.now(UTC).isoformat(),
        "source_id": item["source_id"],
        "domain": item["domain"],
        "reporting_year": item["reporting_year"],
        "resource_identifier": item["resource_identifier"],
        "download_url": item["download_url"],
        "local_path": str(data_path),
        "bytes_downloaded": data_path.stat().st_size,
        "sha256": checksum,
        "expected_bytes": expected_size,
    }

    receipt_path(data_path).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        f"Downloaded {item['source_id']} {item['reporting_year']}: "
        f"{data_path.stat().st_size / (1024**2):.2f} MiB"
    )

    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely download explicitly selected CMS distributions."
    )
    parser.add_argument(
        "--source-id",
        action="append",
        required=True,
        help="Source ID to download. Repeat for multiple sources.",
    )
    parser.add_argument(
        "--year",
        action="append",
        type=int,
        help="Reporting year to download. Repeat for multiple years.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY_PATH,
    )
    parser.add_argument(
        "--acquisition-config",
        type=Path,
        default=DEFAULT_ACQUISITION_PATH,
    )
    parser.add_argument(
        "--target-root",
        type=Path,
        default=DEFAULT_TARGET_ROOT,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inventory = load_json(args.inventory)
    acquisition = load_yaml(args.acquisition_config)
    controls = acquisition["global_controls"]

    selected = select_inventory_items(
        inventory,
        set(args.source_id),
        set(args.year) if args.year else None,
    )

    if not selected:
        raise DownloadError("No distributions matched the selection")

    print(f"Selected {len(selected)} distribution(s)")
    print(f"Free disk before download: {available_disk_gib(args.target_root):.2f} GiB")

    with requests.Session() as session:
        for item in selected:
            download_distribution(
                item,
                args.target_root,
                session,
                controls["request_timeout_seconds"],
                controls["minimum_required_free_disk_gib"],
            )

    print(f"Free disk after download: {available_disk_gib(args.target_root):.2f} GiB")


if __name__ == "__main__":
    main()
