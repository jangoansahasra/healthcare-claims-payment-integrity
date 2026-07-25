from pathlib import Path

from src.ingestion.probe_sources import (
    build_inventory_document,
    parse_content_range,
    probe_download,
    write_inventory_document,
)


class FakeResponse:
    def __init__(self, status: int, headers: dict[str, str]) -> None:
        self.status = status
        self.headers = headers

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_parse_content_range_extracts_total_size() -> None:
    assert parse_content_range("bytes 0-0/1048576") == 1048576
    assert parse_content_range("bytes 0-0/*") is None
    assert parse_content_range(None) is None


def test_probe_download_uses_head_content_length(monkeypatch) -> None:
    response = FakeResponse(
        200,
        {
            "Content-Length": "1048576",
            "Content-Type": "text/csv",
        },
    )

    monkeypatch.setattr(
        "src.ingestion.probe_sources.urlopen",
        lambda request, timeout: response,
    )

    metadata = probe_download("https://data.cms.gov/example.csv")

    assert metadata["content_length_bytes"] == 1048576
    assert metadata["size_detection_method"] == "head_content_length"


def test_probe_download_falls_back_to_content_range(monkeypatch) -> None:
    responses = iter(
        [
            FakeResponse(200, {"Content-Type": "text/csv"}),
            FakeResponse(
                206,
                {
                    "Content-Type": "text/csv",
                    "Content-Length": "1",
                    "Content-Range": "bytes 0-0/2097152",
                },
            ),
        ]
    )

    def fake_urlopen(request, timeout):
        assert timeout == 60
        return next(responses)

    monkeypatch.setattr(
        "src.ingestion.probe_sources.urlopen",
        fake_urlopen,
    )

    metadata = probe_download("https://data.cms.gov/example.csv")

    assert metadata["http_status"] == 206
    assert metadata["content_length_bytes"] == 2097152
    assert metadata["size_detection_method"] == "range_content_range"


def test_build_inventory_document_summarizes_known_sizes() -> None:
    inventory = [
        {"content_length_bytes": 100},
        {"content_length_bytes": 200},
        {"content_length_bytes": None},
    ]

    document = build_inventory_document(inventory)

    assert document["source_count"] == 3
    assert document["sources_with_known_size"] == 2
    assert document["known_total_bytes"] == 300


def test_write_inventory_document_creates_output(tmp_path: Path) -> None:
    output_path = tmp_path / "metadata" / "inventory.json"
    document = {
        "inventory_version": 1,
        "source_count": 0,
        "sources": [],
    }

    write_inventory_document(document, output_path)

    assert output_path.is_file()
    assert '"inventory_version": 1' in output_path.read_text(encoding="utf-8")
