"""
This module contains helper functions that can be used during the data extraction process
""" 
import math
import re
import logging
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Callable, IO, Iterator
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import zipfile

from port.api.file_utils import SeekableBinaryReader
from port.helpers.archive_set import ArchiveSet, ArchiveSource, SingleArchiveSource, is_macos_metadata
from port.helpers.uploads import MAX_MEMBER_UNCOMPRESSED_BYTES
import csv
import io
import json

import pandas as pd
import numpy as np


logger = logging.getLogger(__name__)

# Non-propagating logger for zip content enumeration.
# Contains PII (contact names in file paths). Inert by default —
# a developer must explicitly attach a handler in a debug session.
content_logger = logging.getLogger(f"{__name__}.content")
content_logger.propagate = False
content_logger.addHandler(logging.NullHandler())


def dict_denester(inp: dict[Any, Any] | list[Any], new: dict[Any, Any] | None = None, name: str = "", run_first: bool = True) -> dict[Any, Any]:
    """
    Denests a dictionary or list, returning a new flattened dictionary.

    Args:
        inp (dict[Any, Any] | list[Any]): The input dictionary or list to be denested.
        new (dict[Any, Any] | None, optional): The dictionary to store denested key-value pairs. Defaults to None.
        name (str, optional): The current key name in the denesting process. Defaults to "".
        run_first (bool, optional): Flag to indicate if this is the first run of the function. Defaults to True.

    Returns:
        dict[Any, Any]: A new denested dictionary.

    Examples::

        >>> nested_dict = {"a": {"b": {"c": 1}}, "d": [2, 3]}
        >>> dict_denester(nested_dict)
        {"a-b-c": 1, "d-0": 2, "d-1": 3}
    """
    if run_first:
        new = {}

    if isinstance(inp, dict):
        for k, v in inp.items():
            if isinstance(v, (dict, list)):
                dict_denester(v, new, f"{name}-{str(k)}", run_first=False)
            else:
                newname = f"{name}-{k}"
                new.update({newname[1:]: v})  # type: ignore

    elif isinstance(inp, list):
        for i, item in enumerate(inp):
            dict_denester(item, new, f"{name}-{i}", run_first=False)

    else:
        new.update({name[1:]: inp})  # type: ignore

    return new  # type: ignore


def find_item(d: dict[Any, Any], key_to_match: str) -> str:
    """
    Finds the least nested value in a denested dictionary whose key contains the given key_to_match.

    Args:
        d (dict[Any, Any]): A denested dictionary to search in.
        key_to_match (str): The substring to match in the keys.

    Returns:
        str: The value of the least nested key containing key_to_match.
             Returns an empty string if no match is found.

    Raises:
        Exception: Logs an error message if an exception occurs during the search.

    Examples::

        >>> d = {"asd-asd-asd": 1, "asd-asd": 2, "qwe": 3}
        >>> find_item(d, "asd")
        "2"
    """
    out = ""
    pattern = r"{}".format(f"^.*{key_to_match}.*$")
    depth = math.inf

    try:
        for k, v in d.items():
            if re.match(pattern, k):
                depth_current_match = k.count("-")
                if depth_current_match < depth:
                    depth = depth_current_match
                    out = str(v)
    except Exception as e:
        logger.error(e)

    return out


def find_items(d: dict[Any, Any], key_to_match: str) -> list:
    """
    Finds all values in a denested dictionary whose keys contain the given key_to_match.

    Args:
        d (dict[Any, Any]): A denested dictionary to search in.
        key_to_match (str): The substring to match in the keys.

    Returns:
        list: A list of all values whose keys contain key_to_match.

    Raises:
        Exception: Logs an error message if an exception occurs during the search.

    Examples::

        >>> d = {"asd-1": "a", "asd-2": "b", "qwe": "c"}
        >>> find_items(d, "asd")
        ["a", "b"]
    """
    out = []
    pattern = r"{}".format(f"^.*{key_to_match}.*$")

    try:
        for k, v in d.items():
            if re.match(pattern, k):
                out.append(str(v))
    except Exception as e:
        logger.error("bork bork: %s", e)

    return out


def json_dumper(zfile: str) -> pd.DataFrame:
    """
    Reads all JSON files in a zip file, flattens them, and combines them into a single DataFrame.

    Args:
        zfile (str): Path to the zip file containing JSON files.

    Returns:
        pd.DataFrame: A DataFrame containing flattened data from all JSON files in the zip.

    Raises:
        Exception: Logs an error message if an exception occurs during the process.

    Examples::

        >>> df = json_dumper("data.zip")
        >>> print(df.head())
    """
    out = pd.DataFrame()
    datapoints = []

    try:
        with zipfile.ZipFile(zfile, "r") as zf:
            for f in zf.namelist():
                content_logger.debug("Contained in zip: %s", f)
                fp = Path(f)
                if fp.suffix == ".json":
                    b = io.BytesIO(zf.read(f))
                    d = dict_denester(read_json_from_bytes(b))
                    for k, v in d.items():
                        datapoints.append({
                            "file name": fp.name, 
                            "key": k,
                            "value": v
                        })

        out = pd.DataFrame(datapoints)

    except Exception as e:
        logger.error("Exception was caught:  %s", e)

    return out


def fix_ascii_string(input: str) -> str:
    """
    Fixes the string encoding by removing non-ASCII characters.

    Args:
        input (str): The input string that needs to be fixed.

    Returns:
        str: The fixed string with only ASCII characters, or the original string if an exception occurs.

    Examples::

        >>> fix_ascii_string("Hello, 世界!")
        "Hello, !"
    """
    try:
        fixed_string = input.encode("ascii", 'ignore').decode()
        return fixed_string
    except Exception:
        return input


