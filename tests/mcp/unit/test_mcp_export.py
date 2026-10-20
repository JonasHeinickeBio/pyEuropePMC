"""Unit tests for the export tool and the pure module behind it (hermetic).

``tests/fixtures/export/records.json`` holds Europe PMC core records reduced to the fields the
export reads. Three are real (PMIDs 16004729, 33069326 and 42217054); the long-author-list, the
special-characters and the preprint records are synthetic and say so in a ``_synthetic`` key.
The golden files under ``golden/`` are the expected output for the three cases the issue asks
for (no abstract, very long author list, unusual characters) in every format, and were read
through by hand when they were written.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from pathlib import Path
import re
import sys
from unittest.mock import MagicMock

from mcp.server.fastmcp.exceptions import ToolError
import pytest

from pyeuropepmc.mcp import _batch as bm, _export as ex, server as srv

FIXTURES = Path(__file__).parents[2] / "fixtures" / "export"
RECORDS = json.loads((FIXTURES / "records.json").read_text(encoding="utf-8"))
EXT = {
    "bibtex": "bib",
    "ris": "ris",
    "csl-json": "json",
    "csv": "csv",
    "json": "jsonl.json",
    "markdown": "md",
}
TABLE_FIELDS = (
    "id",
    "source",
    "pmid",
    "pmcid",
    "doi",
    "title",
    "authors",
    "journal",
    "year",
    "is_open_access",
    "abstract",
)


def _run(coro):
    return asyncio.run(coro)


def _trimmed(text: str) -> str:
    """Text without trailing whitespace on any line or at the end."""
    return "\n".join(line.rstrip() for line in text.splitlines()).rstrip()


def render(fmt, records, *, abstract=True, fields=None, max_chars=10**6):
    wanted = fields or (TABLE_FIELDS if fmt in ("csv", "json", "markdown") else bm.DEFAULT_FIELDS)
    header, units, sep, footer, _ = srv._export_units(fmt, records, wanted, abstract)
    return srv._fit_units(header, units, sep, footer, max_chars)


@pytest.fixture(autouse=True)
def _reset_client():
    srv._client_cache.reset()
    yield
    srv._client_cache.reset()


class TestGolden:
    @pytest.mark.parametrize("name", ["no_abstract", "long_authors", "special_chars"])
    @pytest.mark.parametrize("fmt", list(EXT))
    def test_output_matches_the_reviewed_file(self, name, fmt):
        text, _kept = render(fmt, [RECORDS[name]])
        golden = (FIXTURES / "golden" / f"{name}.{EXT[fmt]}").read_text(encoding="utf-8")
        # RIS ends an entry with "ER  - " (a trailing space is conventional); the repository's
        # trailing-whitespace hook strips it from the golden file, so compare without it.
        assert _trimmed(text) == _trimmed(golden)


class TestBibtexNeedsNoExtra:
    """``BibtexManager`` needs bibtexparser to write; the export must work without it."""

    def test_it_works_when_bibtexparser_cannot_be_imported(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "bibtexparser", None)  # an import now raises
        text, kept = render("bibtex", [RECORDS["vasiliou"], RECORDS["gbd"]])
        assert kept == 2
        assert text.startswith("@article{vasiliou2005analysis,")

    def test_the_module_does_not_import_the_library_bibliography_code(self):
        source = Path(ex.__file__).read_text(encoding="utf-8")
        pattern = r"^\s*(?:from|import)\s+pyeuropepmc\.features\.bibliography"
        imports = re.findall(pattern, source, re.M)
        assert imports == []

    def test_the_layout_is_the_librarys(self):
        paper = ex.to_paper(RECORDS["no_abstract"])
        ex.assign_keys([paper])
        lines = ex.bibtex_entry(paper).splitlines()
        assert lines[0] == "@article{hrabos2026grp78,"
        assert lines[1].startswith(" author = {")
        assert lines[-1] == "}"
        assert all(line.endswith(",") for line in lines[1:-2])
        assert not lines[-2].endswith(",")
        names = [line.split(" = ")[0].strip() for line in lines[1:-1]]
        assert names == sorted(names)

    def test_unbalanced_braces_in_a_raw_field_cannot_end_the_entry_early(self):
        paper = ex.to_paper({"id": "1", "source": "MED", "doi": "10.0000/a}b{{c", "title": "T"})
        ex.assign_keys([paper])
        entry = ex.bibtex_entry(paper)
        assert "doi = {10.0000/a%7Db%7B%7Bc}" in entry
        assert entry.count("{") == entry.count("}")

    def test_balanced_braces_are_left_alone(self):
        paper = ex.to_paper({"id": "1", "source": "MED", "doi": "10.0000/{a}", "title": "T"})
        ex.assign_keys([paper])
        assert "doi = {10.0000/{a}}" in ex.bibtex_entry(paper)


class TestFormatsAreValid:
    """Independent of the golden files: each format must read back."""

    ALL = [
        RECORDS[k]
        for k in ("vasiliou", "gbd", "no_abstract", "long_authors", "special_chars", "preprint")
    ]

    def test_bibtex_reads_back(self):
        pytest.importorskip("bibtexparser")
        from pyeuropepmc.features.bibliography.bibtex import BibtexManager

        text, _ = render("bibtex", self.ALL)
        library = BibtexManager().parse_string(text)
        assert [e.citation_key for e in library.entries] == [
            "vasiliou2005analysis",
            "gbd2020global",
            "hrabos2026grp78",
            "okafor2005consortium",
            "muller2005analysis",
            "doe2025preprint",
        ]
        gbd = library.entries[1]
        assert gbd.fields["author"] == "{GBD 2019 Diseases and Injuries Collaborators}"
        assert library.entries[-1].entry_type == "misc"

    def test_ris_is_well_formed(self):
        text, kept = render("ris", self.ALL)
        entries = text.split("\n\n")
        assert len(entries) == kept == 6
        for entry in entries:
            lines = entry.splitlines()
            assert lines[0].startswith("TY  - ")
            assert lines[-1] == "ER  - "
            assert all(re.fullmatch(r"[A-Z][A-Z0-9]  - .*", line) for line in lines), entry

    def test_ris_values_never_span_lines(self):
        text, _ = render("ris", [RECORDS["special_chars"]])
        assert "\n\n" not in text
        assert all(re.match(r"[A-Z][A-Z0-9]  - ", line) for line in text.splitlines())

    def test_csl_json_parses_with_the_expected_shape(self):
        text, _ = render("csl-json", self.ALL)
        items = json.loads(text)
        assert [i["id"] for i in items][:2] == ["vasiliou2005analysis", "gbd2020global"]
        assert items[0]["type"] == "article-journal"
        assert items[0]["author"][0] == {"family": "Vasiliou", "given": "Vasilis"}
        assert items[0]["issued"] == {"date-parts": [[2005, 6]]}
        assert items[1]["author"] == [{"literal": "GBD 2019 Diseases and Injuries Collaborators"}]
        assert items[-1]["type"] == "article"  # a preprint

    def test_json_and_csv_hold_the_same_rows(self):
        as_json = json.loads(render("json", self.ALL)[0])
        rows = list(csv.reader(io.StringIO(render("csv", self.ALL)[0])))
        assert rows[0] == list(TABLE_FIELDS)
        assert len(rows) - 1 == len(as_json) == 6
        assert [r[0] for r in rows[1:]] == [j["id"] for j in as_json]
        assert as_json[4]["is_open_access"] is False
        assert rows[5][TABLE_FIELDS.index("is_open_access")] == "false"

    def test_markdown_rows_have_one_cell_per_column(self):
        text, _ = render("markdown", self.ALL)
        for line in text.splitlines():
            cells = re.split(r"(?<!\\)\|", line.strip())[1:-1]
            assert len(cells) == len(TABLE_FIELDS), line


class TestCleanText:
    def test_block_tags_become_a_space_and_inline_tags_vanish(self):
        raw = (
            "<h4>Background</h4><p>In an era of <i>change</i>, H<sub>2</sub>O.</p>"
            "<h4>Methods</h4><p>We did.</p>"
        )
        assert ex.clean_text(raw) == "Background In an era of change, H2O. Methods We did."

    def test_entities_and_whitespace(self):
        assert ex.clean_text("R&amp;D\n  costs &lt;5%") == "R&D costs <5%"

    def test_not_a_string(self):
        assert ex.clean_text(None) == ""
        assert ex.clean_text(5) == ""

    def test_identifiers_are_only_trimmed(self):
        sici = "10.1002/(SICI)1097-0258(19980815/30)17:15/16<1661::AID-SIM968>3.0.CO;2-2"
        assert ex.identifier(f"  {sici} ") == sici
        assert ex.identifier("10.0000/a&#1%20") == "10.0000/a&#1%20"
        assert ex.identifier(None) == ""
        paper = ex.to_paper({"id": "1", "source": "MED", "doi": sici})
        assert paper.doi == sici
        assert sici in ex.bibtex_entry(paper)


class TestAuthors:
    def test_structured_list(self):
        record = {"authorList": {"author": [{"lastName": "Vasiliou", "firstName": "Vasilis"}]}}
        assert ex.authors_of(record) == [ex.Person(family="Vasiliou", given="Vasilis")]

    def test_initials_when_there_is_no_first_name(self):
        record = {"authorList": {"author": [{"lastName": "Vos", "initials": "T"}]}}
        assert ex.authors_of(record)[0] == ex.Person(family="Vos", given="T")

    def test_a_collective_author_stays_one_name(self):
        record = {"authorList": {"author": [{"collectiveName": "A and B Consortium"}]}}
        (person,) = ex.authors_of(record)
        assert person.is_collective
        assert person.bibtex() == "{A and B Consortium}"
        assert person.ris() == "A and B Consortium"
        assert person.csl() == {"literal": "A and B Consortium"}

    def test_full_name_is_split_when_only_that_is_given(self):
        record = {"authorList": {"author": [{"fullName": "Nebert DW"}]}}
        assert ex.authors_of(record) == [ex.Person(family="Nebert", given="DW")]

    def test_author_string_is_the_fallback(self):
        people = ex.authors_of({"authorString": "Vasiliou V, Nebert DW."})
        assert people == [ex.Person("Vasiliou", "V"), ex.Person("Nebert", "DW")]

    def test_a_name_without_initials_is_kept_whole(self):
        assert ex.authors_of({"authorString": "WHO Working Group."}) == [
            ex.Person(literal="WHO Working Group")
        ]

    def test_nothing(self):
        assert ex.authors_of({}) == []

    def test_only_the_first_hundred_are_kept_and_the_rest_counted(self):
        authors = [{"lastName": f"A{i}", "firstName": "X"} for i in range(250)]
        record = {"authorList": {"author": authors}}
        paper = ex.to_paper(record)
        assert len(paper.authors) == ex.MAX_AUTHORS == 100
        assert paper.authors_omitted == 150
        assert ex.bibtex_fields(paper)["author"].endswith(" and others")
        assert "others" not in ex.ris_entry(paper)


class TestPages:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("138-143", ("138", "143")),
            ("138-43", ("138", "143")),  # NLM abbreviates the end page
            ("1204–1222", ("1204", "1222")),  # en dash
            ("e12345", ("e12345", "")),  # an article number
            ("64", ("64", "")),
            ("S12-S15", ("S12", "S15")),
            ("", ("", "")),
        ],
    )
    def test_split(self, raw, expected):
        assert ex.split_pages(raw) == expected

    def test_ris_has_separate_start_and_end(self):
        paper = ex.to_paper({"id": "1", "source": "MED", "pageInfo": "138-43"})
        ris = ex.ris_entry(paper)
        assert "SP  - 138" in ris and "EP  - 143" in ris
        assert "pages = {138--143}" in ex.bibtex_entry(paper)


class TestKeys:
    def paper(self, **kw):
        base = {
            "id": "1",
            "source": "MED",
            "pubYear": "2005",
            "title": "A study of the deep nets",
            "authorList": {"author": [{"lastName": "Smith", "firstName": "J"}]},
        }
        base.update(kw)
        return ex.to_paper(base)

    def test_author_year_first_significant_word(self):
        assert ex.key_base(self.paper()) == "smith2005study"

    def test_accents_are_folded_and_digits_kept_in_the_title_word(self):
        paper = self.paper(
            title="GRP78 associates", authorList={"author": [{"lastName": "Müller-Ångström"}]}
        )
        assert ex.key_base(paper) == "mullerangstrom2005grp78"

    def test_a_year_or_a_stopword_is_not_the_word(self):
        assert ex.key_base(self.paper(title="2020 and the of in COVID")) == "smith2005covid"

    def test_missing_pieces(self):
        paper = ex.to_paper({"id": "1", "source": "MED", "title": "The of"})
        assert ex.key_base(paper) == "anonnd"

    def test_a_collective_author_gives_its_first_word(self):
        paper = self.paper(authorList={"author": [{"collectiveName": "GBD 2019 Collaborators"}]})
        assert ex.key_base(paper).startswith("gbd2005")

    def test_collisions_get_letters_in_input_order(self):
        papers = [self.paper(id=str(i)) for i in range(30)]
        ex.assign_keys(papers)
        keys = [p.key for p in papers]
        assert keys[:4] == [
            "smith2005study",
            "smith2005studya",
            "smith2005studyb",
            "smith2005studyc",
        ]
        assert keys[26] == "smith2005studyz"
        assert keys[27] == "smith2005studyaa"
        assert len(set(keys)) == 30

    def test_a_suffixed_key_never_collides_with_a_real_base(self):
        a = self.paper(id="1")
        b = self.paper(id="2")
        c = self.paper(id="3", title="A studya of nets")  # base smith2005studya
        papers = [a, b, c]
        ex.assign_keys(papers)
        assert len({p.key for p in papers}) == 3

    def test_keys_do_not_depend_on_the_other_papers_beyond_earlier_collisions(self):
        one = [self.paper(id="1")]
        ex.assign_keys(one)
        two = [self.paper(id="1"), self.paper(id="2")]
        ex.assign_keys(two)
        assert one[0].key == two[0].key


class TestTexEscape:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("R&D", r"R\&D"),
            ("100%", r"100\%"),
            ("a_b", r"a\_b"),
            ("#1", r"\#1"),
            ("$x$", r"\$x\$"),
            ("{a}", r"\{a\}"),
            ("a~b^c", r"a\textasciitilde{}b\textasciicircum{}c"),
            ("a\\b", r"a\textbackslash{}b"),
            ("éü α-synuclein", "éü α-synuclein"),  # unicode is kept
            ("plain", "plain"),
        ],
    )
    def test_escapes(self, raw, expected):
        assert ex.tex_escape(raw) == expected

    def test_doi_and_url_are_not_escaped(self):
        paper = ex.to_paper({"id": "1", "source": "MED", "doi": "10.0000/a_b%20&c#1"})
        fields = ex.bibtex_fields(paper)
        assert fields["doi"] == "10.0000/a_b%20&c#1"
        assert "\\" not in fields["url"]


class TestKindAndMapping:
    def test_a_preprint_is_misc_and_a_journal_article_is_an_article(self):
        assert ex.to_paper({"id": "1", "source": "PPR", "title": "x"}).kind == "misc"
        assert ex.to_paper({"id": "1", "source": "MED", "journalTitle": "J"}).kind == "article"
        assert ex.to_paper({"id": "1", "source": "MED"}).kind == "misc"

    def test_lite_records_work_too(self):
        lite = {
            "id": "1",
            "source": "MED",
            "pmid": "1",
            "title": "A lite record.",
            "authorString": "Vasiliou V, Nebert DW.",
            "journalTitle": "Hum Genomics",
            "pubYear": "2005",
            "journalVolume": "2",
            "issue": "2",
            "pageInfo": "138-43",
        }
        paper = ex.to_paper(lite)
        assert (paper.title, paper.journal, paper.volume, paper.pages) == (
            "A lite record",
            "Hum Genomics",
            "2",
            "138-143",
        )
        assert len(paper.authors) == 2

    def test_the_title_loses_one_final_period_and_markup(self):
        assert ex.to_paper({"title": "Hello <i>world</i>."}).title == "Hello world"
        assert ex.to_paper({"title": "Wait..."}).title == "Wait..."


def _client(records, hits=None):
    client = MagicMock()
    client.search_all.return_value = records
    client.get_hit_count.return_value = hits if hits is not None else len(records)
    srv._client_cache.set(client)
    return client


def rec(i, **kw):
    base = {
        "id": str(i),
        "source": "MED",
        "pmid": str(i),
        "title": f"Paper number {i}.",
        "authorString": f"Author{i} A.",
        "journalTitle": "J Test",
        "pubYear": "2020",
        "isOpenAccess": "N",
    }
    base.update(kw)
    return base


class TestExportPapersTool:
    def test_exactly_one_of_query_and_ids(self):
        _client([])
        with pytest.raises(ToolError, match="either query or ids"):
            _run(srv.export_papers())
        with pytest.raises(ToolError, match="either query or ids"):
            _run(srv.export_papers(query="x", ids=["1"]))

    def test_a_query_with_errors_is_refused_before_any_request(self):
        client = _client([])
        with pytest.raises(ToolError, match="Fix the query first"):
            _run(srv.export_papers(query="malaria AND"))
        client.search_all.assert_not_called()

    def test_skip_plus_limit_is_bounded(self):
        client = _client([])
        with pytest.raises(ToolError, match="must not exceed 1000"):
            _run(srv.export_papers(query="x", limit=500, skip=600))
        client.search_all.assert_not_called()

    def test_unknown_field(self):
        _client([])
        with pytest.raises(ToolError, match="unknown field"):
            _run(srv.export_papers(query="x", format="csv", fields=["nope"]))

    def test_query_mode_asks_for_exactly_skip_plus_limit_and_slices(self):
        client = _client([rec(i) for i in range(1, 6)], hits=500)

        out = _run(srv.export_papers(query="malaria", format="bibtex", limit=3, skip=2))

        client.search_all.assert_called_once_with(
            "malaria", page_size=5, max_results=5, resultType="core"
        )
        assert out["exported"] == 3
        assert out["found"] == 3
        assert out["total_hits"] == 500
        assert out["next_skip"] == 5
        assert out["truncated"] is False
        assert "pmid = {3}" in out["content"] and "pmid = {1}" not in out["content"]

    def test_the_last_part_has_no_next_skip(self):
        _client([rec(1), rec(2)], hits=2)
        assert _run(srv.export_papers(query="x", limit=10))["next_skip"] is None

    def test_tables_without_an_abstract_use_the_smaller_lite_records(self):
        client = _client([rec(1)])
        _run(srv.export_papers(query="x", format="csv"))
        assert client.search_all.call_args.kwargs["resultType"] == "lite"
        _run(srv.export_papers(query="x", format="csv", fields=["title", "abstract"]))
        assert client.search_all.call_args.kwargs["resultType"] == "core"
        _run(srv.export_papers(query="x", format="ris"))
        assert client.search_all.call_args.kwargs["resultType"] == "core"

    def test_ids_mode_keeps_the_order_and_names_what_was_left_out(self):
        _client([rec(2), rec(1)])  # Europe PMC answers in its own order

        out = _run(srv.export_papers(ids=["1", "2", "99", "junk", "pmid-x", "1"], format="ris"))

        assert out["exported"] == 2
        assert out["content"].index("Paper number 1") < out["content"].index("Paper number 2")
        assert out["skipped"] == [
            {"id": "99", "status": "not_found"},
            {"id": "junk", "status": "invalid"},
            {"id": "pmid-x", "status": "invalid"},
            {"id": "1", "status": "duplicate"},
        ]
        assert "total_hits" not in out
        assert out["remaining"] == []

    def test_limit_caps_the_identifier_list(self):
        client = _client([rec(1), rec(2)])
        out = _run(srv.export_papers(ids=["1", "2", "3", "4"], limit=2))
        assert "(EXT_ID:3" not in client.search_all.call_args.args[0]
        assert out["exported"] == 2

    def test_the_abstract_is_opt_in_for_citation_formats(self):
        _client([rec(1, abstractText="An abstract.")])
        without = _run(srv.export_papers(query="x", format="bibtex"))["content"]
        with_it = _run(srv.export_papers(query="x", format="bibtex", include_abstract=True))[
            "content"
        ]
        assert "abstract" not in without
        assert "abstract = {An abstract.}" in with_it

    def test_the_export_is_cut_at_a_record_boundary_and_stays_valid(self):
        records = [rec(i, abstractText="word " * 300) for i in range(1, 8)]
        _client(records)
        for fmt, check in (
            ("bibtex", lambda c, n: c.count("@article{") == n and c.rstrip().endswith("}")),
            ("ris", lambda c, n: c.count("TY  - JOUR") == n and c.rstrip().endswith("ER  -")),
            ("csl-json", lambda c, n: len(json.loads(c)) == n),
            ("json", lambda c, n: len(json.loads(c)) == n),
            ("csv", lambda c, n: len(list(csv.reader(io.StringIO(c)))) == n + 1),
            ("markdown", lambda c, n: len(c.splitlines()) == n + 2),
        ):
            out = _run(
                srv.export_papers(
                    query="x",
                    format=fmt,
                    include_abstract=True,
                    fields=["title", "abstract"],
                    max_chars=5000,
                )
            )
            assert out["truncated"] is True, fmt
            assert 0 < out["exported"] < 7, fmt
            assert out["found"] == 7
            assert out["returned_chars"] == len(out["content"])
            assert check(out["content"], out["exported"]), fmt

    def test_the_first_record_is_kept_even_when_it_is_longer_than_the_limit(self):
        _client([rec(1, abstractText="word " * 2000), rec(2)])
        out = _run(
            srv.export_papers(query="x", format="ris", include_abstract=True, max_chars=1000)
        )
        assert out["exported"] == 1
        assert out["truncated"] is True
        assert out["returned_chars"] > 1000

    def test_remaining_ids_say_where_to_continue(self):
        _client([rec(i, abstractText="word " * 300) for i in range(1, 6)])
        out = _run(
            srv.export_papers(
                ids=["1", "2", "3", "4", "5"],
                format="bibtex",
                include_abstract=True,
                max_chars=4000,
            )
        )
        assert out["truncated"] is True
        assert out["remaining"] == [str(i) for i in range(out["exported"] + 1, 6)]

    def test_keys_do_not_depend_on_how_much_fits(self):
        records = [rec(i, authorString="Same S.", title="Same words here.") for i in range(1, 6)]
        _client(records)
        full = _run(srv.export_papers(query="x", format="bibtex"))["content"]
        short = _run(srv.export_papers(query="x", format="bibtex", max_chars=1000))
        assert re.findall(r"@article\{(\w+),", full)[: short["exported"]] == re.findall(
            r"@article\{(\w+),", short["content"]
        )

    def test_a_note_says_when_authors_were_left_out(self):
        record = rec(1)
        authors = [{"lastName": f"A{i}", "firstName": "X"} for i in range(120)]
        record["authorList"] = {"author": authors}
        _client([record])
        bibtex = _run(srv.export_papers(query="x", format="bibtex"))
        ris = _run(srv.export_papers(query="x", format="ris"))
        assert "and BibTeX ends them with 'and others'" in bibtex["notes"][0]
        assert "100" in ris["notes"][0] and "BibTeX" not in ris["notes"][0]
        assert _run(srv.export_papers(query="x", format="csv"))["notes"] == []

    def test_a_europepmc_failure_is_a_tool_error(self):
        from pyeuropepmc.core.error_codes import ErrorCodes
        from pyeuropepmc.core.exceptions import APIClientError

        client = MagicMock()
        client.search_all.side_effect = APIClientError(ErrorCodes.NET001, {"error": "boom"})
        srv._client_cache.set(client)
        with pytest.raises(ToolError):
            _run(srv.export_papers(query="x"))

    def test_nothing_found_is_an_empty_export_not_an_error(self):
        _client([], hits=0)
        out = _run(srv.export_papers(query="x", format="csv"))
        assert out["exported"] == 0
        assert out["content"].splitlines()[0].startswith("id,source")
        assert out["truncated"] is False

    def test_the_tool_reads_only_and_its_bounds_are_in_the_schema(self):
        tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
        tool = tools["export_papers"]
        assert tool.annotations.readOnlyHint is True
        props = tool.inputSchema["properties"]
        assert (props["limit"]["minimum"], props["limit"]["maximum"]) == (1, 1000)
        assert (props["skip"]["minimum"], props["skip"]["maximum"]) == (0, 999)
        assert props["format"]["enum"] == ["bibtex", "ris", "csl-json", "csv", "json", "markdown"]
        assert props["max_chars"]["minimum"] == 1000
