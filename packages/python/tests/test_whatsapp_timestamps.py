import io
import zipfile

import pytest
from port.platforms import whatsapp as W

LINES = [
    ("22-07-2023 6:50 ’s avonds - Sam Voorbeeld: Hey", "2023-07-22T18:50:00", "Sam Voorbeeld"),
    ("22-07-2023 7:15 ’s ochtends - Sam Voorbeeld: Hey", "2023-07-22T07:15:00", "Sam Voorbeeld"),
    ("22-07-2023 12:05 ’s middags - Sam Voorbeeld: Hey", "2023-07-22T12:05:00", "Sam Voorbeeld"),
    ("22-07-2023 12:30 ’s nachts - Sam Voorbeeld: Hey", "2023-07-22T00:30:00", "Sam Voorbeeld"),
    ("22-07-2023 3:00 ’s middags - Sam Voorbeeld: Hey", "2023-07-22T15:00:00", "Sam Voorbeeld"),
    ("[22/07/2023, 6:50:12 PM] Example User: Hey", "2023-07-22T18:50:00", "Example User"),
    ("22/07/2023, 18:50 - Example User: Hey", "2023-07-22T18:50:00", "Example User"),
]


@pytest.mark.parametrize("line,iso,name", LINES)
def test_line_parses_with_correct_hour(line, iso, name):
    regexes = W.generate_regexes(W.SIMPLIFIED_REGEXES)
    for r in regexes:
        dp = W.create_data_point_from_chat(line, r)
        if dp["name"]:
            break
    assert dp["name"] == name
    assert dp["date"].startswith(iso[:16]), dp["date"]


@pytest.mark.parametrize("hour,ampm,daypart,expected", [
    (6, None, "’s avonds", 18), (12, None, "’s middags", 12), (12, None, "’s nachts", 0),
    (6, "PM", None, 18), (12, "AM", None, 0), (18, None, None, 18),
])
def test_to_24h(hour, ampm, daypart, expected):
    assert W.to_24h(hour, ampm, daypart) == expected


CHAT = "22-07-2023 6:50 ’s avonds - Sam Voorbeeld: Hey\n22-07-2023 7:15 ’s avonds - Example User: Hey love\n"


def test_parse_chat_reads_bare_txt_reader():
    df = W.parse_chat(io.BytesIO(CHAT.encode("utf-8")))
    assert list(df["name"]) == ["Sam Voorbeeld", "Example User"]


def test_parse_chat_reads_zip_reader():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("WhatsApp-chat.txt", CHAT)
    buf.seek(0)
    assert len(W.parse_chat(buf)) == 2


def test_file_prompt_accepts_zip_and_text():
    prompt = W.WhatsAppFlow("s").generate_file_prompt()
    assert "application/zip" in prompt.extensions and "text/plain" in prompt.extensions