def replace_months(input_string: str) -> str:
    """
    Replaces Dutch month abbreviations with English equivalents in the input string.

    Args:
        input_string (str): The input string containing potential Dutch month abbreviations.

    Returns:
        str: The input string with Dutch month abbreviations replaced by English equivalents.

    Examples::

        >>> replace_months("15 mei 2023")
        "15 may 2023"
    """

    month_mapping = {
        'mrt': 'mar',
        'mei': 'may',
        'okt': 'oct',
    }

    for dutch_month, english_month in month_mapping.items():
        if dutch_month in input_string:
            replaced_string = input_string.replace(dutch_month, english_month, 1)
            return replaced_string

    return input_string


#: The shape every extracted timestamp is written in: ``2026-06-15 20:30:41``. Numbers
#: throughout, no month abbreviations, so the column reads the same whatever language the
#: donated export was written in. ``as.POSIXct`` in R and ``pandas.to_datetime`` both read
#: it without being told a format, and it sorts correctly as plain text.
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

#: The reference frame those timestamps are expressed in.
#:
#: Instagram's json export records an absolute instant and its html export names no
#: timezone at all; expressing both in one named zone is what makes the column comparable
#: across a participant's json and html donations of the same account.
#:
#: What this frame is *not* is the time the participant's own watch showed. An epoch
#: timestamp carries no location, so that information is not in the data and no conversion
#: can recover it.
REFERENCE_TIMEZONE = "Europe/Amsterdam"

#: Memo for :func:`_reference_zone`. Resolved on first use, never at import time.
_REFERENCE_ZONE: tzinfo | None = None


def _reference_zone() -> tzinfo:
    """The reference zone, resolved once, or UTC when the runtime has no zone database.

    ``ZoneInfo`` reads the IANA database at call time, and a Pyodide build without the
    ``tzdata`` package has none to read. Resolving the zone at import time would turn that
    into an import error for every module that touches ``extraction_helpers`` — the whole
    port — so the lookup happens here, on first use, and a runtime that cannot answer it
    gets UTC and one local warning instead of a dead worker.

    Falling back shifts written timestamps by one or two hours; it does not lose them.
    """
    global _REFERENCE_ZONE
    if _REFERENCE_ZONE is None:
        try:
            _REFERENCE_ZONE = ZoneInfo(REFERENCE_TIMEZONE)
        except Exception:  # ZoneInfoNotFoundError, and whatever else a runtime raises
            logger.warning(
                "No timezone database for %s; writing timestamps in UTC instead",
                REFERENCE_TIMEZONE,
            )
            _REFERENCE_ZONE = timezone.utc
    return _REFERENCE_ZONE


#: A zone spelled out at the end of a timestamp rather than as an offset (``... 10:09:50
#: UTC``). Only the zero-offset names are listed, so anything else falls through to the
#: parser and is counted rather than guessed at.
NAMED_UTC = re.compile(r"[\s_]+(?:UTC|GMT)$", re.IGNORECASE)


def _to_reference(moment: datetime) -> str:
    """Write *moment*, an aware datetime, in ``REFERENCE_TIMEZONE`` and ``DATETIME_FORMAT``.

    The zone's rules come from ``zoneinfo``, the IANA database the standard library ships.
    A runtime carrying no database — a Pyodide build without ``tzdata`` — writes UTC
    instead; see :func:`_reference_zone`.
    """
    return moment.astimezone(_reference_zone()).strftime(DATETIME_FORMAT)


def resolve_timezone(name: str | None) -> ZoneInfo | None:
    """The IANA zone *name* names (``Europe/London``), or ``None`` when it names nothing
    the database knows — the caller decides whether that is worth counting."""
    if not name:
        return None
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return None


def zone_time_to_datetime_string(moment: datetime, zone: "str | ZoneInfo", errors: Counter | None = None) -> str:
    """Convert a local wall-clock time in an IANA zone to ``DATETIME_FORMAT`` in
    ``REFERENCE_TIMEZONE``.

    Used where an export names the zone its clock stands in rather than an offset. The
    zone's own daylight-saving rules apply for the record's date.

    Args:
        moment: A naive datetime holding the local wall-clock time.
        zone: The zone's IANA name, or a zone already resolved by ``resolve_timezone``.
        errors: Optional counter; a zone the database does not know is counted as
            ``TimezoneUnknown`` and the wall time written as it stands.
    """
    tz = resolve_timezone(zone) if isinstance(zone, str) else zone
    if tz is None:
        if errors is not None:
            errors["TimezoneUnknown"] += 1
        return moment.strftime(DATETIME_FORMAT)
    return _to_reference(moment.replace(tzinfo=tz))


def epoch_to_datetime_string(epoch_timestamp: str | int | float, errors: Counter | None = None) -> str:
    """Convert epoch seconds to ``DATETIME_FORMAT`` in ``REFERENCE_TIMEZONE``.

    Epoch seconds name an absolute instant, so this conversion is exact — nothing about
    the participant has to be assumed. Used for the Instagram json export.

    Args:
        epoch_timestamp: Seconds since the epoch, as a number or a string holding one.
        errors: Optional counter that aggregates error types.

    Returns:
        str: The formatted timestamp, ``""`` for an absent one, or the input unchanged
        when it cannot be read as a number.

    Examples::

        >>> epoch_to_datetime_string(1632139200)
        "2021-09-20 14:00:00"
    """
    # Empty/falsy timestamps are expected absences, not errors
    if not epoch_timestamp and epoch_timestamp != 0:
        return ""

    out = str(epoch_timestamp)
    try:
        moment = datetime.fromtimestamp(int(float(epoch_timestamp)), tz=timezone.utc)
        out = _to_reference(moment)
    except (OverflowError, OSError, ValueError, TypeError) as e:
        logger.error("Could not convert epoch timestamp, %s", e)
        if errors is not None:
            errors["TimestampParseError"] += 1

    return out


