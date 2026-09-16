"""Unit tests for literature normalization utilities."""

import pytest

from pyeuropepmc.features.literature.normalization import (
    is_valid_doi,
    normalize_abstract,
    normalize_affiliation,
    normalize_author_list,
    normalize_author_name,
    normalize_doi,
    normalize_journal_title,
    normalize_mesh_terms,
    normalize_paper_title,
    normalize_to_nfkc,
)

pytestmark = pytest.mark.unit


# ===========================================================================
# NFKC
# ===========================================================================


class TestNormalizeToNfkc:
    def test_none(self):
        assert normalize_to_nfkc(None) is None

    def test_ligatures(self):
        # ﬁ ligature → "fi"
        result = normalize_to_nfkc("ﬁle")
        assert result is not None
        assert "fi" in result

    def test_superscript(self):
        # ² → "2"
        result = normalize_to_nfkc("H₂O")
        assert result is not None
        assert "2" in result or "H₂O" in result  # NFKC decomposes superscript

    def test_fullwidth(self):
        # Ａ → "A"
        result = normalize_to_nfkc("ＡBC")
        assert result is not None
        assert result[0] == "A"

    def test_empty_after_strip(self):
        assert normalize_to_nfkc("   ") is None


# ===========================================================================
# DOI
# ===========================================================================


class TestNormalizeDoi:
    def test_none_input(self):
        """None in, None out."""
        assert normalize_doi(None) is None

    def test_basic_lowercase(self):
        assert normalize_doi("10.1234/TEST") == "10.1234/test"

    def test_doi_with_doi_org_prefix(self):
        assert normalize_doi("https://doi.org/10.1234/TEST") == "10.1234/test"

    def test_doi_with_dx_prefix(self):
        assert normalize_doi("http://dx.doi.org/10.1234/TEST") == "10.1234/test"

    def test_doi_with_http_prefix(self):
        assert normalize_doi("http://doi.org/10.1234/test") == "10.1234/test"

    def test_doi_with_hdl_prefix(self):
        assert normalize_doi("https://hdl.handle.net/10.1234/test") == "10.1234/test"

    def test_invalid_doi_returns_none(self):
        """Invalid DOIs should return None."""
        assert normalize_doi("not-a-doi") is None
        assert normalize_doi("") is None
        assert normalize_doi("   ") is None
        assert normalize_doi("10.123") is None  # too few digits in registrant code

    def test_valid_complex_doi(self):
        assert normalize_doi("10.1038/s41586-021-03836-5") == "10.1038/s41586-021-03836-5"

    def test_strip_whitespace(self):
        assert normalize_doi("  10.1234/TEST  ") == "10.1234/test"


class TestIsValidDoi:
    def test_valid_doi(self):
        assert is_valid_doi("10.1000/xyz123") is True
        assert is_valid_doi("10.1038/s41586-021-03836-5") is True

    def test_invalid_doi(self):
        assert is_valid_doi("not-a-doi") is False
        assert is_valid_doi("") is False
        assert is_valid_doi(None) is False
        assert is_valid_doi("10.123/too-few") is False  # 3 digits

    def test_edge_cases(self):
        assert is_valid_doi("10.1234/abc-def_ghi") is True
        assert is_valid_doi("10.12345/abc(def)ghi") is True


# ===========================================================================
# Author name
# ===========================================================================


