"""Study-side extraction helpers (algosoc-2026): email/username redaction and the
typed XPath helper the study's HTML extractors use.

These helpers are study-local — they are applied inside each platform's
``extraction()`` after the tables are built, so they must leave missing cells
missing (never the literal text "nan") and must not redact inside unrelated
words when the username is short.
"""

import numpy as np
import pandas as pd
import pytest

from port.helpers.extraction_helpers import (
    EMAIL_PATTERN,
    anonymize_dataframe,
    redact_member_path,
    replace_email,
    replace_username,
)


class TestReplaceEmail:
    def test_replaces_every_address(self):
        text = "mail me at jane.doe+x@example.org or JANE@Example.co.uk today"
        assert replace_email(text) == "mail me at [email] or [email] today"

    def test_leaves_text_without_addresses_untouched(self):
        assert replace_email("no address here @ all") == "no address here @ all"

    def test_pattern_is_shared(self):
        assert EMAIL_PATTERN.search("a@b.cc") is not None


class TestReplaceUsername:
    def test_case_insensitive_whole_word(self):
        assert replace_username("Hi Jane, JANE and jane!", "jane") == "Hi [user], [user] and [user]!"

    def test_short_username_does_not_hit_unrelated_words(self):
        # "al" is a plausible two-letter username; it must not redact "already"
        # or "alcohol", only the standalone token.
        assert replace_username("al already drank alcohol, al.", "al") == "[user] already drank alcohol, [user]."

    def test_username_with_regex_metacharacters(self):
        assert replace_username("ping j.doe (j.doe) now", "j.doe") == "ping [user] ([user]) now"

    def test_username_adjacent_to_punctuation(self):
        assert replace_username("@al: al's turn", "al") == "@[user]: [user]'s turn"


class TestAnonymizeDataframe:
    def test_missing_cells_stay_missing(self):
        df = pd.DataFrame({"Title": ["a@b.cc", None, np.nan, "plain"]})
        anonymize_dataframe(df, ["Title"])
        assert df["Title"].tolist()[0] == "[email]"
        assert df["Title"].tolist()[3] == "plain"
        assert df["Title"].isna().tolist() == [False, True, True, False]
        assert "nan" not in df["Title"].dropna().tolist()
        assert "None" not in df["Title"].dropna().tolist()
        # The wire form the consent UI receives: a missing cell is JSON null,
        # exactly like an untouched column, never the text "nan".
        assert '"1":null' in df.to_json() and '"2":null' in df.to_json()

    def test_username_replaced_only_as_whole_word(self):
        df = pd.DataFrame({"Details": ["al liked this", "already", None]})
        anonymize_dataframe(df, ["Details"], username="al")
        assert df["Details"].tolist()[0] == "[user] liked this"
        assert df["Details"].tolist()[1] == "already"
        assert pd.isna(df["Details"].tolist()[2])

    def test_absent_columns_are_skipped_and_frame_mutated_in_place(self):
        df = pd.DataFrame({"Title": ["x@y.zz"], "Other": [1]})
        out = anonymize_dataframe(df, ["Title", "Missing"], username="x")
        assert out is df
        assert df["Title"].tolist() == ["[email]"]
        assert df["Other"].tolist() == [1]

    def test_empty_username_means_no_username_pass(self):
        df = pd.DataFrame({"Title": ["nothing to do"]})
        anonymize_dataframe(df, ["Title"], username="")
        assert df["Title"].tolist() == ["nothing to do"]

    def test_empty_frame_is_a_no_op(self):
        df = pd.DataFrame({"Title": pd.Series([], dtype="object")})
        anonymize_dataframe(df, ["Title"], username="jane")
        assert df.empty


class TestXpathNodes:
    def test_node_query_returns_the_element_list(self):
        from lxml import etree
        from port.helpers.extraction_helpers import xpath_nodes

        tree = etree.HTML("<html><body><section>a</section><section>b</section></body></html>")
        nodes = xpath_nodes(tree, "//section")
        assert [n.text for n in nodes] == ["a", "b"]

    def test_non_node_results_are_no_matches(self):
        from lxml import etree
        from port.helpers.extraction_helpers import xpath_nodes

        tree = etree.HTML("<html><body><p>x</p></body></html>")
        assert xpath_nodes(tree, "count(//p)") == []
        assert xpath_nodes(tree, "string(//p)") == []
        assert xpath_nodes(tree, "boolean(//p)") == []
        assert xpath_nodes(tree, "//nothing") == []


class TestRedactMemberPath:
    """An archive member path is participant data: exports name folders and files after
    the people the participant talked to. What survives is the shape — which top-level
    section, how deep, what kind of file."""

    @pytest.mark.parametrize("path,expected", [
        ("messages/inbox/name_123/message_1.json", "messages/<dir>/<dir>/<file>.json"),
        ("messages/inbox/message_1.json", "messages/<dir>/<file>.json"),
        ("ads_information/advertisers.json", "ads_information/<file>.json"),
        ("archive_browser.html", "<file>.html"),
        ("Takeout/YouTube/history/watch-history.html", "Takeout/<dir>/<dir>/<file>.html"),
    ])
    def test_the_shape_is_kept_and_the_names_are_not(self, path, expected):
        assert redact_member_path(path) == expected

    def test_a_leaf_without_an_extension_is_still_a_leaf(self):
        assert redact_member_path("messages/inbox/README") == "messages/<dir>/<file>"

    def test_a_dotfile_has_no_extension_to_keep(self):
        assert redact_member_path("config/.gitignore") == "config/<file>"

    def test_only_the_last_dot_names_the_kind(self):
        assert redact_member_path("logs/session.tar.gz") == "logs/<file>.gz"

    def test_a_directory_entry_stays_a_directory(self):
        assert redact_member_path("messages/inbox/name_123/") == "messages/<dir>/<dir>/"

    def test_empty_and_degenerate_paths_are_returned_as_they_are(self):
        assert redact_member_path("") == ""
        assert redact_member_path("/") == "/"

    def test_redaction_is_idempotent(self):
        once = redact_member_path("messages/inbox/name_123/message_1.json")
        assert redact_member_path(once) == once