def utc_timestamp_to_datetime_string(timestamp: str, errors: Counter | None = None) -> str:
    """Convert a timestamp string to ``DATETIME_FORMAT`` in ``REFERENCE_TIMEZONE``.

    Reads what the platform wrote about the zone and honours it: a trailing ``Z`` or an
    offset names the instant exactly, and so does a zone spelled out in full (``...
    10:09:50 UTC``).

    A timestamp carrying no zone at all is taken for UTC.

    Note that a naive timestamp is *always* read as UTC, so this must not be called on a
    value it has already converted.

    Args:
        timestamp: An ISO 8601 timestamp, with or without a zone.
        errors: Optional counter that aggregates error types.

    Returns:
        str: The formatted timestamp, ``""`` for an absent one, or the input unchanged
        when it cannot be read.

    Examples::

        >>> utc_timestamp_to_datetime_string("2021-09-20T12:00:00.123Z")
        "2021-09-20 14:00:00"
        >>> utc_timestamp_to_datetime_string("2021-09-20 12:00:00 UTC")
        "2021-09-20 14:00:00"
        >>> utc_timestamp_to_datetime_string("2021-09-20 12:00:00")
        "2021-09-20 14:00:00"
    """
    if not timestamp or not isinstance(timestamp, str):
        return ""

    # A zone written as a name carries no offset for the parser to read, so it is dropped
    # here; the zero-offset names it matches mean the same as the UTC default below.
    text = NAMED_UTC.sub("", timestamp.strip())

    try:
        # Python reads the trailing Z itself from 3.11 on, but the exports are not
        # consistent about upper case and this keeps the parse independent of that.
        moment = datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
    except (ValueError, TypeError) as e:
        logger.error("Could not convert timestamp, %s", e)
        if errors is not None:
            errors["TimestampParseError"] += 1
        return timestamp

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    return _to_reference(moment)


def local_time_to_datetime_string(
    moment: datetime, utc_offset: timedelta, errors: Counter | None = None
) -> str:
    """Convert a local wall-clock time to ``DATETIME_FORMAT`` in ``REFERENCE_TIMEZONE``.

    Used for the Instagram html export, which names no timezone but is rendered at a fixed
    offset from UTC. Knowing that offset is what makes the record comparable with the json
    export, which writes an absolute instant.

    Args:
        moment: A naive datetime holding the local wall-clock time.
        utc_offset: How far that local time stands ahead of UTC.
        errors: Optional counter that aggregates error types.

    Returns:
        str: The formatted timestamp.
    """
    try:
        return _to_reference(moment.replace(tzinfo=timezone(utc_offset)))
    except (OverflowError, ValueError, TypeError) as e:
        logger.error("Could not convert local timestamp, %s", e)
        if errors is not None:
            errors["TimestampParseError"] += 1
        return moment.strftime(DATETIME_FORMAT)


def epoch_to_iso(epoch_timestamp: str | int | float, errors: Counter | None = None) -> str:
    """
    Convert epoch timestamp to an ISO 8601 string, assuming UTC.

    Used by callers that have not been moved onto ``DATETIME_FORMAT``; new code should
    call ``epoch_to_datetime_string`` instead.

    Args:
        epoch_timestamp (str | int): The epoch timestamp to convert.

    Returns:
        str: The ISO 8601 formatted string, or the original input if conversion fails.

    Raises:
        Exception: Logs an error message if conversion fails.

    Examples::

        >>> epoch_to_iso(1632139200)
        "2021-09-20T12:00:00+00:00"
    """
    # Empty/falsy timestamps are expected absences, not errors
    if not epoch_timestamp and epoch_timestamp != 0:
        return ""

    out = str(epoch_timestamp)
    try:
        epoch_timestamp = int(float(epoch_timestamp))
        out = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError, TypeError) as e:
        logger.error("Could not convert epoch time timestamp, %s", e)
        if errors is not None:
            errors["TimestampParseError"] += 1

    return out


#: Months by the first three letters of how the Meta html exports abbreviate them,
#: lowercased, across the languages they are written in that use Latin script. An
#: account writes its export in whatever language it is set to, which is not always the
#: language of the study.
META_HTML_MONTHS = {
    "jan": 1, "oca": 1, "ene": 1,
    "feb": 2, "şub": 2, "sub": 2,
    "mar": 3, "mrt": 3, "mär": 3, "mrz": 3,
    "apr": 4, "nis": 4, "abr": 4,
    "may": 5, "mei": 5, "mai": 5,
    "jun": 6, "haz": 6,
    "jul": 7, "tem": 7,
    "aug": 8, "ağu": 8, "agu": 8, "ago": 8,
    "sep": 9, "eyl": 9, "set": 9,
    "oct": 10, "okt": 10, "eki": 10,
    "nov": 11, "kas": 11,
    "dec": 12, "dez": 12, "ara": 12, "dic": 12,
}

#: ``Jun 26, 2026 9:05:20 am`` — how the Facebook and Instagram html exports write a
#: timestamp: the month as a word, a 12-hour clock in lower case, the seconds usually
#: included. The meridiem and the seconds are optional so that a 24-hour locale and
#: Instagram's minute-precision stamps read too. No zone is written beside it.
META_HTML_TIMESTAMP = re.compile(
    r"^([^\s\d]+)\.?\s+(\d{1,2}),?\s+(\d{4})[\s,]+(\d{1,2}):(\d{2})(?::(\d{2}))?"
    r"(?:\s*([AaPp])\.?[Mm]\.?)?\s*$"
)


