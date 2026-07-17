import pytest
from unittest.mock import patch, MagicMock

from pyeuropepmc.agentic.bibliography_tools import (
    bibliography_registry,
    register_all_bibliography_tools,
    bib_parse_string,
    bib_validate,
    bib_is_bibtex,
)
from pyeuropepmc.agentic.registry import ToolRegistry


SAMPLE_BIBTEX = '@article{key2024, title = {Hello}, author = {Smith, John}, year = {2024}}'


class TestBibliographyRegistry:
    def test_registry_populated(self):
        assert len(bibliography_registry.list_all()) >= 12

    def test_registry_contains_expected_tools(self):
        names = {t.name for t in bibliography_registry.list_all()}
        expected = {
            "bib_parse_string", "bib_parse_file", "bib_write_string", "bib_write_file",
            "bib_validate", "bib_merge",
            "ref_resolve_doi", "ref_resolve_pmid", "ref_resolve_arxiv",
            "convert_to_ris", "convert_to_csl",
            "bib_is_bibtex",
            "zotero_list_collections", "zotero_export_collection",
        }
        assert names.issuperset(expected)

    def test_bib_parse_string_tool(self):
        result = bib_parse_string(SAMPLE_BIBTEX)
        assert result["entries_count"] == 1
        assert "key2024" in result["keys"]
        assert result["entries"][0]["entry_type"] == "article"

    def test_bib_parse_string_error(self):
        result = bib_parse_string("not bibtex at all")
        assert "error" in result or result["entries_count"] == 0

    def test_bib_validate_tool(self):
        result = bib_validate({"entries": [{"entry_type": "article", "citation_key": "k", "fields": {}}]})
        assert result["issues_count"] >= 1

    def test_bib_is_bibtex_tool(self):
        assert bib_is_bibtex(SAMPLE_BIBTEX)["is_bibtex"] is True
        assert bib_is_bibtex("plain text")["is_bibtex"] is False

    def test_register_all_bibliography_tools(self):
        target = ToolRegistry()
        result = register_all_bibliography_tools(target)
        assert result is target
        assert len(target.list_all()) >= 12

    def test_register_all_bibliography_tools_no_arg(self):
        result = register_all_bibliography_tools()
        assert result is bibliography_registry
