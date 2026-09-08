"""
ChatGPT

This module provides an example flow of a ChatGPT data donation study

Assumptions:
It handles DDPs in the english language with filetype JSON.

Configuration
-------------
The ``extraction`` function is driven by ``port_config.json``.  Generate one with::

    pnpm generate-config chatgpt

Each extractor function carries its own table config in a ``Table config::``
JSON block inside its docstring.  The generator reads those blocks and
assembles the JSON file.

Platform info::

    {
        "name": "ChatGPT",
        "filetypes": ["json"],
        "languages": ["en", "nl"],
        "description": "Handles DDPs in English. These data donation flows have not been tested yet, if you find anything wrong with them report to datadonation@uu.nl and they will be fixed!",
        "time_last_tested": "not yet implemented"
    }
"""
import logging
from collections import Counter
from datetime import datetime
from typing import Callable
from weakref import WeakKeyDictionary

import pandas as pd

import port.helpers.extraction_helpers as eh
import port.helpers.validate as validate
from port.helpers.extraction_helpers import ZipArchiveReader
from port.helpers.flow_builder import FlowBuilder

from port.helpers.validate import (
    DDPCategory,
    DDPFiletype,
    Language,
)
from port.api.d3i_props import ExtractionResult
from port.api.file_utils import SeekableBinaryReader
from port.helpers.table_extractor import (
    load_port_config,
    run_extraction,
)

logger = logging.getLogger(__name__)

DDP_CATEGORIES = [
    DDPCategory(
        id="json",
        ddp_filetype=DDPFiletype.JSON,
        language=Language.EN,
        known_files=[
            "chat.html",
            "conversations-000.json",
            "message_feedback.json",
            "model_comparisons.json",
            "user.json"
        ]
    )
]