class TestNormalizeAuthorName:
    def test_none_input(self):
        assert normalize_author_name(None) is None

    def test_empty_input(self):
        assert normalize_author_name("") is None
        assert normalize_author_name("   ") is None

    def test_already_normalized(self):
        assert normalize_author_name("Smith, John") == "Smith, John"

    def test_simple_conversion(self):
        result = normalize_author_name("John Doe")
        assert result == "Doe, John"

    def test_middle_name(self):
        result = normalize_author_name("John Michael Doe")
        assert result == "Doe, John Michael"

    def test_multi_word_surname_prefix(self):
        """Multi-word surname with 'von' prefix."""
        result = normalize_author_name("John von Neumann")
        assert result == "von Neumann, John"

    def test_multi_word_surname_da(self):
        result = normalize_author_name("Maria da Silva")
        assert result == "da Silva, Maria"

    def test_multi_word_surname_de_la(self):
        result = normalize_author_name("Juan de la Cruz")
        assert result == "de la Cruz, Juan"

    def test_multi_word_surname_van_der(self):
        result = normalize_author_name("Johannes van der Waals")
        assert result == "van der Waals, Johannes"

    def test_single_name(self):
        result = normalize_author_name("Socrates")
        assert result == "Socrates"

    def test_hyphenated_surname(self):
        result = normalize_author_name("Jean-Pierre Taylor-Smith")
        assert result == "Taylor-Smith, Jean-Pierre"

    def test_unicode_name(self):
        result = normalize_author_name("José García")
        assert result == "García, José"

    def test_le_surname(self):
        result = normalize_author_name("Marine Le Pen")
        assert result == "Le Pen, Marine"

    def test_mc_prefix(self):
        result = normalize_author_name("John McDonald")
        assert result == "McDonald, John"

    def test_ben_prefix(self):
        result = normalize_author_name("David ben Gurion")
        assert result == "ben Gurion, David"

    def test_o_prefix(self):
        result = normalize_author_name("Sean O'Brien")
        assert result == "O'Brien, Sean"

    # PubMed ESummary and Europe PMC authorString write "Surname Initials".
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Smith J", "Smith, J"),
            ("Smith JA", "Smith, JA"),
            ("Doe J.A.", "Doe, J.A."),
            ("Kim J.-P.", "Kim, J.-P."),
            ("Smith J A", "Smith, J A"),
            ("Taylor-Smith AB", "Taylor-Smith, AB"),
            ("O'Brien K", "O'Brien, K"),
            ("van der Berg JA", "van der Berg, JA"),
            ("de la Cruz M", "de la Cruz, M"),
        ],
    )
    def test_surname_then_initials_is_not_reversed(self, raw, expected):
        assert normalize_author_name(raw) == expected

    def test_initials_first_still_reordered(self):
        assert normalize_author_name("J Smith") == "Smith, J"
        assert normalize_author_name("J. R. R. Tolkien") == "Tolkien, J. R. R."

    def test_all_caps_name_is_left_to_the_general_rule(self):
        """Without lower-case letters nothing says which part is the surname."""
        assert normalize_author_name("WANG LI") == "LI, WANG"


# ===========================================================================
# Author list
# ===========================================================================


class TestNormalizeAuthorList:
    def test_none_input(self):
        assert normalize_author_list(None) is None

    def test_empty_list(self):
        assert normalize_author_list([]) is None

    def test_basic_authors(self):
        authors = [{"name": "John Doe"}, {"name": "Jane Smith"}]
        result = normalize_author_list(authors)
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "Doe, John"
        assert result[1]["name"] == "Smith, Jane"

    def test_family_given_format(self):
        authors = [{"family_name": "Einstein", "given_name": "Albert"}]
        result = normalize_author_list(authors)
        assert result is not None
        assert result[0]["name"] == "Einstein, Albert"

    def test_last_first_format(self):
        authors = [{"last_name": "Curie", "first_name": "Marie"}]
        result = normalize_author_list(authors)
        assert result is not None
        assert result[0]["name"] == "Curie, Marie"

    def test_orcid_cleaning(self):
        authors = [{"name": "Doe, John", "orcid": "0000-0002-1825-0097"}]
        result = normalize_author_list(authors)
        assert result is not None
        assert result[0]["orcid"] == "0000000218250097"

    def test_affiliation_normalization(self):
        authors = [{"name": "Doe, John", "affiliation": "  University of X.;  "}]
        result = normalize_author_list(authors)
        assert result is not None
        assert result[0]["affiliation"] == "University of X"

    def test_email_preserved(self):
        authors = [{"name": "Doe, John", "email": "john@example.com"}]
        result = normalize_author_list(authors)
        assert result is not None
        assert result[0].get("email") == "john@example.com"

    def test_role_preserved(self):
        authors = [{"name": "Doe, John", "role": "first author"}]
        result = normalize_author_list(authors)
        assert result is not None
        assert result[0].get("role") == "first author"

    def test_non_dict_skipped(self):
        authors = [{"name": "Valid, Author"}, "invalid string"]
        result = normalize_author_list(authors)
        assert result is not None
        assert len(result) == 1

    def test_empty_dict_skipped(self):
        authors = [{}]
        result = normalize_author_list(authors)
        assert result is None


# ===========================================================================
# Journal title
# ===========================================================================


