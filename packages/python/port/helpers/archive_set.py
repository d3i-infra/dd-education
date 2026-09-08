"""One logical archive-set over N uploaded zip parts.

Owns canonical part ordering (by `(name, size)` metadata, never selection
order), the union member inventory with provenance, and on-demand per-part
reads. See the archive-set ADR; ADR-0024 (amended) moves inventory discovery
here.
"""
import logging
import zipfile
from collections import Counter
from contextlib import AbstractContextManager, contextmanager
from typing import IO, Iterator, Protocol, runtime_checkable

from port.helpers.uploads import MAX_MEMBER_UNCOMPRESSED_BYTES

logger = logging.getLogger(__name__)


class MemberTooLargeError(Exception):
    """A zip member's uncompressed size exceeds MAX_MEMBER_UNCOMPRESSED_BYTES."""


MACOS_METADATA_DIR = "__MACOSX/"
MACOS_RESOURCE_FORK_PREFIX = "._"


def is_macos_metadata(path: str) -> bool:
    """True for entries macOS Finder adds when re-zipping: the ``__MACOSX/`` tree and
    ``._name`` AppleDouble resource forks. They are never DDP content and they
    collide with real members on basename matching."""
    if path.startswith(MACOS_METADATA_DIR):
        return True
    return path.rsplit("/", 1)[-1].startswith(MACOS_RESOURCE_FORK_PREFIX)


@runtime_checkable
class ArchiveSource(Protocol):
    @property
    def members(self) -> list[str]: ...
    def read_member(self, path: str) -> bytes: ...
    def open_member(self, path: str) -> AbstractContextManager[IO[bytes]]: ...


def _guarded_read(zf: zipfile.ZipFile, path: str) -> bytes:
    info = zf.getinfo(path)
    if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
        raise MemberTooLargeError(
            f"member uncompressed size {info.file_size} exceeds "
            f"{MAX_MEMBER_UNCOMPRESSED_BYTES}"
        )
    return zf.read(path)


class SingleArchiveSource:
    """ArchiveSource over one already-validated archive (the single-file path)."""

    def __init__(self, archive, members: list[str]):
        self._archive = archive
        self.members = members

    def read_member(self, path: str) -> bytes:
        with zipfile.ZipFile(self._archive, "r") as zf:
            return _guarded_read(zf, path)

    @contextmanager
    def open_member(self, path: str) -> Iterator[IO[bytes]]:
        """Streaming counterpart to read_member: yields the member's decompression
        stream without materializing it. Deliberately not size-guarded — the guard
        bounds full-buffer decompression; a streaming consumer bounds its own memory."""
        with zipfile.ZipFile(self._archive, "r") as zf:
            with zf.open(path) as stream:
                yield stream


class ArchiveSet:
    """N uploaded parts presented as one archive. Raises zipfile.BadZipFile if
    any part is unreadable (caller converts to validation status, ADR-0018/0024).

    Canonical part order is `(name, size)` — both JS-reported metadata, never
    selection order, never a byte read. Parts with identical name AND size are
    indistinguishable without reading bytes (which the pre-validation path
    forbids), so their relative order among themselves is unspecified (falls
    out of Python's stable sort over whatever order they were passed in).

    Duplicate paths are tracked in `self.duplicates` under two distinct keys,
    counted independently so neither inflates the other:
      - "DuplicateMemberAcrossParts": a path's first-in-canonical-order part
        wins; `read_member`/`part_index_of` resolve to that part.
      - "DuplicateMemberWithinPart": the zip format allows the same path to
        appear more than once inside a single part's central directory.
        We deliberately do not fight `zipfile` for first-entry semantics
        here (real exports show zero such duplicates; this is a defensive
        observability path) — a within-part duplicate path resolves to
        that part's *last* central-directory entry, i.e. plain Python
        `zipfile` semantics (`ZipFile.read`/`getinfo` on a repeated name).
    """

    def __init__(self, parts: list) -> None:
        self._parts = sorted(
            parts, key=lambda p: (getattr(p, "name", ""), getattr(p, "size", 0))
        )
        self.duplicates: Counter = Counter()
        self._owner: dict[str, int] = {}
        self._info_by_path: dict[str, zipfile.ZipInfo] | None = None
        members: list[str] = []
        for index, part in enumerate(self._parts):
            seen_in_part: set[str] = set()
            with zipfile.ZipFile(part, "r") as zf:
                for path in zf.namelist():
                    if is_macos_metadata(path):
                        continue
                    if path in seen_in_part:
                        self.duplicates["DuplicateMemberWithinPart"] += 1
                        continue
                    seen_in_part.add(path)
                    if path in self._owner:
                        self.duplicates["DuplicateMemberAcrossParts"] += 1
                        continue
                    self._owner[path] = index
                    members.append(path)
        self.members = sorted(members)

    def part_index_of(self, path: str) -> int:
        return self._owner[path]

    def _info_map(self) -> dict[str, zipfile.ZipInfo]:
        """Central-directory metadata for every member, built once and kept.

        One pass over the parts answers every `member_info` call. Building it per call
        instead reopened and reparsed a part's central directory once per member, so a
        table over the whole set — the issue report's file overview — reparsed the same
        directory thousands of times.

        Only the entries this set resolves to are kept, so a path owned by an earlier
        part is not shadowed by a later part's entry at the same name. Within one part a
        repeated name resolves to its last central-directory entry, matching what
        `getinfo` and `read_member` already do.
        """
        if self._info_by_path is None:
            info_by_path: dict[str, zipfile.ZipInfo] = {}
            for index, part in enumerate(self._parts):
                with zipfile.ZipFile(part, "r") as zf:
                    for info in zf.infolist():
                        if self._owner.get(info.filename) == index:
                            info_by_path[info.filename] = info
            self._info_by_path = info_by_path
        return self._info_by_path

    def member_info(self, path: str) -> zipfile.ZipInfo:
        """Return the owning part's central-directory metadata for `path`
        (size, modified time, ...) without reading the member's content —
        `ZipFile(part, "r")` only parses the central directory index, never
        decompresses member data (ADR-0026).

        Raises KeyError for a path this set does not hold.
        """
        return self._info_map()[path]

    def read_member(self, path: str) -> bytes:
        """Read `path` from its owning (first-in-canonical-order) part.

        If that part's zip has more than one entry at `path` (a within-part
        duplicate — see class docstring), this returns the *last* entry's
        content, matching Python `zipfile` semantics.
        """
        part = self._parts[self._owner[path]]
        with zipfile.ZipFile(part, "r") as zf:
            return _guarded_read(zf, path)

    @contextmanager
    def open_member(self, path: str) -> Iterator[IO[bytes]]:
        """Streaming counterpart to read_member: yields the owning part's
        decompression stream for `path` without materializing it. Deliberately
        not size-guarded — the guard bounds full-buffer decompression; a
        streaming consumer bounds its own memory."""
        part = self._parts[self._owner[path]]
        with zipfile.ZipFile(part, "r") as zf:
            with zf.open(path) as stream:
                yield stream