def parse_meta_html_timestamp(text: str) -> datetime | None:
    """Read a Meta html display timestamp into a naive ``datetime``, or ``None``.

    The clock it stands on is the caller's business: Instagram renders at a fixed
    offset, Facebook in the timezone of the account. A regex rather than
    ``strptime`` — an order of magnitude faster, and Pyodide is slow."""
    if not text or not isinstance(text, str):
        return None
    match = META_HTML_TIMESTAMP.match(text.strip())
    if not match:
        return None
    month, day, year, hour, minute, second, meridiem = match.groups()
    number = META_HTML_MONTHS.get(month[:3].lower())
    if number is None:
        return None
    hour = int(hour)
    if meridiem:
        # A 12-hour clock counts noon as 12 pm and midnight as 12 am.
        hour = hour % 12 + (12 if meridiem.lower() == "p" else 0)
    try:
        return datetime(int(year), number, int(day), hour, int(minute), int(second or 0))
    except ValueError:
        return None


def meta_html_timestamp_to_datetime_string(text: str, errors: Counter | None = None) -> str:
    """Write a Meta html display timestamp in ``DATETIME_FORMAT``, the clock left as is.

    Same contract as ``epoch_to_iso``: an empty cell is an expected absence and returns
    ``""`` without counting; text of any other shape is returned unchanged and counted as
    ``TimestampParseError``. Only the shape changes here — the export names no zone, so a
    caller that knows the clock converts the parsed ``datetime`` itself.

    Examples::

        >>> meta_html_timestamp_to_datetime_string("Mar 02, 2026 4:57:45 pm")
        "2026-03-02 16:57:45"
    """
    if not text:
        return ""
    moment = parse_meta_html_timestamp(text)
    if moment is not None:
        return moment.strftime(DATETIME_FORMAT)
    # The value itself is not logged: a cell that failed to parse is still participant data.
    logger.error("Could not read a Meta html timestamp")
    if errors is not None:
        errors["TimestampParseError"] += 1
    return text


def sort_isotimestamp_empty_timestamp_last(timestamp_series: pd.Series) -> pd.Series:
    """
    Creates a key for sorting a pandas Series of ISO timestamps, placing empty timestamps last.

    Args:
        timestamp_series (pd.Series): A pandas Series containing ISO formatted timestamps.

    Returns:
        pd.Series: A Series of sorting keys, with -timestamp for valid dates and infinity for invalid/empty dates.

    Examples::

        >>> df = df.sort_values(by="Date", key=sort_isotimestamp_empty_timestamp_last)
    """
    def convert_timestamp(timestamp):

        out = np.inf
        try:
            if isinstance(timestamp, str) and len(timestamp) > 0:
                dt = datetime.fromisoformat(timestamp)
                out = -dt.timestamp()
        except Exception as e:
            logger.debug("Cannot convert timestamp: %s", e)

        return out

    return timestamp_series.apply(convert_timestamp)


def fix_latin1_string(input: str) -> str:
    """
    Fixes the string encoding by attempting to encode it using the 'latin1' encoding and then decoding it.

    Args:
        input (str): The input string that needs to be fixed.

    Returns:
        str: The fixed string after encoding and decoding, or the original string if an exception occurs.

    Examples::

        >>> fix_latin1_string("café")
        "café"
    """
    try:
        fixed_string = input.encode("latin1").decode()
        return fixed_string
    except Exception:
        return input


class FileNotFoundInZipError(Exception):
    """
    The File you are looking for is not present in a zipfile
    """


def extract_file_from_zip(zfile: str, file_to_extract: str, errors: Counter | None = None) -> io.BytesIO:
    """
    Extracts a specific file from a zipfile and returns it as a BytesIO buffer.

    Args:
        zfile (str): Path to the zip file.
        file_to_extract (str): Name or path of the file to extract from the zip.
        errors (Counter | None): Optional counter for aggregating error types.

    Returns:
        io.BytesIO: A BytesIO buffer containing the extracted file's content of the first file found.
                    Returns an empty BytesIO if the file is not found or an error occurs.
    """

    file_to_extract_bytes = io.BytesIO()

    try:
        with zipfile.ZipFile(zfile, "r") as zf:
            file_found = False

            for f in zf.namelist():
                content_logger.debug("Contained in zip: %s", f)
                if re.match(rf"^.*{re.escape(file_to_extract)}$", f):
                    file_to_extract_bytes = io.BytesIO(zf.read(f))
                    file_found = True
                    break

        if not file_found:
            raise FileNotFoundInZipError("File not found in zip")

    except zipfile.BadZipFile as e:
        logger.error("BadZipFile:  %s", e)
        if errors is not None:
            errors["BadZipFile"] += 1
    except FileNotFoundInZipError as e:
        logger.error("File not found:  %s: %s", file_to_extract, e)
        if errors is not None:
            errors["FileNotFoundInZipError"] += 1
    except Exception as e:
        logger.error("Exception was caught:  %s", e)
        if errors is not None:
            errors["Exception"] += 1

    return file_to_extract_bytes


def _json_reader_bytes(json_bytes: bytes, encoding: str) -> Any:
    """
    Reads JSON data from bytes using the specified encoding.
    This function should not be used directly.

    Args:
        json_bytes (bytes): The JSON data in bytes.
        encoding (str): The encoding to use for decoding the bytes.

    Returns:
        Any: The parsed JSON data.

    Examples:
        >>> data = _json_reader_bytes(b'{"key": "value"}', "utf-8")
        >>> print(data)
        {'key': 'value'}
    """
    json_str = json_bytes.decode(encoding)
    result = json.loads(json_str)
    return result


def _json_reader_file(json_file: str, encoding: str) -> Any:
    """
    Reads JSON data from a file using the specified encoding.
    This function should not be used directly.

    Args:
        json_file (str): Path to the JSON file.
        encoding (str): The encoding to use for reading the file.

    Returns:
        Any: The parsed JSON data.

    Examples::

        >>> data = _json_reader_file("data.json", "utf-8")
        >>> print(data)
        {'key': 'value'}
    """
    with open(json_file, 'r', encoding=encoding) as f:
        result = json.load(f)
    return result