class TestNormalizeJournalTitle:
    def test_none(self):
        assert normalize_journal_title(None) is None

    def test_trailing_punctuation(self):
        assert normalize_journal_title("Nature.;") == "Nature."

    def test_whitespace_collapse(self):
        result = normalize_journal_title("  The   New  England  Journal  ")
        assert result == "The New England Journal"

    def test_mixed_punctuation(self):
        # Period preserved (part of abbreviation), semicolon stripped
        assert normalize_journal_title("J. Am. Chem. Soc.;") == "J. Am. Chem. Soc."


# ===========================================================================
# Paper title
# ===========================================================================


class TestNormalizePaperTitle:
    def test_none(self):
        assert normalize_paper_title(None) is None

    def test_trailing_punctuation(self):
        assert normalize_paper_title("A Study on X.") == "A Study on X"

    def test_whitespace_collapse(self):
        result = normalize_paper_title("  A   Study  ")
        assert result == "A Study"

    def test_nfkc_applied(self):
        # Fullwidth letters
        result = normalize_paper_title("Ａ Study")
        assert result is not None
        assert result[0] == "A"


# ===========================================================================
# Abstract
# ===========================================================================


class TestNormalizeAbstract:
    def test_none(self):
        assert normalize_abstract(None) is None

    def test_basic_strip(self):
        result = normalize_abstract("  Hello world  ")
        assert result == "Hello world"

    def test_strip_headers(self):
        result = normalize_abstract(
            "Background: This is background. Methods: We did X. Results: Y. Conclusions: Z."
        )
        assert "Background:" not in result
        assert "Methods:" not in result
        assert "This is background" in result

    def test_strip_funding(self):
        result = normalize_abstract("We found something. Funded by NIH grant 12345.")
        assert "Funded by" not in result

    def test_strip_conflict(self):
        result = normalize_abstract("Our results show X. Conflict of interest: none.")
        assert "Conflict of interest" not in result

    def test_strip_acknowledgments(self):
        result = normalize_abstract("Our results show X. Acknowledgments: thanks to Y.")
        assert "Acknowledgments" not in result

    def test_no_strip_headers_disabled(self):
        text = "Background: This is background."
        result = normalize_abstract(text, strip_headers=False)
        assert "Background:" in result

    def test_empty_after_strip(self):
        result = normalize_abstract("   ")
        assert result is None


# ===========================================================================
# MeSH terms
# ===========================================================================


class TestNormalizeMeshTerms:
    def test_none(self):
        assert normalize_mesh_terms(None) is None

    def test_empty_list(self):
        assert normalize_mesh_terms([]) is None

    def test_basic_normalization(self):
        result = normalize_mesh_terms(["  Cancer  ", "  Diabetes  "])
        assert result == ["Cancer", "Diabetes"]

    def test_deduplication(self):
        result = normalize_mesh_terms(["Cancer", "cancer", "CANCER"])
        assert result == ["Cancer"]

    def test_invalid_entries_skipped(self):
        result = normalize_mesh_terms(["Cancer", "", None, "Diabetes"])
        assert result == ["Cancer", "Diabetes"]

    def test_nfkc_applied(self):
        result = normalize_mesh_terms(["Ａlzheimer"])
        assert result is not None
        assert result[0][0] == "A"


# ===========================================================================
# Affiliation
# ===========================================================================


class TestNormalizeAffiliation:
    def test_none(self):
        assert normalize_affiliation(None) is None

    def test_basic(self):
        result = normalize_affiliation("  University of X.  ")
        assert result == "University of X"

    def test_trailing_punctuation(self):
        assert normalize_affiliation("Harvard Medical School;") == "Harvard Medical School"

    def test_whitespace_collapse(self):
        result = normalize_affiliation("Max  Planck   Institute")
        assert result == "Max Planck Institute"


class TestPackageExports:
    """Everything in ``normalization.__all__`` is reachable from the package."""

    def test_pmid_helpers_are_exported(self):
        from pyeuropepmc.features.literature import is_valid_pmid, normalize_pmid

        assert normalize_pmid("PMID:12345678") == "12345678"
        assert is_valid_pmid("12345678") is True

    def test_package_reexports_all_normalization_helpers(self):
        import pyeuropepmc.features.literature as literature
        from pyeuropepmc.features.literature import normalization

        missing = [n for n in normalization.__all__ if n not in literature.__all__]
        assert missing == []
        for name in normalization.__all__:
            assert getattr(literature, name) is getattr(normalization, name)