def account_info_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract the account-identifying fields OpenAI keeps in ``user.json``.

    ``user.json`` is a flat, four-field object: whether the account is a
    ChatGPT Plus subscriber, the account id, and the email and phone number
    on file. Present but empty (0 bytes, or an empty JSON object) is treated
    the same as absent (ADR-0024): a real file with nothing in it must not
    surface as four blank-value rows.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Field``, ``Value``. One row per account field.
        Empty DataFrame when the file is absent, empty, or parsing fails.

    Table documentation::

        {
          "summary": "One row per account-identifying field OpenAI keeps on file for the account.",
          "source_file": "user.json",
          "columns": {
            "Field": "Name of the account field.",
            "Value": "Value OpenAI has on file for that field."
          }
        }

    Table config::

        {
          "id": "chatgpt_account_info",
          "title": {
            "en": "What OpenAI has on file for your account",
            "nl": "Wat OpenAI over uw account heeft vastgelegd"
          },
          "description": {
            "en": "The account fields OpenAI keeps for your ChatGPT account, from user.json.",
            "nl": "De accountgegevens die OpenAI voor uw ChatGPT-account bewaart, uit user.json."
          },
          "headers": {
            "Field": {"en": "Field", "nl": "Veld"},
            "Value": {"en": "Value", "nl": "Waarde"}
          }
        }
    """
    result = reader.json("user.json")
    out = pd.DataFrame()
    if not result.found or not isinstance(result.data, dict) or not result.data:
        return out
    try:
        data = result.data
        plus = data.get("chatgpt_plus_user")
        plus_value = "Yes" if plus is True else ("No" if plus is False else "")
        rows = [
            {"Field": "ChatGPT Plus subscriber", "Value": plus_value},
            {"Field": "Account ID", "Value": str(data.get("id") or "")},
            {"Field": "Email on file", "Value": str(data.get("email") or "")},
            {"Field": "Phone on file", "Value": str(data.get("phone_number") or "")},
        ]
        out = pd.DataFrame(rows)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


#: One parse per reader, shared by every extractor that needs the turns.
#:
#: ``conversations-*.json`` is the largest member of a ChatGPT export — the whole
#: conversation history — and two extractors in the same flow ask for the same turns.
#: Keyed weakly so a reader that goes out of scope takes its turns with it rather than
#: pinning a whole export's worth of dicts for the life of the process.
_TURNS_BY_READER: "WeakKeyDictionary[ZipArchiveReader, list[dict]]" = WeakKeyDictionary()


def _conversation_turns(reader: ZipArchiveReader, errors: Counter) -> list[dict]:
    """The visible message turns for *reader*, parsed once and then reused.

    The parse itself is :func:`_parse_conversation_turns`; this is the memo in front of
    it. A cached hit counts no errors, because the errors of the one parse were already
    counted into the ``errors`` of the call that did it.
    """
    turns = _TURNS_BY_READER.get(reader)
    if turns is None:
        turns = _parse_conversation_turns(reader, errors)
        _TURNS_BY_READER[reader] = turns
    return turns


def _parse_conversation_turns(reader: ZipArchiveReader, errors: Counter) -> list[dict]:
    """Shared traversal: one dict per visible message turn across every
    ``conversations-*.json`` file, feeding both ``conversations_to_df`` and
    ``models_used_to_df`` from the same parse.

    Every user turn's ``model`` is blank — ChatGPT only records the model
    slug on the assistant reply that used it (confirmed against the real
    export: 1508 of 3057 turns are user turns, all blank on ``model``; the
    remaining 1549 assistant turns are never blank). ``models_used_to_df``
    relies on this to select assistant turns only, rather than trying to
    read a model off a user turn.

    On any parse exception the whole result is thrown away (an empty list),
    matching the original ``conversations_to_df`` behaviour: no partial rows
    from a conversation half-read.

    Returns
    -------
    list[dict]
        Each dict has keys ``conversation title``, ``role``, ``message``,
        ``model``, ``time``. Empty list when no conversations file is found
        or parsing fails.
    """
    results = reader.json_all(r"conversations-.*\.json")
    if not results:
        return []
    conversations = [conv for result in results for conv in result.data]

    datapoints: list[dict] = []
    try:
        for conversation in conversations:
            title = conversation["title"]
            for _, turn in conversation["mapping"].items():

                denested_d = eh.dict_denester(turn)
                is_hidden = eh.find_item(denested_d, "is_visually_hidden_from_conversation")
                if is_hidden != "True":
                    role = eh.find_item(denested_d, "role")
                    message = "".join(eh.find_items(denested_d, "part"))
                    model = eh.find_item(denested_d, "-model_slug")
                    time = eh.epoch_to_iso(eh.find_item(denested_d, "create_time"), errors=errors)

                    datapoint = {
                        "conversation title": title,
                        "role": role,
                        "message": message,
                        "model": model,
                        "time": time,
                    }
                    if role != "":
                        datapoints.append(datapoint)
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
        return []

    return datapoints


def _parse_iso(value: str) -> "datetime | None":
    """``time`` / ``model`` cells are already-formatted output of
    ``eh.epoch_to_iso`` (or blank); parse defensively rather than trust that,
    the same way ``prepareHeatmapData.ts`` treats an unparseable date cell as
    absent instead of crashing the block."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def conversations_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract one row per ChatGPT conversation, aggregated from its turns.

    Groups the shared turn parse (``_conversation_turns``) by conversation
    title, preserving each conversation's first-appearance order in the
    export (not sorted by date or size). ``Models`` only ever looks at
    assistant turns — a user turn's ``model`` is always blank, see
    ``_conversation_turns`` — so it never contains an empty entry.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``Conversation title``, ``Started``, ``Last message``, ``Turns``, ``Models``.
        One row per conversation. Empty DataFrame when no conversations file
        is found or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one ChatGPT conversation: its title, when it started and last had a message, how many turns it has, and which AI models answered in it.",
          "source_file": "conversations files (conversations-000.json, conversations-001.json, ...)",
          "columns": {
            "Conversation title": "Title of the conversation as stored in the export.",
            "Started": "ISO 8601 timestamp of the conversation's earliest turn.",
            "Last message": "ISO 8601 timestamp of the conversation's latest turn.",
            "Turns": "Number of message turns (user and assistant) in the conversation.",
            "Models": "Comma-joined distinct ChatGPT model slugs that answered in this conversation."
          }
        }

    Table config::

        {
          "id": "chatgpt_conversations",
          "title": {
            "en": "Your conversations with ChatGPT",
            "nl": "Je gesprekken met ChatGPT"
          },
          "description": {
            "en": "One row per ChatGPT conversation, from the conversations export files.",
            "nl": "Eén rij per ChatGPT-gesprek, uit de conversations-exportbestanden."
          },
          "headers": {
            "Conversation title": {"en": "Conversation title", "nl": "Gesprektitel"},
            "Started": {"en": "Started", "nl": "Gestart"},
            "Last message": {"en": "Last message", "nl": "Laatste bericht"},
            "Turns": {"en": "Turns", "nl": "Beurten"},
            "Models": {"en": "Models", "nl": "Modellen"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Your ChatGPT use at a glance",
                "nl": "Je ChatGPT-gebruik in het kort"
              },
              "type": "stats",
              "tiles": [
                {"label": {"en": "Conversations", "nl": "Gesprekken"}, "aggregate": "count"},
                {"label": {"en": "First conversation", "nl": "Eerste gesprek"}, "aggregate": "first_date", "column": "Started"},
                {"label": {"en": "Last conversation", "nl": "Laatste gesprek"}, "aggregate": "last_date", "column": "Started"},
                {"label": {"en": "Busiest day", "nl": "Drukste dag"}, "aggregate": "busiest_day", "column": "Started"}
              ]
            },
            {
              "title": {"en": "Conversations started per month", "nl": "Gesprekken gestart per maand"},
              "type": "area",
              "group": {"column": "Started", "dateFormat": "month", "label": {"en": "Month", "nl": "Maand"}},
              "values": [{"aggregate": "count", "label": {"en": "Conversations", "nl": "Gesprekken"}}]
            }
          ]
        }
    """
    turns = _conversation_turns(reader, errors)
    if not turns:
        return pd.DataFrame()

    rows: list[dict] = []
    try:
        groups: dict[str, dict] = {}
        order: list[str] = []
        for turn in turns:
            title = turn.get("conversation title", "")
            if title not in groups:
                groups[title] = {"times": [], "models": set(), "count": 0}
                order.append(title)
            group = groups[title]
            group["count"] += 1
            parsed = _parse_iso(turn.get("time", ""))
            if parsed is not None:
                group["times"].append((parsed, turn["time"]))
            if turn.get("role") == "assistant" and turn.get("model"):
                group["models"].add(turn["model"])

        for title in order:
            group = groups[title]
            started = min(group["times"])[1] if group["times"] else ""
            last_message = max(group["times"])[1] if group["times"] else ""
            rows.append({
                "Conversation title": title,
                "Started": started,
                "Last message": last_message,
                "Turns": group["count"],
                "Models": ", ".join(sorted(group["models"])),
            })
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
        return pd.DataFrame()

    return pd.DataFrame(rows)


def messages_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract every ChatGPT message turn into a DataFrame, one row per turn.

    The per-turn frame ``conversations_to_df`` used to return directly, now
    under its own name and table (``chatgpt_messages``) now that
    ``conversations_to_df`` aggregates to one row per conversation instead.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns, in order: ``Time``, ``Conversation title``, ``Role``, ``Message``, ``Model``.
        Empty DataFrame when the file is absent or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one message turn in a ChatGPT conversation, including the role (user or assistant), the message text, the model used, and the timestamp.",
          "source_file": "conversations files (conversations-000.json, conversations-001.json, ...)",
          "columns": {
            "Time": "ISO 8601 timestamp of when the message was created.",
            "Conversation title": "Title of the conversation as stored in the export.",
            "Role": "Role of the message author: 'user' or 'assistant'.",
            "Message": "Full text of the message.",
            "Model": "ChatGPT model slug used to generate the assistant reply. Blank on user turns — only an assistant reply records which model produced it."
          }
        }

    Table config::

        {
          "id": "chatgpt_messages",
          "title": {
            "en": "Your messages with ChatGPT",
            "nl": "Je berichten met ChatGPT"
          },
          "description": {
            "en": "Every message turn across your ChatGPT conversations, from the conversations export files.",
            "nl": "Elk berichtbeurt uit je ChatGPT-gesprekken, uit de conversations-exportbestanden."
          },
          "headers": {
            "Time": {"en": "Time", "nl": "Tijd"},
            "Conversation title": {"en": "Conversation title", "nl": "Gesprektitel"},
            "Role": {"en": "Role", "nl": "Rol"},
            "Message": {"en": "Message", "nl": "Bericht"},
            "Model": {"en": "Model", "nl": "Model"}
          },
          "visualizations": [
            {
              "title": {
                "en": "Your conversations",
                "nl": "Je gesprekken"
              },
              "type": "thread",
              "groupColumn": "Conversation title",
              "roleColumn": "Role",
              "textColumn": "Message",
              "timeColumn": "Time",
              "badgeColumn": "Model",
              "selfRole": "user"
            },
            {
              "title": {
                "en": "Your messages in a wordcloud",
                "nl": "Je berichten in een woordwolk"
              },
              "type": "wordcloud",
              "textColumn": "Message",
              "tokenize": true
            },
            {
              "title": {"en": "Which days you chat with ChatGPT most", "nl": "Op welke dagen je het meest met ChatGPT chat"},
              "type": "bar",
              "group": {"column": "Time", "dateFormat": "weekday_cycle", "label": {"en": "Day of the week", "nl": "Dag van de week"}},
              "values": [{"aggregate": "count", "label": {"en": "Number of messages", "nl": "Aantal berichten"}}]
            },
            {
              "title": {"en": "When you talk to ChatGPT", "nl": "Wanneer je met ChatGPT praat"},
              "type": "heatmap",
              "mode": "weekday_hour",
              "dateColumn": "Time"
            }
          ]
        }
    """
    turns = _conversation_turns(reader, errors)
    if not turns:
        return pd.DataFrame()

    df = pd.DataFrame(turns).rename(columns={
        "time": "Time",
        "conversation title": "Conversation title",
        "role": "Role",
        "message": "Message",
        "model": "Model",
    })
    return pd.DataFrame(df[["Time", "Conversation title", "Role", "Message", "Model"]])


