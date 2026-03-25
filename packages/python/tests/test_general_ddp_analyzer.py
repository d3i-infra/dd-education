"""Tests for General DDP Analyzer extraction helpers."""

import json
import sys
import zipfile
import tempfile
from unittest.mock import MagicMock

sys.modules["js"] = MagicMock()

from port.helpers.extraction_helpers import (
    extract_file_structures_from_zip,
    extract_zip_file_info,
)


def create_test_zip(files: dict[str, bytes]) -> str:
    """Create a temporary zip file with the given files and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    tmp.close()
    return tmp.name


class TestExtractFileStructures:
    def test_extracts_json_field_names(self):
        files = {"data.json": json.dumps({"name": "Alice", "age": 30}).encode()}
        path = create_test_zip(files)
        df = extract_file_structures_from_zip(path)
        assert not df.empty
        assert "filepath" in df.columns
        assert "field_name" in df.columns
        assert "data.json" in df["filepath"].values

    def test_extracts_csv_columns(self):
        files = {"data.csv": b"name,age\nAlice,30\n"}
        path = create_test_zip(files)
        df = extract_file_structures_from_zip(path)
        assert not df.empty
        assert "data.csv" in df["filepath"].values

    def test_empty_zip_returns_empty_dataframe(self):
        path = create_test_zip({})
        df = extract_file_structures_from_zip(path)
        assert df.empty

    def test_infer_types_replaces_values(self):
        files = {"data.json": json.dumps({"name": "Alice", "age": 30}).encode()}
        path = create_test_zip(files)
        df = extract_file_structures_from_zip(path, infer_types=True)
        # Values should be type names, not actual values
        values = df["value"].tolist()
        assert "Alice" not in values


class TestExtractZipFileInfo:
    def test_returns_file_metadata(self):
        files = {"readme.txt": b"hello", "data/file.json": b"{}"}
        path = create_test_zip(files)
        df = extract_zip_file_info(path)
        assert len(df) == 2
        assert "file_path" in df.columns
        assert "file_size" in df.columns

    def test_includes_mime_type(self):
        files = {"data.json": b"{}"}
        path = create_test_zip(files)
        df = extract_zip_file_info(path)
        assert "mime_type" in df.columns

    def test_skips_directories(self):
        path = create_test_zip({"dir/file.txt": b"content"})
        df = extract_zip_file_info(path)
        # Should only have the file, not the directory
        assert all("file.txt" in p for p in df["file_path"].values)
