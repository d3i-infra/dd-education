"""Tests for education structure-helper extraction functions.

Ported from the pre-rebase `test_general_ddp_analyzer.py` (git show
master:packages/python/tests/test_general_ddp_analyzer.py), with the zip
fixtures built as in-memory `io.BytesIO` buffers instead of temp-file paths —
extraction_helpers now takes a reader per ADR-0026.
"""

import io
import json
import zipfile

import pytest

import port.helpers.extraction_helpers as eh
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

    def test_single_reader_skips_a_member_over_the_size_cap(self, monkeypatch):
        """A member whose *uncompressed* size exceeds the cap is skipped before
        ``zf.read`` is called at all — the cap guards against decompression-bomb
        style members, not against a large file that merely reads slowly."""
        files = {
            "small.json": json.dumps({"a": 1}).encode(),
            "huge.json": json.dumps({"b": "x" * 1000}).encode(),
        }
        buf = create_test_zip(files)

        monkeypatch.setattr(eh, "MAX_MEMBER_UNCOMPRESSED_BYTES", 100)

        original_read = zipfile.ZipFile.read
        read_calls: list[str] = []

        def spy_read(self, name, *args, **kwargs):
            read_calls.append(name)
            return original_read(self, name, *args, **kwargs)

        monkeypatch.setattr(zipfile.ZipFile, "read", spy_read)

        df = extract_file_structures_from_zip(buf)

        assert read_calls == ["small.json"]
        assert "huge.json" not in df["filepath"].values
        assert "small.json" in df["filepath"].values


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


class TestTheStructureOverviewIsBounded:
    """`dict_denester` makes one row per JSON leaf, so an export with a year of messages
    in one member flattens to a frame nobody can read and nobody should upload. Two caps
    bound it: one per member, one per call."""

    def _member_with(self, field_count: int) -> dict[str, bytes]:
        return {"big.json": json.dumps({f"f{i}": i for i in range(field_count)}).encode()}

    def test_a_member_under_the_cap_is_listed_whole(self):
        df = extract_file_structures_from_zip(create_test_zip(self._member_with(10)))
        assert len(df) == 10
        assert eh.TRUNCATION_MARKER not in df["field_name"].values

    def test_a_member_over_the_cap_is_cut_and_says_so(self):
        over = eh.MAX_STRUCTURE_ROWS_PER_MEMBER + 37
        df = extract_file_structures_from_zip(create_test_zip(self._member_with(over)))

        assert len(df) == eh.MAX_STRUCTURE_ROWS_PER_MEMBER + 1, "the cap plus one marker row"
        marker = df.iloc[-1]
        assert marker["field_name"] == eh.TRUNCATION_MARKER
        assert marker["filepath"] == "big.json"
        assert marker["value"] == "<37 more>"

    def test_a_csv_header_over_the_cap_is_cut_too(self):
        over = eh.MAX_STRUCTURE_ROWS_PER_MEMBER + 5
        header = ",".join(f"c{i}" for i in range(over))
        row = ",".join("v" for _ in range(over))
        df = extract_file_structures_from_zip(create_test_zip({"wide.csv": f"{header}\n{row}\n".encode()}))

        assert len(df) == eh.MAX_STRUCTURE_ROWS_PER_MEMBER + 1
        assert df.iloc[-1]["value"] == "<5 more>"

    def test_the_total_cap_stops_the_scan_and_names_the_members_left(self, monkeypatch):
        """Reaching the total cap leaves the remaining members unread, not merely
        unlisted — the point of the cap is to stop the work, not to trim the output."""
        monkeypatch.setattr(eh, "MAX_STRUCTURE_ROWS_PER_MEMBER", 10)
        monkeypatch.setattr(eh, "MAX_STRUCTURE_ROWS_TOTAL", 25)

        files = {f"m{i}.json": json.dumps({f"f{j}": j for j in range(10)}).encode() for i in range(8)}
        buf = create_test_zip(files)

        original_read = zipfile.ZipFile.read
        read_calls: list[str] = []

        def spy_read(self, name, *args, **kwargs):
            read_calls.append(name)
            return original_read(self, name, *args, **kwargs)

        monkeypatch.setattr(zipfile.ZipFile, "read", spy_read)

        df = extract_file_structures_from_zip(buf)

        assert read_calls == ["m0.json", "m1.json", "m2.json"], "the fourth member is never read"
        marker = df.iloc[-1]
        assert marker["field_name"] == eh.TRUNCATION_MARKER
        assert marker["filepath"] == "m3.json"
        assert marker["value"] == "<5 more>", "m3 through m7"

    def test_an_archive_set_is_capped_the_same_way(self, monkeypatch):
        monkeypatch.setattr(eh, "MAX_STRUCTURE_ROWS_PER_MEMBER", 10)
        monkeypatch.setattr(eh, "MAX_STRUCTURE_ROWS_TOTAL", 25)

        part = create_test_zip(
            {f"m{i}.json": json.dumps({f"f{j}": j for j in range(10)}).encode() for i in range(8)}
        )
        part.name = "part-1.zip"
        part.size = len(part.getvalue())

        df = extract_file_structures_from_zip(ArchiveSet([part]))

        assert len(df) == 31, "three whole members, plus one marker"
        assert df.iloc[-1]["field_name"] == eh.TRUNCATION_MARKER


class TestArchiveSetMemberInfoIsCached:
    """`extract_zip_file_info` asks for every member's metadata in turn. Reopening the
    owning part per call reparsed one central directory once per member; the map is built
    once instead."""

    def _set_of(self, member_count: int) -> ArchiveSet:
        part = create_test_zip({f"f{i}.json": b"{}" for i in range(member_count)})
        part.name = "part-1.zip"
        part.size = len(part.getvalue())
        return ArchiveSet([part])

    def test_the_parts_are_opened_once_however_many_members_are_asked_about(self, monkeypatch):
        archive_set = self._set_of(12)

        original_init = zipfile.ZipFile.__init__
        opens: list[int] = []

        def counting_init(self, *args, **kwargs):
            opens.append(1)
            return original_init(self, *args, **kwargs)

        monkeypatch.setattr(zipfile.ZipFile, "__init__", counting_init)

        for member in archive_set.members:
            archive_set.member_info(member)

        assert len(opens) == 1, "one pass over the one part, not one open per member"

    def test_the_metadata_is_the_same_as_before_the_cache(self):
        archive_set = self._set_of(3)
        for member in archive_set.members:
            info = archive_set.member_info(member)
            assert info.filename == member
            assert info.file_size == 2

    def test_a_path_the_set_does_not_hold_is_a_key_error(self):
        archive_set = self._set_of(2)
        with pytest.raises(KeyError):
            archive_set.member_info("nothing/here.json")

    def test_a_path_owned_by_the_first_part_is_not_shadowed_by_a_later_part(self):
        """Across-part duplicates resolve to the first part in canonical order, and the
        cached map has to resolve them the same way `read_member` does."""
        first = create_test_zip({"shared.json": b'{"a": 1}'})
        first.name = "a-part.zip"
        first.size = len(first.getvalue())
        second = create_test_zip({"shared.json": b'{"a": 1, "b": 2, "c": 3}'})
        second.name = "b-part.zip"
        second.size = len(second.getvalue())

        archive_set = ArchiveSet([second, first])

        assert archive_set.part_index_of("shared.json") == 0
        assert archive_set.member_info("shared.json").file_size == len(b'{"a": 1}')