def _read_json(json_input: Any, json_reader: Callable[[Any, str], Any], errors: Counter | None = None) -> dict[Any, Any] | list[Any]:
    """
    Reads JSON input using the provided json_reader function, trying different encodings.
    This function should not be used directly.

    Args:
        json_input (Any): The JSON input (can be bytes or file path).
        json_reader (Callable[[Any, str], Any]): A function to read the JSON input.
        errors (Counter | None): Optional counter for aggregating error types.

    Returns:
        dict[Any, Any] | list[Any]: The parsed JSON data as a dictionary or list.
                                    Returns an empty dictionary if parsing fails.
    """

    out: dict[Any, Any] | list[Any] = {}

    encodings = ["utf8", "utf-8-sig"]
    for encoding in encodings:
        try:
            result = json_reader(json_input, encoding)

            if not isinstance(result, (dict, list)):
                raise TypeError("Did not convert bytes to a list or dict, but to another type instead")

            out = result
            logger.debug("Succesfully converted json bytes with encoding: %s", encoding)
            break

        except json.JSONDecodeError:
            logger.error("Cannot decode json with encoding: %s", encoding)
            if errors is not None:
                errors["JSONDecodeError"] += 1
        except TypeError as e:
            logger.error("%s, could not convert json bytes", e)
            if errors is not None:
                errors["TypeError"] += 1
            break
        except Exception as e:
            logger.error("%s, could not convert json bytes", e)
            if errors is not None:
                errors["Exception"] += 1
            break

    return out


def read_json_from_bytes(json_bytes: io.BytesIO, errors: Counter | None = None) -> dict[Any, Any] | list[Any]:
    """
    Reads JSON data from a BytesIO buffer.

    Args:
        json_bytes (io.BytesIO): A BytesIO buffer containing JSON data.

    Returns:
        dict[Any, Any] | list[Any]: The parsed JSON data as a dictionary or list.
                                    Returns an empty dictionary if parsing fails.

    Examples::

        >>> buffer = io.BytesIO(b'{"key": "value"}')
        >>> data = read_json_from_bytes(buffer)
        >>> print(data)
        {'key': 'value'}
    """
    out: dict[Any, Any] | list[Any] = {}
    try:
        b = json_bytes.read()
        if not b:
            return out  # empty bytes → empty result, no parse attempt
        out = _read_json(b, _json_reader_bytes, errors=errors)
    except Exception as e:
        logger.error("%s, could not convert json bytes", e)
        if errors is not None:
            errors["Exception"] += 1

    return out


def read_json_from_file(json_file: str) -> dict[Any, Any] | list[Any]:
    """
    Reads JSON data from a file.

    Args:
        json_file (str): Path to the JSON file.

    Returns:
        dict[Any, Any] | list[Any]: The parsed JSON data as a dictionary or list.
                                    Returns an empty dictionary if parsing fails.

    Examples::

        >>> data = read_json_from_file("data.json")
        >>> print(data)
        {'key': 'value'}
    """
    out = _read_json(json_file, _json_reader_file)
    return out


def read_csv_from_bytes(json_bytes: io.BytesIO, errors: Counter | None = None) -> list[dict[Any, Any]]:
    """
    Reads CSV data from a BytesIO buffer and returns it as a list of dictionaries.

    Args:
        json_bytes (io.BytesIO): A BytesIO buffer containing CSV data.
        errors (Counter | None): Optional counter for aggregating error types.

    Returns:
        list[dict[Any, Any]]: A list of dictionaries, where each dictionary represents a row in the CSV.
                              Returns an empty list if parsing fails.
    """
    out: list[dict[Any, Any]] = []

    try:
        stream = io.TextIOWrapper(json_bytes, encoding="utf-8")
        reader = csv.DictReader(stream)
        for row in reader:
            out.append(row)
        logger.debug("succesfully converted csv bytes with encoding utf8")

    except Exception as e:
        logger.error("%s, could not convert csv bytes", e)
        if errors is not None:
            errors["CSVDecodeError"] += 1

    return out


def read_csv_from_bytes_to_df(json_bytes: io.BytesIO) -> pd.DataFrame:
    """
    Reads CSV data from a BytesIO buffer and returns it as a pandas DataFrame.

    Args:
        json_bytes (io.BytesIO): A BytesIO buffer containing CSV data.

    Returns:
        pd.DataFrame: A pandas DataFrame containing the CSV data.

    Examples:

        >>> buffer = io.BytesIO(b'name,age\\nAlice,30\\nBob,25')
        >>> df = read_csv_from_bytes_to_df(buffer)
        >>> print(df)
           name  age
        0  Alice   30
        1    Bob   25
    """
    return pd.DataFrame(read_csv_from_bytes(json_bytes))


def xpath_nodes(node: Any, expression: str) -> list[Any]:
    """Run an XPath query and return its node list.

    lxml's ``xpath`` is typed as a union (a query can also yield a string, a
    number or a boolean); every caller here iterates over element results, so a
    non-list result is treated as "no matches" rather than raised.
    """
    result = node.xpath(expression)
    return result if isinstance(result, list) else []


# --- Result types for ZipArchiveReader ---

@dataclass
class JsonExtractionResult:
    """Result of extracting and parsing a JSON file from a zip."""
    found: bool
    data: dict | list  # {} when not found
    member_path: str | None = None


@dataclass
class CsvExtractionResult:
    """Result of extracting and parsing a CSV file from a zip."""
    found: bool
    data: pd.DataFrame  # empty DataFrame when not found
    member_path: str | None = None


@dataclass
class RawExtractionResult:
    """Result of extracting raw bytes from a zip."""
    found: bool
    data: io.BytesIO  # empty BytesIO when not found
    member_path: str | None = None


