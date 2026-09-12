"""Additional unit tests for pyeuropepmc.features.bibliography.reference.

Covers ReferenceResolver's CrossRef/Europe PMC integration paths and the
static parsing helpers, which are not exercised by the existing
tests/unit/bibliography/test_reference.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pyeuropepmc.features.bibliography.reference import ReferenceResolver


def _resolver():
    return ReferenceResolver(crossref_email="me@example.com")


class TestResolveTopLevel:
    def test_resolve_isbn(self):
        resolver = _resolver()
        with patch.object(resolver, "_resolve_via_pmc", return_value=None) as mock_pmc:
            resolver.resolve_isbn("978-0-13-468599-1")
        mock_pmc.assert_called_once_with("9780134685991")

    def test_resolve_pmcid_adds_prefix(self):
        resolver = _resolver()
        with patch.object(resolver, "_resolve_via_pmc", return_value=None) as mock_pmc:
            resolver.resolve_pmcid("123456")
        mock_pmc.assert_called_once_with("PMCID:PMC123456")

    def test_resolve_pmcid_keeps_existing_prefix(self):
        resolver = _resolver()
        with patch.object(resolver, "_resolve_via_pmc", return_value=None) as mock_pmc:
            resolver.resolve_pmcid("pmc123456")
        mock_pmc.assert_called_once_with("PMCID:PMC123456")

    def test_resolve_arxiv_found_via_pmc(self):
        resolver = _resolver()
        sentinel = object()
        with patch.object(resolver, "_resolve_via_pmc", return_value=sentinel) as mock_pmc:
            result = resolver.resolve_arxiv("arXiv:2101.00001")
        mock_pmc.assert_called_once_with("2101.00001")
        assert result is sentinel

    def test_resolve_arxiv_falls_back_to_doi(self):
        resolver = _resolver()
        sentinel = object()
        with (
            patch.object(resolver, "_resolve_via_pmc", return_value=None),
            patch.object(resolver, "resolve_doi", return_value=sentinel) as mock_doi,
        ):
            result = resolver.resolve_arxiv("2101.00001")
        mock_doi.assert_called_once_with("10.48550/arXiv.2101.00001")
        assert result is sentinel

    def test_resolve_doi_strips_prefix_and_lowercases(self):
        resolver = _resolver()
        with patch.object(resolver, "_resolve_via_crossref", return_value="ref") as mock_cr:
            result = resolver.resolve_doi("DOI:10.1234/ABC")
        mock_cr.assert_called_once_with("10.1234/abc")
        assert result == "ref"

    def test_resolve_doi_falls_back_to_pmc_when_crossref_returns_none(self):
        resolver = _resolver()
        sentinel = object()
        with (
            patch.object(resolver, "_resolve_via_crossref", return_value=None),
            patch.object(resolver, "_resolve_via_pmc", return_value=sentinel) as mock_pmc,
        ):
            result = resolver.resolve_doi("10.1234/abc")
        mock_pmc.assert_called_once_with('DOI:"10.1234/abc"')
        assert result is sentinel

    def test_resolve_doi_falls_back_to_pmc_on_crossref_exception(self):
        resolver = _resolver()
        sentinel = object()
        with (
            patch.object(resolver, "_resolve_via_crossref", side_effect=RuntimeError("boom")),
            patch.object(resolver, "_resolve_via_pmc", return_value=sentinel),
        ):
            result = resolver.resolve_doi("10.1234/abc")
        assert result is sentinel

    def test_resolve_unknown_type_logs_and_returns_none(self):
        resolver = _resolver()
        assert resolver.resolve("not an identifier at all !!!") is None

    def test_resolve_swallows_method_exception(self):
        resolver = _resolver()
        with patch.object(resolver, "resolve_doi", side_effect=RuntimeError("boom")):
            assert resolver.resolve("10.1234/abc") is None

    def test_search_by_title_crossref(self):
        resolver = _resolver()
        with patch.object(resolver, "_search_crossref", return_value=["r"]) as mock:
            result = resolver.search_by_title("some title", limit=3, source="crossref")
        mock.assert_called_once_with("some title", limit=3)
        assert result == ["r"]

    def test_search_by_title_pmc(self):
        resolver = _resolver()
        with patch.object(resolver, "_search_pmc", return_value=["r"]) as mock:
            result = resolver.search_by_title("some title", limit=2, source="pmc")
        mock.assert_called_once_with("some title", limit=2)
        assert result == ["r"]

    def test_resolve_many_skips_unresolved(self):
        resolver = _resolver()
        with patch.object(resolver, "resolve", side_effect=[None, "ref2", None]):
            result = resolver.resolve_many(["a", "b", "c"])
        assert result == ["ref2"]


class TestGetCrossrefClient:
    def test_lazy_initializes_once(self):
        resolver = _resolver()
        fake_client = MagicMock()
        with patch(
            "pyeuropepmc.features.enrich.sources.crossref.CrossRefClient",
            return_value=fake_client,
        ) as mock_cls:
            client1 = resolver._get_crossref_client()
            client2 = resolver._get_crossref_client()
        mock_cls.assert_called_once_with(email="me@example.com")
        assert client1 is client2 is fake_client


class TestResolveViaCrossref:
    def test_no_data_returns_none(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.enrich.return_value = None
        with patch.object(resolver, "_get_crossref_client", return_value=fake_client):
            assert resolver._resolve_via_crossref("10.1/x") is None

    def test_full_mapping(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.enrich.return_value = {
            "title": "A Title",
            "journal": "Nature",
            "volume": "10",
            "issue": "2",
            "pages": "1-10",
            "publisher": "NPG",
            "authors": [{"family": "Smith", "given": "J"}, "Doe A"],
            "abstract": "An abstract.",
            "url": "http://x",
            "type": "journal-article",
            "issued": {"date-parts": [[2020, 1]]},
        }
        with patch.object(resolver, "_get_crossref_client", return_value=fake_client):
            ref = resolver._resolve_via_crossref("10.1/x")
        assert ref.doi == "10.1/x"
        assert ref.title == "A Title"
        assert ref.journal == "Nature"
        assert ref.volume == "10"
        assert ref.issue == "2"
        assert ref.pages == "1-10"
        assert ref.publisher == "NPG"
        assert ref.authors == ["Smith, J", "Doe A"]
        assert ref.abstract == "An abstract."
        assert ref.url == "http://x"
        assert ref.entry_type == "article"
        assert ref.year == 2020

    def test_authors_not_a_list_left_default(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.enrich.return_value = {"title": "T", "authors": "not a list"}
        with patch.object(resolver, "_get_crossref_client", return_value=fake_client):
            ref = resolver._resolve_via_crossref("10.1/x")
        assert ref.authors == []


class TestSearchCrossref:
    def test_list_results(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = [{"DOI": "10.1/a"}, {"DOI": ""}]
        with (
            patch.object(resolver, "_get_crossref_client", return_value=fake_client),
            patch.object(resolver, "resolve_doi", return_value="ref") as mock_resolve,
        ):
            result = resolver._search_crossref("query", limit=5)
        mock_resolve.assert_called_once_with("10.1/a")
        assert result == ["ref"]

    def test_dict_results_message_items(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = {"message": {"items": [{"DOI": "10.1/b"}]}}
        with (
            patch.object(resolver, "_get_crossref_client", return_value=fake_client),
            patch.object(resolver, "resolve_doi", return_value="ref"),
        ):
            result = resolver._search_crossref("query")
        assert result == ["ref"]

    def test_unexpected_results_type_returns_empty(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = "not a list or dict"
        with patch.object(resolver, "_get_crossref_client", return_value=fake_client):
            result = resolver._search_crossref("query")
        assert result == []

    def test_resolve_doi_returning_none_is_skipped(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = [{"DOI": "10.1/a"}]
        with (
            patch.object(resolver, "_get_crossref_client", return_value=fake_client),
            patch.object(resolver, "resolve_doi", return_value=None),
        ):
            result = resolver._search_crossref("query")
        assert result == []


class TestGetSearchClient:
    def test_lazy_initializes_once(self):
        resolver = _resolver()
        fake_client = MagicMock()
        with patch("pyeuropepmc.SearchClient", return_value=fake_client) as mock_cls:
            c1 = resolver._get_search_client()
            c2 = resolver._get_search_client()
        mock_cls.assert_called_once()
        assert c1 is c2 is fake_client


class TestResolveViaPmc:
    def test_dict_results_with_papers(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = {
            "results": [
                {
                    "title": "T",
                    "doi": "10.1/x",
                    "pmid": "123",
                    "pmcid": "PMC1",
                    "pubYear": "2021",
                    "journalTitle": "J",
                    "journalVolume": "1",
                    "journalIssue": "2",
                    "pageInfo": "1-2",
                    "authorString": "Smith J, Doe A",
                    "abstractText": "Abstract text.",
                    "fullTextUrl": "http://x",
                }
            ]
        }
        with patch.object(resolver, "_get_search_client", return_value=fake_client):
            ref = resolver._resolve_via_pmc("query")
        assert ref.title == "T"
        assert ref.doi == "10.1/x"
        assert ref.pmid == "123"
        assert ref.pmcid == "PMC1"
        assert ref.year == 2021
        assert ref.journal == "J"
        assert ref.volume == "1"
        assert ref.issue == "2"
        assert ref.pages == "1-2"
        assert ref.authors == ["Smith J", "Doe A"]
        assert ref.abstract == "Abstract text."
        assert ref.url == "http://x"
        assert ref.entry_type == "article"
        assert ref.source == "europe_pmc"

    def test_no_papers_returns_none(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = {"results": []}
        with patch.object(resolver, "_get_search_client", return_value=fake_client):
            assert resolver._resolve_via_pmc("query") is None

    def test_non_dict_results_falsy_returns_none(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = None
        with patch.object(resolver, "_get_search_client", return_value=fake_client):
            assert resolver._resolve_via_pmc("query") is None

    def test_non_dict_iterable_results(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = [{"title": "T"}]
        with patch.object(resolver, "_get_search_client", return_value=fake_client):
            ref = resolver._resolve_via_pmc("query")
        assert ref.title == "T"

    def test_non_dict_paper_entry_returns_none(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = {"results": ["not a dict"]}
        with patch.object(resolver, "_get_search_client", return_value=fake_client):
            assert resolver._resolve_via_pmc("query") is None


class TestSearchPmc:
    def test_multiple_papers(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = {
            "results": [
                {"title": "T1", "authorString": "A, B"},
                {"title": "T2", "authorString": ""},
                "not a dict",
            ]
        }
        with patch.object(resolver, "_get_search_client", return_value=fake_client):
            refs = resolver._search_pmc("query", limit=5)
        assert len(refs) == 2
        assert refs[0].title == "T1"
        assert refs[1].authors == []

    def test_falsy_results_returns_empty(self):
        resolver = _resolver()
        fake_client = MagicMock()
        fake_client.search.return_value = None
        with patch.object(resolver, "_get_search_client", return_value=fake_client):
            assert resolver._search_pmc("query") == []


class TestHelpers:
    def test_clean_str_none(self):
        assert ReferenceResolver._clean_str(None) is None

    def test_clean_str_empty_after_strip(self):
        assert ReferenceResolver._clean_str("   ") is None

    def test_clean_str_value(self):
        assert ReferenceResolver._clean_str("  hi  ") == "hi"

    def test_clean_str_non_string_coerced(self):
        assert ReferenceResolver._clean_str(123) == "123"

    def test_safe_int_none(self):
        assert ReferenceResolver._safe_int(None) is None

    def test_safe_int_valid(self):
        assert ReferenceResolver._safe_int("42") == 42

    def test_safe_int_invalid(self):
        assert ReferenceResolver._safe_int("not a number") is None

    def test_extract_year_published_print(self):
        data = {"published_print": {"date-parts": [[2019, 6]]}}
        assert ReferenceResolver._extract_year(data) == 2019

    def test_extract_year_falls_through_keys(self):
        data = {"issued": {"date-parts": [[2018]]}}
        assert ReferenceResolver._extract_year(data) == 2018

    def test_extract_year_no_date_fields(self):
        assert ReferenceResolver._extract_year({}) is None

    def test_extract_year_empty_date_parts(self):
        data = {"created": {"date-parts": []}}
        assert ReferenceResolver._extract_year(data) is None

    def test_extract_year_bad_value(self):
        data = {"created": {"date-parts": [["not-a-year"]]}}
        assert ReferenceResolver._extract_year(data) is None

    def test_parse_author_string_empty(self):
        assert ReferenceResolver._parse_author_string("") == []

    def test_parse_author_string_multiple(self):
        assert ReferenceResolver._parse_author_string("Smith J, Doe A, ") == ["Smith J", "Doe A"]

    def test_crossref_type_to_bibtex_known(self):
        assert ReferenceResolver._crossref_type_to_bibtex("book") == "book"

    def test_crossref_type_to_bibtex_unknown_defaults_to_misc(self):
        assert ReferenceResolver._crossref_type_to_bibtex("something-weird") == "misc"
