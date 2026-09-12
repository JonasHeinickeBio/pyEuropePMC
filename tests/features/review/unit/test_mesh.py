"""Unit tests for pyeuropepmc.features.review.mesh (hermetic, no network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pyeuropepmc.features.review.mesh import (
    MeSHExpander,
    MeSHExpansionResult,
    expand_with_mesh,
    lookup_mesh_descriptor,
    suggest_mesh_terms,
    translate_to_mesh,
)


class TestMeSHExpander:
    def test_expand_known_term(self):
        expander = MeSHExpander()
        result = expander.expand("cancer")
        assert isinstance(result, MeSHExpansionResult)
        assert "Neoplasms" in result.mesh_terms
        assert "cancer" in result.term_suggestions
        assert result.original_query == "cancer"

    def test_expand_unknown_term_passthrough(self):
        expander = MeSHExpander()
        result = expander.expand("xyzzy_unknown_term")
        assert result.mesh_terms == []
        assert "xyzzy_unknown_term" in result.expanded_query

    def test_expand_boolean_query_tokenization(self):
        expander = MeSHExpander()
        result = expander.expand('cancer AND "diabetes" OR (brain)')
        # all three known terms should surface as mesh suggestions
        assert any(t in result.mesh_terms for t in ["Neoplasms", "Diabetes Mellitus", "Brain"])

    def test_tokenize_splits_on_boolean_operators(self):
        expander = MeSHExpander()
        tokens = expander._tokenize("cancer AND brain")
        assert tokens == ["cancer", "brain"]

    def test_tokenize_filters_short_tokens(self):
        expander = MeSHExpander()
        tokens = expander._tokenize("cancer AND x")
        assert "x" not in tokens
        assert "cancer" in tokens

    def test_max_suggestions_limits_output(self):
        expander = MeSHExpander(max_suggestions=1)
        suggestions = expander._suggest_mesh("cancer")
        assert len(suggestions) == 1

    def test_suggest_mesh_api_success(self):
        expander = MeSHExpander(use_api=True)
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = ["Neoplasms", "Tumor"]
        with patch("pyeuropepmc.features.review.mesh.requests.get", return_value=mock_resp):
            suggestions = expander._suggest_mesh("cancer")
        assert suggestions == ["Neoplasms", "Tumor"]

    def test_suggest_mesh_api_non_list_response_returns_empty(self):
        expander = MeSHExpander(use_api=True)
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"unexpected": "shape"}
        with patch("pyeuropepmc.features.review.mesh.requests.get", return_value=mock_resp):
            suggestions = expander._suggest_mesh("cancer")
        # a 200 with a non-list body returns [] directly (no guide fallback)
        assert suggestions == []

    def test_suggest_mesh_api_non_200_falls_back_to_guide(self):
        expander = MeSHExpander(use_api=True)
        mock_resp = MagicMock(status_code=500)
        with patch("pyeuropepmc.features.review.mesh.requests.get", return_value=mock_resp):
            suggestions = expander._suggest_mesh("cancer")
        assert "Neoplasms" in suggestions

    def test_suggest_mesh_api_exception_falls_back_to_guide(self):
        expander = MeSHExpander(use_api=True)
        with patch(
            "pyeuropepmc.features.review.mesh.requests.get", side_effect=RuntimeError("boom")
        ):
            suggestions = expander._suggest_mesh("cancer")
        assert "Neoplasms" in suggestions

    def test_expansion_result_repr(self):
        result = MeSHExpansionResult(
            original_query="q",
            expanded_query="q expanded",
            mesh_terms=["A", "B"],
            term_suggestions={"q": ["A", "B"]},
        )
        text = repr(result)
        assert "q expanded" in text
        assert "A" in text


class TestModuleFunctions:
    def test_expand_with_mesh(self):
        result = expand_with_mesh("diabetes")
        assert "Diabetes Mellitus" in result.mesh_terms

    def test_suggest_mesh_terms(self):
        terms = suggest_mesh_terms("obesity", max_suggestions=2)
        assert len(terms) <= 2
        assert "Obesity" in terms

    def test_translate_to_mesh(self):
        mapping = translate_to_mesh(["cancer", "unknownxyz"])
        assert "cancer" in mapping
        assert "unknownxyz" not in mapping

    def test_lookup_mesh_descriptor_list_response(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = [{"label": "Neoplasms", "ui": "D009369"}]
        with patch("pyeuropepmc.features.review.mesh.requests.get", return_value=mock_resp):
            desc = lookup_mesh_descriptor("Neoplasms")
        assert desc == {"label": "Neoplasms", "ui": "D009369"}

    def test_lookup_mesh_descriptor_dict_response(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"label": "Neoplasms"}
        with patch("pyeuropepmc.features.review.mesh.requests.get", return_value=mock_resp):
            desc = lookup_mesh_descriptor("Neoplasms")
        assert desc == {"label": "Neoplasms"}

    def test_lookup_mesh_descriptor_empty_list(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = []
        with patch("pyeuropepmc.features.review.mesh.requests.get", return_value=mock_resp):
            desc = lookup_mesh_descriptor("Nothing")
        assert desc is None

    def test_lookup_mesh_descriptor_non_200(self):
        mock_resp = MagicMock(status_code=404)
        with patch("pyeuropepmc.features.review.mesh.requests.get", return_value=mock_resp):
            desc = lookup_mesh_descriptor("Nothing")
        assert desc is None

    def test_lookup_mesh_descriptor_exception(self):
        with patch(
            "pyeuropepmc.features.review.mesh.requests.get", side_effect=RuntimeError("boom")
        ):
            desc = lookup_mesh_descriptor("Neoplasms")
        assert desc is None
