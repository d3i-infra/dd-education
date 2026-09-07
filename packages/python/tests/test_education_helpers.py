"""Tests for education structure-helper extraction functions.

Ported from the pre-rebase `test_general_ddp_analyzer.py` (git show
master:packages/python/tests/test_general_ddp_analyzer.py), with the zip
fixtures built as in-memory `io.BytesIO` buffers instead of temp-file paths —
extraction_helpers now takes a reader per ADR-0026.
"""

import io
import json
import zipfile

from port.helpers.archive_set import ArchiveSet
from port.helpers.extraction_helpers import (
    extract_file_structures_from_zip,
    extract_zip_file_info,
)


def create_test_zip(files: dict[str, bytes]) -> io.BytesIO:
    """Create an in-memory zip archive with the given files and return it."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


class TestExtractFileStructures:
    def test_extracts_json_field_names(self):
        files = {"data.json": json.dumps({"name": "Alice", "age": 30}).encode()}
        buf = create_test_zip(files)
        df = extract_file_structures_from_zip(buf)
        assert not df.empty
        assert "filepath" in df.columns
        assert "field_name" in df.columns
        assert "data.json" in df["filepath"].values

    def test_extracts_csv_columns(self):
        files = {"data.csv": b"name,age\nAlice,30\n"}
        buf = create_test_zip(files)
        df = extract_file_structures_from_zip(buf)
        assert not df.empty
        assert "data.csv" in df["filepath"].values

    def test_empty_zip_returns_empty_dataframe(self):
        buf = create_test_zip({})
        df = extract_file_structures_from_zip(buf)
        assert df.empty

    def test_infer_types_replaces_values(self):
        files = {"data.json": json.dumps({"name": "Alice", "age": 30}).encode()}
        buf = create_test_zip(files)
        df = extract_file_structures_from_zip(buf, infer_types=True)
        # Values should be type names, not actual values
        values = df["value"].tolist()
        assert "Alice" not in values


class TestExtractFileStructuresSkipsNonStructureMembers:
    """Regression: only .json/.csv members may be read at all — a real
    export's images/videos must never be pulled into memory just to be
    discarded by the extension check (ADR-0026)."""

    def test_single_reader_only_reads_json_and_csv_members(self, monkeypatch):
        files = {
            "data.json": json.dumps({"a": 1}).encode(),
            "photo.bin": b"\x00" * (5 * 1024 * 1024),
        }
        buf = create_test_zip(files)

        original_read = zipfile.ZipFile.read
        read_calls: list[str] = []

        def spy_read(self, name, *args, **kwargs):
            read_calls.append(name)
            return original_read(self, name, *args, **kwargs)

        monkeypatch.setattr(zipfile.ZipFile, "read", spy_read)

        df = extract_file_structures_from_zip(buf)

        assert read_calls == ["data.json"]
        assert "photo.bin" not in df["filepath"].values

    def test_archive_set_only_reads_json_and_csv_members(self, monkeypatch):
        part = create_test_zip({
            "data.json": json.dumps({"a": 1}).encode(),
            "photo.bin": b"\x00" * (5 * 1024 * 1024),
        })
        part.name = "part-1.zip"
        part.size = len(part.getvalue())
        archive_set = ArchiveSet([part])

        original_read_member = ArchiveSet.read_member
        read_calls: list[str] = []

        def spy_read_member(self, path):
            read_calls.append(path)
            return original_read_member(self, path)

        monkeypatch.setattr(ArchiveSet, "read_member", spy_read_member)

        df = extract_file_structures_from_zip(archive_set)

        assert read_calls == ["data.json"]
        assert "photo.bin" not in df["filepath"].values


class TestExtractZipFileInfo:
    def test_returns_file_metadata(self):
        files = {"readme.txt": b"hello", "data/file.json": b"{}"}
        buf = create_test_zip(files)
        df = extract_zip_file_info(buf)
        assert len(df) == 2
        assert "file_path" in df.columns
        assert "file_size" in df.columns

    def test_includes_mime_type(self):
        files = {"data.json": b"{}"}
        buf = create_test_zip(files)
        df = extract_zip_file_info(buf)
        assert "mime_type" in df.columns

    def test_skips_directories(self):
        buf = create_test_zip({"dir/file.txt": b"content"})
        df = extract_zip_file_info(buf)
        # Should only have the file, not the directory
        assert all("file.txt" in p for p in df["file_path"].values)