class ZipArchiveReader:
    """Reads files from a zip archive using cached member inventory.

    Encapsulates a seekable binary archive (`SeekableBinaryReader`),
    archive member list (from validation), and error counter. Provides
    json()/csv()/raw() methods with found/not-found signaling to
    eliminate cascading errors for expected-missing files.

    Per ADR-0026, the upload pipeline passes the
    `AsyncFileAdapter` from a browser upload here directly so the zip
    is never materialized into Pyodide's heap. Path-string inputs are
    not accepted; tests construct fixtures via `io.BytesIO`.

    Usage:
        reader = ZipArchiveReader(archive, validation.archive_members, errors)
        result = reader.json("following.json")
        if result.found:
            data = result.data  # parsed dict/list
    """

    def __init__(
        self,
        archive: SeekableBinaryReader | ArchiveSource,
        archive_members: list[str],
        errors: Counter,
    ):
        self.archive = archive
        self.archive_members = archive_members
        self.errors = errors
        self._source: ArchiveSource = (
            archive if isinstance(archive, ArchiveSource) else SingleArchiveSource(archive, archive_members)
        )
        duplicates = getattr(archive, "duplicates", None)
        if duplicates is not None:
            errors.update(duplicates)

    def resolve_member(self, filename: str) -> str | None:
        """Resolve a filename to an archive member path.

        Resolution rule:
        1. Exact path match → use it.
        2. Path-boundary suffix match (member.endswith("/" + filename)) →
           if exactly 1, use it.
        3. 0 matches → return None.
        4. Multiple matches → return None, log warning,
           increment errors["AmbiguousMemberMatch(<filename>)"].

        Both steps also try the requested name with every apostrophe replaced
        by an underscore: Meta exports delivered through Google Drive write
        ``who_you_ve_followed.json`` where device downloads write
        ``who_you've_followed.json``. That is one substitution on the request,
        never a fuzzy match — two members differing only in that spelling are
        still ambiguous.

        The counter key embeds the *requested* name (a code literal), never a
        member path from the archive: it reaches the host log.
        """
        candidates = [filename]
        if "'" in filename:
            candidates.append(filename.replace("'", "_"))

        # 1. Exact match
        for candidate in candidates:
            if candidate in self.archive_members:
                return candidate

        # 2. Path-boundary suffix match
        suffixes = tuple("/" + candidate for candidate in candidates)
        matches = [m for m in self.archive_members if m.endswith(suffixes)]

        if len(matches) == 1:
            return matches[0]
        elif len(matches) == 0:
            return None
        else:
            logger.warning(
                "Ambiguous member match: '%s' matched %d members in archive",
                filename, len(matches),
            )
            self.errors[f"AmbiguousMemberMatch({filename})"] += 1
            return None

    @contextmanager
    def open_member(self, filename: str) -> Iterator[IO[bytes] | None]:
        """Yields a binary stream for the resolved member, or None when the lookup
        fails — resolution and error counting mirror the buffered read paths."""
        member_path = self.resolve_member(filename)
        if member_path is None:
            yield None
            return
        with self._source.open_member(member_path) as stream:
            yield stream

    def _read_member_bytes(self, member_path: str) -> io.BytesIO:
        """Read a specific member via the archive source (single archive or
        ArchiveSet), by exact path."""
        try:
            return io.BytesIO(self._source.read_member(member_path))
        except Exception as e:
            logger.error("Error reading zip member: %s", type(e).__name__)
            self.errors[type(e).__name__] += 1
            return io.BytesIO()

    def json(self, filename: str) -> JsonExtractionResult:
        """Extract and parse a JSON file.

        Returns JsonExtractionResult(found=False, data={}) if member
        not in archive. Skips JSON parsing entirely when not found.
        """
        member = self.resolve_member(filename)
        if member is None:
            return JsonExtractionResult(found=False, data={})

        b = self._read_member_bytes(member)
        raw = b.read()
        if not raw:
            return JsonExtractionResult(found=True, data={}, member_path=member)

        # Call _read_json directly (intentional — avoids BytesIO re-wrapping)
        data = _read_json(raw, _json_reader_bytes, errors=self.errors)
        return JsonExtractionResult(found=True, data=data, member_path=member)

    def json_all(self, pattern: str) -> list[JsonExtractionResult]:
        """Extract and parse all JSON files matching a regex pattern.

        Returns results sorted lexicographically by member path.
        Used for paginated exports (post_comments_1.json, _2.json, etc.).
        """
        matches = sorted(m for m in self.archive_members if re.search(pattern, m))
        results = []
        for member in matches:
            b = self._read_member_bytes(member)
            raw = b.read()
            if not raw:
                results.append(JsonExtractionResult(found=True, data={}, member_path=member))
                continue
            data = _read_json(raw, _json_reader_bytes, errors=self.errors)
            results.append(JsonExtractionResult(found=True, data=data, member_path=member))
        return results

    def csv(self, filename: str) -> CsvExtractionResult:
        """Extract and parse a CSV file.

        Returns CsvExtractionResult(found=False, data=pd.DataFrame())
        if member not in archive.
        """
        member = self.resolve_member(filename)
        if member is None:
            return CsvExtractionResult(found=False, data=pd.DataFrame())

        b = self._read_member_bytes(member)
        if not b.getvalue():
            return CsvExtractionResult(found=True, data=pd.DataFrame(), member_path=member)

        df = read_csv_from_bytes_to_df(b)
        return CsvExtractionResult(found=True, data=df, member_path=member)

    def raw(self, filename: str) -> RawExtractionResult:
        """Extract raw bytes from a zip member.

        Returns RawExtractionResult(found=False, data=io.BytesIO())
        if member not in archive. Used for HTML (Chrome bookmarks),
        text files (WhatsApp, TikTok), and .js files (X — caller applies
        bytesio_to_listdict for JS prefix stripping).
        """
        member = self.resolve_member(filename)
        if member is None:
            return RawExtractionResult(found=False, data=io.BytesIO())

        b = self._read_member_bytes(member)
        return RawExtractionResult(found=True, data=b, member_path=member)

    def raw_all(self, pattern: str) -> list[RawExtractionResult]:
        """Extract raw bytes from all zip members matching a regex pattern.

        Returns results sorted lexicographically by member path. Used for
        paginated HTML exports (post_comments_1.html, _2.html, etc.). Every
        member is read through ``_read_member_bytes`` so the member-size guard
        and error counting apply exactly as for ``raw()``.
        """
        matches = sorted(m for m in self.archive_members if re.search(pattern, m))
        results = []
        for member in matches:
            b = self._read_member_bytes(member)
            results.append(RawExtractionResult(found=True, data=b, member_path=member))
        return results


