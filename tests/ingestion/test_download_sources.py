import hashlib
import json
from pathlib import Path

import pytest

from src.ingestion.download_sources import (
    DownloadError,
    download_distribution,
    filename_from_url,
    select_inventory_items,
    sha256_file,
    verified_existing_file,
)


class FakeResponse:
    status_code = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        assert chunk_size > 0
        yield b"example,csv\n"
        yield b"1,value\n"


class FakeSession:
    def get(self, url, headers, stream, timeout):
        assert url == "https://data.cms.gov/example.csv"
        assert headers == {}
        assert stream is True
        assert timeout == 120
        return FakeResponse()


def test_filename_from_url_decodes_filename() -> None:
    url = "https://data.cms.gov/files/example%20file.csv"

    assert filename_from_url(url) == "example file.csv"


def test_sha256_file_matches_expected_digest(tmp_path: Path) -> None:
    path = tmp_path / "example.csv"
    path.write_bytes(b"example")

    assert sha256_file(path) == hashlib.sha256(b"example").hexdigest()


def test_select_inventory_items_filters_source_and_year() -> None:
    inventory = {
        "sources": [
            {"source_id": "one", "reporting_year": 2023},
            {"source_id": "one", "reporting_year": 2024},
            {"source_id": "two", "reporting_year": 2024},
        ]
    }

    selected = select_inventory_items(inventory, {"one"}, {2024})

    assert selected == [{"source_id": "one", "reporting_year": 2024}]


def test_select_inventory_items_rejects_unknown_source() -> None:
    inventory = {"sources": []}

    with pytest.raises(DownloadError, match="Unknown source IDs"):
        select_inventory_items(inventory, {"unknown"}, None)


def test_download_distribution_writes_file_and_receipt(tmp_path: Path) -> None:
    content = b"example,csv\n1,value\n"
    item = {
        "source_id": "example_source",
        "domain": "example",
        "reporting_year": 2024,
        "resource_identifier": "example-version",
        "download_url": "https://data.cms.gov/example.csv",
        "content_length_bytes": len(content),
    }

    receipt = download_distribution(
        item,
        tmp_path,
        FakeSession(),
        timeout_seconds=120,
        minimum_free_gib=0,
    )

    data_path = tmp_path / "example_source" / "2024" / "example.csv"

    assert data_path.read_bytes() == content
    assert receipt["bytes_downloaded"] == len(content)
    assert receipt["sha256"] == hashlib.sha256(content).hexdigest()
    assert verified_existing_file(data_path)


def test_verified_existing_file_rejects_bad_receipt(tmp_path: Path) -> None:
    data_path = tmp_path / "example.csv"
    data_path.write_bytes(b"example")
    receipt = {
        "bytes_downloaded": len(b"example"),
        "sha256": "incorrect",
    }
    data_path.with_suffix(".csv.receipt.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    assert verified_existing_file(data_path) is False