def models_used_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Extract which AI model produced each ChatGPT reply.

    One row per assistant turn — the ``model`` field a user turn carries is
    always blank (see ``_conversation_turns``), so filtering to
    ``role == "assistant"`` is what makes a model-grouped chart meaningful:
    ``chatgpt_conversations`` used to group its own model bar over every
    turn, including the 1508 (of 3057, on the real export) blank-model user
    turns, making the tallest bar an empty category. This table exists so
    that chart has a column worth grouping on.

    Parameters
    ----------
    reader:
        Archive reader used to load JSON files from the DDP zip.
    errors:
        Mutable counter that accumulates error type counts encountered during
        extraction.  Updated in-place.

    Returns
    -------
    pd.DataFrame
        Columns: ``model``, ``timestamp``, ``conversation title``. One row
        per assistant turn.
        Empty DataFrame when no conversations file is found or parsing fails.

    Table documentation::

        {
          "summary": "Each row represents one ChatGPT reply, naming the AI model that produced it.",
          "source_file": "conversations files (conversations-000.json, conversations-001.json, ...)",
          "columns": {
            "model": "ChatGPT model slug that produced this reply.",
            "timestamp": "ISO 8601 timestamp of when the reply was created.",
            "conversation title": "Title of the conversation this reply belongs to."
          }
        }

    Table config::

        {
          "id": "chatgpt_models_used",
          "title": {
            "en": "Which AI models answered you",
            "nl": "Welke AI-modellen je antwoordden"
          },
          "description": {
            "en": "The AI model behind each of your ChatGPT replies, from the conversations export files.",
            "nl": "Het AI-model achter elk van uw ChatGPT-antwoorden, uit de conversations-exportbestanden."
          },
          "headers": {
            "model": {"en": "Model", "nl": "Model"},
            "timestamp": {"en": "Time", "nl": "Tijd"},
            "conversation title": {"en": "Conversation title", "nl": "Gesprektitel"}
          },
          "visualizations": [
            {
              "title": {"en": "Which AI models answered you", "nl": "Welke AI-modellen je antwoordden"},
              "type": "bar",
              "group": {"column": "model", "top": 10, "label": {"en": "Model", "nl": "Model"}},
              "values": [{"aggregate": "count", "label": {"en": "Number of replies", "nl": "Aantal antwoorden"}}]
            }
          ]
        }
    """
    out = pd.DataFrame()
    try:
        assistant_turns = [t for t in _conversation_turns(reader, errors) if t.get("role") == "assistant"]
        if assistant_turns:
            df = pd.DataFrame(assistant_turns).rename(columns={"time": "timestamp"})
            out = pd.DataFrame(df[["model", "timestamp", "conversation title"]])
    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
    return out


# ---------------------------------------------------------------------------
# Extractor registry & platform info
# ---------------------------------------------------------------------------

#: Mapping from the string names used in port_config.json to actual extractor functions.
EXTRACTOR_REGISTRY: dict[str, Callable[..., pd.DataFrame]] = {
    "account_info_to_df": account_info_to_df,
    "conversations_to_df": conversations_to_df,
    "messages_to_df": messages_to_df,
    "models_used_to_df": models_used_to_df,
}


# ---------------------------------------------------------------------------
# Main extraction & flow
# ---------------------------------------------------------------------------

def extraction(chatgpt_zip: SeekableBinaryReader, validation) -> ExtractionResult:
    """Extract data from a ChatGPT DDP zip and return consent-form tables.

    Parameters
    ----------
    chatgpt_zip:
        Seekable binary reader over the ChatGPT DDP zip — the upload
        adapter itself, never a path (ADR-0026).
    validation:
        Validation result object whose ``archive_members`` attribute is passed
        to ``ZipArchiveReader``.
    """
    config = load_port_config(EXTRACTOR_REGISTRY, "chatgpt")
    errors: Counter = Counter()
    reader = ZipArchiveReader(chatgpt_zip, validation.archive_members, errors)
    return run_extraction(reader, errors, config)


class ChatGPTFlow(FlowBuilder):
    """Flow implementation for the ChatGPT data donation study."""

    def __init__(self, session_id: str):
        super().__init__(session_id, "ChatGPT")

    def validate_file(self, file):
        return validate.validate_zip(DDP_CATEGORIES, file)

    def extract_data(self, file_value, validation):
        return extraction(file_value, validation)


def process(session_id):
    flow = ChatGPTFlow(session_id)
    return flow.start_flow()