# --- Study-side anonymization (algosoc-2026) ---
#
# Applied by a platform's ``extraction()`` after the tables are built. These
# helpers operate on nullable string columns so a missing cell stays missing
# instead of becoming the literal text "nan".

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def replace_email(text: str) -> str:
    """Replace email addresses in *text* with ``[email]``."""
    return EMAIL_PATTERN.sub("[email]", text)


def _username_pattern(username: str) -> re.Pattern[str]:
    """Whole-token, case-insensitive match for *username*.

    Anchored on both sides so a short username (initials, a two-letter
    nickname) never redacts the inside of an unrelated word.
    """
    return re.compile(rf"(?<!\w){re.escape(username)}(?!\w)", re.IGNORECASE)


def replace_username(text: str, username: str) -> str:
    """Replace whole-token, case-insensitive occurrences of *username* with ``[user]``."""
    return _username_pattern(username).sub("[user]", text)


def anonymize_dataframe(df: pd.DataFrame, columns: list[str], username: str | None = None) -> pd.DataFrame:
    """Anonymize text columns in a DataFrame, in place.

    Replaces email addresses and, when *username* is given, the user's name
    with placeholder tokens. Only columns that exist in *df* are touched.
    Missing values are preserved as missing. The frame is mutated and also
    returned for convenience.
    """
    for col in columns:
        if col not in df.columns:
            continue
        redacted = df[col].astype("string").str.replace(EMAIL_PATTERN, "[email]", regex=True)
        if username:
            redacted = redacted.str.replace(_username_pattern(username), "[user]", regex=True)
        df[col] = redacted
    return df


# --- Education helpers: anonymized structure overviews for the issue report ---
#
# Ported from the pre-rebase education fork (git show
# master:packages/python/port/helpers/extraction_helpers.py). Ported to accept
# a reader (or ArchiveSet, for multi-file/PayloadFiles platforms such as
# Google) rather than a path, per ADR-0026.


def _is_structure_member(member: str) -> bool:
    """True for the only members extract_file_structures_from_zip reads:
    JSON and CSV. Checked *before* any read — a real export's images,
    videos, and other binary members must never be pulled into memory just
    to be discarded (ADR-0026)."""
    lower = member.lower()
    return lower.endswith(".json") or lower.endswith(".csv")


#: Row caps for the structure overview. `dict_denester` flattens a JSON document to one
#: row per leaf, so a single export member — a year of messages in one file — flattens to
#: hundreds of thousands of rows, and a whole export to millions. The table is read by a
#: human looking for the *shape* of an export, and the issue report is uploaded, so both
#: the frame in memory and the payload on the wire have to stop somewhere. A few thousand
#: rows already show every distinct field name an export has.
MAX_STRUCTURE_ROWS_PER_MEMBER = 2000
MAX_STRUCTURE_ROWS_TOTAL = 20000

#: The `field_name` of the row that marks a cut, so a reader can tell a short table from a
#: truncated one. `<...>` brackets keep it from colliding with a real field name.
TRUNCATION_MARKER = "<truncated>"


def _truncation_row(member: str, count: int) -> dict[str, Any]:
    """The single row that marks a cut: `(member, "<truncated>", "<n more>")`.

    What *n* counts depends on which cap fired, and the two are told apart by where the
    row sits: after a member's own rows it is the fields of that member left unlisted;
    as the last row of the whole table it is the members left unread.
    """
    return {"filepath": member, "field_name": TRUNCATION_MARKER, "value": f"<{count} more>"}


def _structure_rows_for_member(member: str, raw: bytes, infer_types: bool) -> list[dict[str, Any]]:
    """Extract field-name/value rows for one JSON or CSV archive member.
    Caller must already have filtered to `_is_structure_member(member)`.

    If infer_types is True, values are replaced with their Python type
    names (used to anonymize the issue-report structure table).

    At most MAX_STRUCTURE_ROWS_PER_MEMBER rows come back, plus one
    `_truncation_row` naming how many fields were left out.
    """
    rows: list[dict[str, Any]] = []
    lower = member.lower()
    if lower.endswith(".json"):
        data = json.loads(raw.decode("utf-8-sig"))
        flat = dict_denester(data)
        for key, value in flat.items():
            if len(rows) >= MAX_STRUCTURE_ROWS_PER_MEMBER:
                rows.append(_truncation_row(member, len(flat) - MAX_STRUCTURE_ROWS_PER_MEMBER))
                break
            v = type(value).__name__ if infer_types else value
            rows.append({"filepath": member, "field_name": key, "value": v})
    elif lower.endswith(".csv"):
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        first_row = next(reader, None)
        if first_row:
            for key, value in first_row.items():
                if len(rows) >= MAX_STRUCTURE_ROWS_PER_MEMBER:
                    rows.append(_truncation_row(member, len(first_row) - MAX_STRUCTURE_ROWS_PER_MEMBER))
                    break
                v = type(value).__name__ if infer_types else value
                rows.append({"filepath": member, "field_name": key, "value": v})
    return rows


def extract_file_structures_from_zip(
    archive: SeekableBinaryReader | ArchiveSet, infer_types: bool = False
) -> pd.DataFrame:
    """Extract field names and optionally infer value types from all JSON/CSV
    files in a zip archive (a single reader) or an ArchiveSet (multiple
    uploaded parts, e.g. Google Takeout).

    Only `.json`/`.csv` members are ever read — every other member (images,
    videos, ...) is skipped by name before any bytes are pulled, so a real
    export's large binary members are never read just to be discarded.

    Each member contributes at most MAX_STRUCTURE_ROWS_PER_MEMBER rows and the whole call
    at most MAX_STRUCTURE_ROWS_TOTAL. Reaching the total stops the scan — the remaining
    members are not read at all, and one `_truncation_row` says how many they were.

    Returns a DataFrame with columns: filepath, field_name, value.
    If infer_types is True, values are replaced with their Python type names.
    """
    results: list[dict[str, Any]] = []

    def scan(members: list[str], read: Callable[[str], bytes | None], where: str) -> None:
        """Read each structure member in *members* until the total row cap is reached.

        *read* returns None for a member it declined to read and has already logged.
        """
        for position, member in enumerate(members):
            if len(results) >= MAX_STRUCTURE_ROWS_TOTAL:
                results.append(_truncation_row(member, len(members) - position))
                logger.warning(
                    "Structure overview capped at %d rows; %d of %d members left unread",
                    MAX_STRUCTURE_ROWS_TOTAL, len(members) - position, len(members),
                )
                return
            if not _is_structure_member(member):
                continue
            try:
                raw = read(member)
                if raw is None:
                    continue
                results.extend(_structure_rows_for_member(member, raw, infer_types))
            except Exception:
                logger.warning("Could not process %s in %s", member, where)

    try:
        if isinstance(archive, ArchiveSet):
            # archive.members already excludes macOS metadata
            scan(archive.members, archive.read_member, "archive set")
        else:
            archive.seek(0)
            with zipfile.ZipFile(archive, "r") as zf:
                def read_guarded(member: str) -> bytes | None:
                    info = zf.getinfo(member)
                    if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
                        logger.warning(
                            "Skipping oversize member %s (%d bytes exceeds %d cap)",
                            member, info.file_size, MAX_MEMBER_UNCOMPRESSED_BYTES,
                        )
                        return None
                    return zf.read(member)

                members = [m for m in zf.namelist() if not is_macos_metadata(m)]
                scan(members, read_guarded, "zip")
    except zipfile.BadZipFile:
        logger.warning("Bad zip file")

    return pd.DataFrame(results) if results else pd.DataFrame(columns=["filepath", "field_name", "value"])


#: What a redacted path segment is written as. Two placeholders rather than one, so a
#: reader can still tell a folder from the file at the end of the path.
REDACTED_DIR = "<dir>"
REDACTED_FILE = "<file>"


def redact_member_path(path: str) -> str:
    """Reduce an archive member path to its shape: top-level folder, depth, extension.

    Export archives name folders and files after people — ``messages/inbox/jane_doe_17``,
    a contact's name as a filename — so a full member path is participant data even when
    every value inside the file has been replaced by its type. What a bug report actually
    needs from a path is none of that: which top-level section the file sits in, how deep
    it is, and what kind of file it is.

    Every segment below the top level becomes ``<dir>`` and the leaf name becomes
    ``<file>``, keeping its extension::

        >>> redact_member_path("messages/inbox/name_123/message_1.json")
        'messages/<dir>/<dir>/<file>.json'

    The top-level folder is kept because it names the export section rather than a person.
    """
    if not path:
        return path

    is_dir = path.endswith("/")
    segments = [segment for segment in path.rstrip("/").split("/") if segment]
    if not segments:
        return path

    if is_dir:
        leaf = REDACTED_DIR
    else:
        stem, dot, extension = segments[-1].rpartition(".")
        leaf = f"{REDACTED_FILE}.{extension}" if dot and stem else REDACTED_FILE

    if len(segments) == 1:
        redacted = [leaf]
    else:
        redacted = [segments[0]] + [REDACTED_DIR] * (len(segments) - 2) + [leaf]

    return "/".join(redacted) + ("/" if is_dir else "")


def extract_zip_file_info(archive: SeekableBinaryReader | ArchiveSet) -> pd.DataFrame:
    """Extract metadata for all files in a zip archive (a single reader) or
    an ArchiveSet (multiple uploaded parts, e.g. Google Takeout).

    Returns a DataFrame with columns: file_path, modified_time, file_size, mime_type.
    Uses mimetypes stdlib for MIME detection (safe for Pyodide).
    """
    import mimetypes

    def _row(filename: str, file_size: int, date_time: tuple[int, ...], is_dir: bool) -> dict[str, Any] | None:
        if is_dir:
            return None
        mime, _ = mimetypes.guess_type(filename)
        return {
            "file_path": filename,
            "modified_time": "{:04d}-{:02d}-{:02d} {:02d}:{:02d}".format(*date_time[:5]),
            "file_size": file_size,
            "mime_type": mime or "unknown",
        }

    results: list[dict[str, Any]] = []
    try:
        if isinstance(archive, ArchiveSet):
            for member in archive.members:  # already excludes macOS metadata
                info = archive.member_info(member)
                row = _row(info.filename, info.file_size, info.date_time, info.is_dir())
                if row is not None:
                    results.append(row)
        else:
            archive.seek(0)
            with zipfile.ZipFile(archive, "r") as zf:
                for info in zf.infolist():
                    if is_macos_metadata(info.filename):
                        continue
                    row = _row(info.filename, info.file_size, info.date_time, info.is_dir())
                    if row is not None:
                        results.append(row)
    except zipfile.BadZipFile:
        logger.warning("Bad zip file")

    return pd.DataFrame(results) if results else pd.DataFrame(
        columns=["file_path", "modified_time", "file_size", "mime_type"]
    )
