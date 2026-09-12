"""Unit tests for DataMerger enrichment data merging."""

from pyeuropepmc.features.enrich.data_merger import DataMerger


class TestDataMerger:
    """Tests for DataMerger."""

    def setup_method(self):
        """Set up test fixtures."""
        self.merger = DataMerger()

    # ---------- _merge_title ----------

    def test_merge_title_crossref_priority(self):
        """Title picks crossref over openalex and semantic_scholar."""
        results = {
            "crossref": {"title": "Crossref Title"},
            "openalex": {"title": "OpenAlex Title"},
            "semantic_scholar": {"title": "SS Title"},
        }
        merged = self.merger._merge_title(results)
        assert merged == {"title": "Crossref Title"}

    def test_merge_title_openalex_fallback(self):
        """Title picks openalex when crossref missing."""
        results = {
            "openalex": {"title": "OpenAlex Title"},
            "semantic_scholar": {"title": "SS Title"},
        }
        merged = self.merger._merge_title(results)
        assert merged == {"title": "OpenAlex Title"}

    def test_merge_title_semantic_scholar_fallback(self):
        """Title picks semantic_scholar when higher priority missing."""
        results = {
            "semantic_scholar": {"title": "SS Title"},
        }
        merged = self.merger._merge_title(results)
        assert merged == {"title": "SS Title"}

    def test_merge_title_empty(self):
        """Title returns empty dict when no source has title."""
        results = {
            "crossref": {},
            "openalex": {},
            "semantic_scholar": {},
        }
        merged = self.merger._merge_title(results)
        assert merged == {}

    def test_merge_title_missing_source(self):
        """Title returns empty dict when sources absent."""
        results = {}
        merged = self.merger._merge_title(results)
        assert merged == {}

    def test_merge_title_non_dict_source(self):
        """Title handles non-dict source data gracefully."""
        results = {"crossref": "not a dict"}
        merged = self.merger._merge_title(results)
        assert merged == {}

    # ---------- _merge_abstract ----------

    def test_merge_abstract_crossref_priority(self):
        """Abstract picks crossref over semantic_scholar."""
        results = {
            "crossref": {"abstract": "Crossref abstract."},
            "semantic_scholar": {"abstract": "SS abstract."},
        }
        merged = self.merger._merge_abstract(results)
        assert merged == {"abstract": "Crossref abstract."}

    def test_merge_abstract_semantic_scholar_fallback(self):
        """Abstract picks semantic_scholar when crossref missing."""
        results = {
            "semantic_scholar": {"abstract": "SS abstract."},
        }
        merged = self.merger._merge_abstract(results)
        assert merged == {"abstract": "SS abstract."}

    def test_merge_abstract_empty(self):
        """Abstract returns empty dict when no source provides one."""
        results = {"crossref": {}, "semantic_scholar": {}}
        merged = self.merger._merge_abstract(results)
        assert merged == {}

    # ---------- _merge_journal ----------

    def test_merge_journal_crossref_priority(self):
        """Journal picks crossref over openalex.venue."""
        results = {
            "crossref": {"journal": "Nature"},
            "openalex": {"venue": {"display_name": "Nature Venue"}},
        }
        merged = self.merger._merge_journal(results)
        assert merged == {"journal": "Nature"}

    def test_merge_journal_openalex_venue(self):
        """Journal picks openalex venue when crossref missing."""
        results = {
            "openalex": {"venue": {"display_name": "Nature"}},
        }
        merged = self.merger._merge_journal(results)
        assert merged == {"journal": {"display_name": "Nature"}}

    def test_merge_journal_empty(self):
        """Journal returns empty dict when no source has it."""
        results = {"crossref": {}, "openalex": {}}
        merged = self.merger._merge_journal(results)
        assert merged == {}

    def test_merge_journal_falls_through_crossref_no_journal(self):
        """Journal falls through to openalex when crossref has no journal key."""
        results = {
            "crossref": {"title": "Something"},
            "openalex": {"venue": "Science"},
        }
        merged = self.merger._merge_journal(results)
        assert merged == {"journal": "Science"}

    # ---------- _merge_publication_date ----------

    def test_merge_publication_date_crossref(self):
        """Publication date prefers crossref."""
        results = {
            "crossref": {"publication_date": "2021-06-15"},
            "openalex": {"publication_date": "2020-01-01"},
        }
        merged = self.merger._merge_publication_date(results)
        assert merged == {"publication_date": "2021-06-15"}

    def test_merge_publication_date_openalex_date(self):
        """Publication date falls back to openalex date."""
        results = {
            "openalex": {"publication_date": "2020-01-01"},
        }
        merged = self.merger._merge_publication_date(results)
        assert merged == {"publication_date": "2020-01-01"}

    def test_merge_publication_date_openalex_year(self):
        """Publication date falls back to openalex publication_year."""
        results = {
            "openalex": {"publication_year": 2020},
        }
        merged = self.merger._merge_publication_date(results)
        assert merged == {"publication_year": 2020}

    def test_merge_publication_date_openalex_date_preferred_over_year(self):
        """openalex publication_date preferred over publication_year."""
        results = {
            "openalex": {"publication_date": "2020-06-01", "publication_year": 2019},
        }
        merged = self.merger._merge_publication_date(results)
        assert merged == {"publication_date": "2020-06-01"}

    def test_merge_publication_date_empty(self):
        """Publication date returns empty when no source."""
        merged = self.merger._merge_publication_date({})
        assert merged == {}

    # ---------- _merge_citations ----------

    def test_merge_citations_max(self):
        """Citations uses max count from all sources."""
        results = {
            "crossref": {"citation_count": 10},
            "semantic_scholar": {"citation_count": 20},
            "openalex": {"citation_count": 15},
        }
        merged = self.merger._merge_citations(results)
        assert merged["citation_count"] == 20
        assert len(merged["citation_counts"]) == 3

    def test_merge_citations_single_source(self):
        """Citations works with single source."""
        results = {
            "crossref": {"citation_count": 5},
        }
        merged = self.merger._merge_citations(results)
        assert merged["citation_count"] == 5
        assert len(merged["citation_counts"]) == 1

    def test_merge_citations_empty(self):
        """Citations returns empty when no citation counts."""
        results = {"crossref": {}, "semantic_scholar": {}, "openalex": {}}
        merged = self.merger._merge_citations(results)
        assert merged == {}

    def test_merge_citations_non_dict_source(self):
        """Citations handles non-dict source."""
        results = {"crossref": "string", "semantic_scholar": None}
        merged = self.merger._merge_citations(results)
        assert merged == {}

    def test_merge_citations_some_none_counts(self):
        """Citations ignores None counts."""
        results = {
            "crossref": {"citation_count": None},
            "semantic_scholar": {"citation_count": 7},
        }
        merged = self.merger._merge_citations(results)
        assert merged["citation_count"] == 7

    # ---------- _merge_oa_info ----------

    def test_merge_oa_info_unpaywall_primary(self):
        """OA info uses unpaywall as primary source."""
        results = {
            "unpaywall": {
                "is_oa": True,
                "oa_status": "gold",
                "best_oa_location": {"url": "https://example.com/paper"},
            },
            "openalex": {"is_oa": False, "oa_status": "closed"},
        }
        merged = self.merger._merge_oa_info(results)
        assert merged["is_oa"] is True
        assert merged["oa_status"] == "gold"
        assert merged["oa_url"] == "https://example.com/paper"

    def test_merge_oa_info_unpaywall_no_best_location(self):
        """OA info handles missing best_oa_location."""
        results = {
            "unpaywall": {
                "is_oa": True,
                "oa_status": "hybrid",
            },
        }
        merged = self.merger._merge_oa_info(results)
        assert merged["is_oa"] is True
        assert merged["oa_status"] == "hybrid"
        assert "oa_url" not in merged

    def test_merge_oa_info_openalex_fallback(self):
        """OA info falls back to openalex."""
        results = {
            "openalex": {
                "is_oa": True,
                "oa_status": "green",
                "oa_url": "https://openalex.org/paper",
            },
        }
        merged = self.merger._merge_oa_info(results)
        assert merged["is_oa"] is True
        assert merged["oa_status"] == "green"
        assert merged["oa_url"] == "https://openalex.org/paper"

    def test_merge_oa_info_empty(self):
        """OA info returns empty when no source."""
        merged = self.merger._merge_oa_info({})
        assert merged == {}

    # ---------- _merge_additional_metrics ----------

    def test_merge_additional_metrics_semantic_scholar(self):
        """Additional metrics extracted from semantic_scholar only."""
        results = {
            "semantic_scholar": {
                "influential_citation_count": 15,
                "fields_of_study": ["Computer Science", "Biology"],
            },
        }
        merged = self.merger._merge_additional_metrics(results)
        assert merged["influential_citation_count"] == 15
        assert merged["fields_of_study"] == ["Computer Science", "Biology"]

    def test_merge_additional_metrics_empty(self):
        """Additional metrics returns empty when no semantic_scholar data."""
        merged = self.merger._merge_additional_metrics({})
        assert merged == {}

    def test_merge_additional_metrics_none_values(self):
        """Additional metrics returns dict with None values when keys absent."""
        results = {
            "semantic_scholar": {"other_key": "value"},
        }
        merged = self.merger._merge_additional_metrics(results)
        assert merged["influential_citation_count"] is None
        assert merged["fields_of_study"] is None

    # ---------- _merge_topics ----------

    def test_merge_topics_openalex(self):
        """Topics extracted from openalex only."""
        results = {
            "openalex": {"topics": [{"id": "T1", "display_name": "Machine Learning"}]},
        }
        merged = self.merger._merge_topics(results)
        assert merged["topics"] == [{"id": "T1", "display_name": "Machine Learning"}]

    def test_merge_topics_empty(self):
        """Topics returns empty when no openalex data."""
        merged = self.merger._merge_topics({})
        assert merged == {}

    # ---------- _merge_license ----------

    def test_merge_license_crossref(self):
        """License extracted from crossref only."""
        results = {
            "crossref": {"license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}]},
        }
        merged = self.merger._merge_license(results)
        assert merged["license"] == [{"URL": "https://creativecommons.org/licenses/by/4.0/"}]

    def test_merge_license_empty(self):
        """License returns empty when crossref missing or no license key."""
        merged = self.merger._merge_license({"crossref": {}})
        assert merged == {}

    # ---------- _merge_funders ----------

    def test_merge_funders_crossref(self):
        """Funders extracted from crossref."""
        results = {
            "crossref": {
                "funders": [
                    {"name": "NIH", "award": ["R01"]},
                ]
            },
        }
        merged = self.merger._merge_funders(results)
        assert merged["funding"] == [{"name": "NIH", "award": ["R01"]}]

    def test_merge_funders_empty(self):
        """Funders returns empty when crossref missing or no funders key."""
        merged = self.merger._merge_funders({"crossref": {}})
        assert merged == {}

    # ---------- _merge_external_ids ----------

    def test_merge_external_ids_semantic_scholar(self):
        """External IDs from semantic_scholar mapped correctly."""
        results = {
            "semantic_scholar": {
                "external_ids": {
                    "CorpusId": "12345",
                    "PubMed": "67890",
                },
            },
        }
        merged = self.merger._merge_external_ids(results)
        assert merged["external_ids"]["semantic_scholar_corpus_id"] == "12345"
        assert merged["external_ids"]["pmid"] == "67890"

    def test_merge_external_ids_pmid_normalization(self):
        """PMIDs from semantic_scholar are normalized from URLs."""
        results = {
            "semantic_scholar": {
                "external_ids": {
                    "PubMed": "https://pubmed.ncbi.nlm.nih.gov/12345",
                },
            },
        }
        merged = self.merger._merge_external_ids(results)
        assert merged["external_ids"]["pmid"] == "12345"

    def test_merge_external_ids_openalex(self):
        """External IDs from openalex mapped correctly."""
        results = {
            "openalex": {
                "ids": {
                    "openalex": "W12345",
                    "doi": "https://doi.org/10.1000/test",
                    "pmid": "https://pubmed.ncbi.nlm.nih.gov/99999",
                },
            },
        }
        merged = self.merger._merge_external_ids(results)
        assert merged["external_ids"]["openalex_id"] == "W12345"
        assert merged["external_ids"]["doi"] == "10.1000/test"
        assert merged["external_ids"]["pmid"] == "99999"

    def test_merge_external_ids_crossref_doi(self):
        """DOI from crossref is normalized."""
        results = {
            "crossref": {"DOI": "https://doi.org/10.1001/abc"},
        }
        merged = self.merger._merge_external_ids(results)
        assert merged["external_ids"]["doi"] == "10.1001/abc"

    def test_merge_external_ids_doi_conflict(self):
        """DOI conflict between sources is recorded."""
        results = {
            "semantic_scholar": {
                "external_ids": {
                    "CorpusId": "1",
                },
            },
            "openalex": {
                "ids": {
                    "doi": "https://doi.org/10.1000/alpha",
                },
            },
            "crossref": {"DOI": "https://doi.org/10.1000/beta"},
        }
        merged = self.merger._merge_external_ids(results)
        assert "doi" in merged["external_id_conflicts"]
        assert len(merged["external_id_conflicts"]["doi"]) >= 1

    def test_merge_external_ids_pmid_conflict(self):
        """PMID conflict between sources is recorded."""
        results = {
            "semantic_scholar": {
                "external_ids": {
                    "PubMed": "11111",
                },
            },
            "openalex": {
                "ids": {
                    "pmid": "https://pubmed.ncbi.nlm.nih.gov/22222",
                },
            },
        }
        merged = self.merger._merge_external_ids(results)
        assert "pmid" in merged["external_id_conflicts"]

    def test_merge_external_ids_no_conflict_same_values(self):
        """No conflict when sources provide same normalized value."""
        results = {
            "semantic_scholar": {
                "external_ids": {
                    "PubMed": "12345",
                },
            },
            "openalex": {
                "ids": {
                    "pmid": "https://pubmed.ncbi.nlm.nih.gov/12345",
                },
            },
        }
        merged = self.merger._merge_external_ids(results)
        assert "external_id_conflicts" not in merged
        assert merged["external_ids"]["pmid"] == "12345"

    def test_merge_external_ids_empty(self):
        """External IDs returns empty when no sources."""
        merged = self.merger._merge_external_ids({})
        assert merged == {}

    # ---------- _merge_bibliographic_info ----------

    def test_merge_bibliographic_info_crossref_primary(self):
        """Bibliographic info uses crossref as primary with gaps filled."""
        results = {
            "crossref": {
                "volume": "10",
                "issue": "2",
                "page": "100-110",
                "publisher": "Test Publisher",
                "issn": "1234-5678",
                "type": "journal-article",
            },
            "openalex": {
                "biblio": {
                    "volume": "99",
                    "first_page": "1",
                },
            },
        }
        merged = self.merger._merge_bibliographic_info(results)
        biblio = merged["biblio"]
        assert biblio["volume"] == "10"  # crossref wins
        assert biblio["issue"] == "2"
        assert biblio["pages"] == "100-110"
        assert biblio["publisher"] == "Test Publisher"
        assert biblio["issn"] == "1234-5678"
        assert biblio["type"] == "journal-article"
        assert biblio["first_page"] == "1"  # openalex fills gap

    def test_merge_bibliographic_info_openalex_fills_gaps(self):
        """OpenAlex fills gaps when crossref is missing fields."""
        results = {
            "crossref": {"publisher": "Test Pub"},
            "openalex": {
                "biblio": {
                    "volume": "20",
                    "issue": "3",
                    "first_page": "50",
                    "last_page": "60",
                },
            },
        }
        merged = self.merger._merge_bibliographic_info(results)
        biblio = merged["biblio"]
        assert biblio["volume"] == "20"
        assert biblio["issue"] == "3"
        assert biblio["publisher"] == "Test Pub"

    def test_merge_bibliographic_info_semantic_scholar_fills_gaps(self):
        """Semantic Scholar journal fills volume/pages gaps."""
        results = {
            "openalex": {
                "biblio": {
                    "volume": "30",
                },
            },
            "semantic_scholar": {
                "journal": {
                    "pages": "200-210",
                    "volume": "99",
                },
            },
        }
        merged = self.merger._merge_bibliographic_info(results)
        biblio = merged["biblio"]
        assert biblio["volume"] == "30"  # openalex first
        assert biblio["pages"] == "200-210"  # SS fills gap

    def test_merge_bibliographic_info_empty(self):
        """Bibliographic info returns empty when no sources."""
        merged = self.merger._merge_bibliographic_info({})
        assert merged == {}

    # ---------- _merge_references ----------

    def test_merge_references_crossref_count(self):
        """References count from crossref."""
        results = {
            "crossref": {"references_count": 25},
        }
        merged = self.merger._merge_references(results)
        assert merged["references"]["count"] == 25

    def test_merge_references_max_of_counts(self):
        """References count is max of all sources."""
        results = {
            "crossref": {"references_count": 25},
            "semantic_scholar": {"reference_count": 30},
            "openalex": {"referenced_works_count": 20},
        }
        merged = self.merger._merge_references(results)
        assert merged["references"]["count"] == 30

    def test_merge_references_openalex_additional(self):
        """OpenAlex adds cited_by_count and related_works."""
        results = {
            "openalex": {
                "cited_by_count": 100,
                "related_works": ["W1", "W2"],
            },
        }
        merged = self.merger._merge_references(results)
        assert merged["references"]["cited_by_count"] == 100
        assert merged["references"]["related_works"] == ["W1", "W2"]

    def test_merge_references_empty(self):
        """References returns empty when no source provides data."""
        merged = self.merger._merge_references({})
        assert merged == {}

    # ---------- _merge_authors ----------

    def test_merge_authors_crossref_authors(self):
        """Authors from crossref are processed."""
        results = {
            "crossref": {
                "authors": [
                    {"name": "Doe, John", "given": "John", "family": "Doe", "sequence": "first"},
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert merged_authors is not None
        assert merged_authors[0]["name"] == "Doe, John"
        assert merged_authors[0]["sources"] == ["crossref"]
        assert merged_authors[0]["given_name"] == "John"

    def test_merge_authors_openalex_authors(self):
        """Authors from openalex are processed with institutions."""
        results = {
            "openalex": {
                "authors": [
                    {
                        "display_name": "Smith, Jane",
                        "id": "A123",
                        "orcid": "0000-0001-2345-6789",
                        "institutions": [
                            {
                                "id": "I123",
                                "display_name": "MIT",
                                "country": "US",
                                "ror_id": "https://ror.org/01abc",
                            },
                        ],
                        "position": "first",
                    },
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert merged_authors is not None
        assert merged_authors[0]["name"] == "Smith, Jane"
        assert merged_authors[0]["openalex_id"] == "A123"
        assert merged_authors[0]["orcid"] == "0000-0001-2345-6789"
        assert merged_authors[0]["institutions"][0]["display_name"] == "MIT"

    def test_merge_authors_semantic_scholar_authors(self):
        """Authors from semantic_scholar are processed with affiliations."""
        results = {
            "semantic_scholar": {
                "authors": [
                    {
                        "name": "Brown, Bob",
                        "author_id": "456",
                        "affiliations": ["Stanford"],
                    },
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert merged_authors is not None
        assert merged_authors[0]["name"] == "Brown, Bob"
        assert merged_authors[0]["semantic_scholar_id"] == "456"
        assert merged_authors[0]["affiliations"] == [{"name": "Stanford"}]

    def test_merge_authors_semantic_scholar_dict_affiliations(self):
        """Semantic Scholar handles dict affiliations."""
        results = {
            "semantic_scholar": {
                "authors": [
                    {
                        "name": "Lee, Alice",
                        "affiliations": [{"name": "Oxford", "department": "Physics"}],
                    },
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert merged_authors[0]["affiliations"] == [{"name": "Oxford", "department": "Physics"}]

    def test_merge_authors_datacite_authors(self):
        """Authors from datacite are processed."""
        results = {
            "datacite": {
                "creators": [
                    {
                        "name": "Wilson, Eve",
                        "given_name": "Eve",
                        "family_name": "Wilson",
                        "orcid": "0000-0002-9876-5432",
                    },
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert merged_authors is not None
        assert merged_authors[0]["name"] == "Wilson, Eve"
        assert merged_authors[0]["sources"] == ["datacite"]
        assert merged_authors[0]["orcid"] == "0000-0002-9876-5432"

    def test_merge_authors_dedup_by_name(self):
        """Same author from multiple sources is deduplicated."""
        results = {
            "crossref": {
                "authors": [
                    {"name": "Doe, John", "given": "John", "family": "Doe", "sequence": "first"},
                ],
            },
            "openalex": {
                "authors": [
                    {
                        "display_name": "Doe, John",
                        "orcid": "0000-0001-1234-5678",
                        "institutions": [{"display_name": "Harvard"}],
                    },
                ],
            },
            "semantic_scholar": {
                "authors": [
                    {"name": "Doe, John", "author_id": "789"},
                ],
            },
            "datacite": {
                "creators": [
                    {
                        "name": "Doe, John",
                        "orcid": "0000-0001-1234-5678",
                    },
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert len(merged_authors) == 1
        author = merged_authors[0]
        assert author["orcid"] == "0000-0001-1234-5678"
        assert "crossref" in author["sources"]
        assert "openalex" in author["sources"]  # crossref+openalex gets sorted first
        assert author["given_name"] == "John"
        assert author["family_name"] == "Doe"

    def test_merge_authors_sorted_by_source_count(self):
        """Authors sorted by number of sources descending."""
        results = {
            "crossref": {
                "authors": [
                    {"name": "Alpha", "given": "A", "family": "Alpha", "sequence": "first"},
                ],
            },
            "openalex": {
                "authors": [
                    {"display_name": "Alpha", "orcid": "0000-0001-1111-1111"},
                    {"display_name": "Beta", "orcid": "0000-0002-2222-2222"},
                ],
            },
            "semantic_scholar": {
                "authors": [
                    {"name": "Alpha", "author_id": "A1"},
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert len(merged_authors) == 2
        assert merged_authors[0]["name"] == "Alpha"  # 3 sources, sorted first
        assert merged_authors[1]["name"] == "Beta"  # 1 source

    def test_merge_authors_empty(self):
        """Authors returns None when no sources."""
        merged_authors = self.merger._merge_authors({})
        assert merged_authors is None

    def test_merge_authors_non_list_data(self):
        """Authors handles non-list author data gracefully."""
        results = {
            "crossref": {"authors": "not a list"},
        }
        merged_authors = self.merger._merge_authors(results)
        assert merged_authors is None

    def test_merge_authors_empty_name_skipped(self):
        """Authors with empty name are skipped."""
        results = {
            "crossref": {
                "authors": [
                    {"name": "", "given": "John", "family": "Doe"},
                    {"name": "Real Author"},
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert len(merged_authors) == 1
        assert merged_authors[0]["name"] == "Real Author"

    def test_merge_authors_fields_updated_on_dedup(self):
        """Existing author fields updated when deduping."""
        results = {
            "openalex": {
                "authors": [
                    {
                        "display_name": "No ORCID",
                        "institutions": [{"display_name": "MIT"}],
                    },
                ],
            },
            "semantic_scholar": {
                "authors": [
                    {
                        "name": "No ORCID",
                        "author_id": "S1",
                        "affiliations": ["MIT"],
                    },
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert len(merged_authors) == 1
        author = merged_authors[0]
        assert author["semantic_scholar_id"] == "S1"

    def test_merge_authors_crossref_with_orcid_update(self):
        """ORCID from later source fills in when crossref entry exists."""
        results = {
            "crossref": {
                "authors": [{"name": "Author One", "given": "A", "family": "One"}],
            },
            "datacite": {
                "creators": [
                    {
                        "name": "Author One",
                        "orcid": "0000-0003-3333-3333",
                    },
                ],
            },
        }
        merged_authors = self.merger._merge_authors(results)
        assert merged_authors[0]["orcid"] == "0000-0003-3333-3333"

    # ---------- _merge_authors_field ----------

    def test_merge_authors_field(self):
        """_merge_authors_field wraps _merge_authors into authors key."""
        results = {
            "crossref": {
                "authors": [{"name": "Test Author"}],
            },
        }
        merged = self.merger._merge_authors_field(results)
        assert "authors" in merged
        assert merged["authors"][0]["name"] == "Test Author"

    def test_merge_authors_field_empty(self):
        """_merge_authors_field returns empty when no authors."""
        merged = self.merger._merge_authors_field({})
        assert merged == {}

    # ---------- _apply_ror_enrichment_to_authors ----------

    def test_ror_enrichment_applied_to_authors(self):
        """ROR enrichment adds data to author institutions."""
        merged = {
            "authors": [
                {
                    "name": "Test Author",
                    "institutions": [
                        {
                            "display_name": "MIT",
                            "ror_id": "https://ror.org/01abc",
                        },
                    ],
                },
            ],
        }
        results = {
            "ror": {
                "https://ror.org/01abc": {
                    "country": "United States",
                    "country_code": "US",
                    "city": "Cambridge",
                    "latitude": 42.36,
                    "longitude": -71.09,
                    "types": ["Education"],
                    "website": "https://mit.edu",
                    "established": 1861,
                    "external_ids": [
                        {
                            "type": "wikidata",
                            "preferred": "Q49108",
                            "all": ["Q49108"],
                        },
                    ],
                    "relationships": [{"type": "parent", "label": "MIT System"}],
                    "domains": ["education"],
                },
            },
        }
        self.merger._apply_ror_enrichment_to_authors(merged, results)
        inst = merged["authors"][0]["institutions"][0]
        assert inst["ror_enriched"] is True
        assert inst["country"] == "United States"
        assert inst["country_code"] == "US"
        assert inst["city"] == "Cambridge"
        assert inst["latitude"] == 42.36
        assert inst["longitude"] == -71.09
        assert inst["type"] == "Education"
        assert inst["website"] == "https://mit.edu"
        assert inst["established"] == 1861

    def test_ror_enrichment_skipped_when_no_ror_data(self):
        """ROR enrichment skipped when ror key is missing."""
        merged = {
            "authors": [
                {
                    "institutions": [{"ror_id": "https://ror.org/01abc"}],
                },
            ],
        }
        self.merger._apply_ror_enrichment_to_authors(merged, {})
        inst = merged["authors"][0]["institutions"][0]
        assert inst.get("ror_enriched") is None

    def test_ror_enrichment_skipped_when_no_ror_id(self):
        """ROR enrichment skipped when institution has no ror_id."""
        merged = {
            "authors": [
                {
                    "institutions": [{"display_name": "Unknown"}],
                },
            ],
        }
        results = {"ror": {"anything": {}}}
        self.merger._apply_ror_enrichment_to_authors(merged, results)
        inst = merged["authors"][0]["institutions"][0]
        assert inst.get("ror_enriched") is None

    def test_ror_enrichment_already_enriched_skipped(self):
        """Already ROR-enriched institutions are not re-enriched."""
        merged = {
            "authors": [
                {
                    "institutions": [
                        {
                            "ror_id": "https://ror.org/01abc",
                            "ror_enriched": True,
                        },
                    ],
                },
            ],
        }
        results = {
            "ror": {
                "https://ror.org/01abc": {"country": "France"},
            },
        }
        self.merger._apply_ror_enrichment_to_authors(merged, results)
        assert merged["authors"][0]["institutions"][0].get("country") is None

    def test_ror_enrichment_no_authors(self):
        """ROR enrichment handles missing authors gracefully."""
        merged = {}
        results = {"ror": {"https://ror.org/01abc": {"country": "US"}}}
        self.merger._apply_ror_enrichment_to_authors(merged, results)
        assert merged == {}

    def test_ror_enrichment_non_dict_author_institution(self):
        """ROR enrichment handles non-dict institution gracefully."""
        merged = {
            "authors": [
                {
                    "institutions": ["not a dict"],
                },
            ],
        }
        results = {
            "ror": {"01abc": {"country": "US"}},
        }
        self.merger._apply_ror_enrichment_to_authors(merged, results)
        assert merged["authors"][0]["institutions"][0] == "not a dict"

    # ---------- _enrich_institution_with_ror ----------

    def test_enrich_institution_with_ror_basic(self):
        """Basic ROR enrichment adds country, city, coordinates."""
        institution = {"ror_id": "https://ror.org/01abc"}
        ror_data = {
            "country": "Germany",
            "country_code": "DE",
            "city": "Berlin",
            "latitude": 52.52,
            "longitude": 13.40,
        }
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert institution["country"] == "Germany"
        assert institution["country_code"] == "DE"
        assert institution["city"] == "Berlin"
        assert institution["latitude"] == 52.52
        assert institution["longitude"] == 13.40
        assert institution["ror_enriched"] is True

    def test_enrich_institution_with_ror_does_not_overwrite(self):
        """ROR enrichment does not overwrite existing values."""
        institution = {
            "country": "Existing Country",
            "country_code": "EC",
            "ror_id": "https://ror.org/01abc",
        }
        ror_data = {
            "country": "New Country",
            "country_code": "NC",
        }
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert institution["country"] == "Existing Country"
        assert institution["country_code"] == "EC"

    def test_enrich_institution_with_ror_types(self):
        """ROR enrichment adds type from types list."""
        institution = {"ror_id": "01abc"}
        ror_data = {"types": ["Healthcare", "Research"]}
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert institution["type"] == "Healthcare"

    def test_enrich_institution_with_ror_types_empty(self):
        """ROR enrichment handles empty types list."""
        institution = {"ror_id": "01abc"}
        ror_data = {"types": []}
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert institution.get("type") is None

    def test_enrich_institution_with_ror_website_and_established(self):
        """ROR enrichment adds website and established year."""
        institution = {"ror_id": "01abc"}
        ror_data = {"website": "https://example.org", "established": 1900}
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert institution["website"] == "https://example.org"
        assert institution["established"] == 1900

    def test_enrich_institution_with_ror_external_ids(self):
        """ROR enrichment adds external IDs."""
        institution = {"ror_id": "01abc"}
        ror_data = {
            "external_ids": [
                {"type": "wikidata", "preferred": "Q123", "all": ["Q123", "Q456"]},
                {"type": "grid", "preferred": "grid.12345", "all": ["grid.12345"]},
            ],
        }
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert len(institution["external_ids"]) == 2
        assert institution["external_ids"][0]["type"] == "wikidata"
        assert institution["external_ids"][0]["preferred"] == "Q123"
        assert institution["external_ids"][0]["all"] == ["Q123", "Q456"]

    def test_enrich_institution_with_ror_external_ids_no_duplicates(self):
        """ROR enrichment avoids duplicate external ID types."""
        institution = {
            "ror_id": "01abc",
            "external_ids": [{"type": "wikidata", "preferred": "Existing"}],
        }
        ror_data = {
            "external_ids": [
                {"type": "wikidata", "preferred": "Q123", "all": ["Q123"]},
                {"type": "new_type", "preferred": "N1", "all": ["N1"]},
            ],
        }
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert len(institution["external_ids"]) == 2
        wikidata = [e for e in institution["external_ids"] if e["type"] == "wikidata"]
        assert len(wikidata) == 1
        assert wikidata[0]["preferred"] == "Existing"

    def test_enrich_institution_with_ror_relationships_and_domains(self):
        """ROR enrichment adds relationships and domains."""
        institution = {"ror_id": "01abc"}
        ror_data = {
            "relationships": [{"type": "parent", "label": "System"}],
            "domains": ["education", "research"],
        }
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert institution["relationships"] == [{"type": "parent", "label": "System"}]
        assert institution["domains"] == ["education", "research"]

    def test_enrich_institution_with_ror_missing_ext_id_type(self):
        """ROR external IDs without type or preferred are skipped."""
        institution = {"ror_id": "01abc"}
        ror_data = {
            "external_ids": [
                {},
                {"type": "valid", "preferred": "V1", "all": ["V1"]},
            ],
        }
        self.merger._enrich_institution_with_ror(institution, ror_data)
        assert len(institution["external_ids"]) == 1
        assert institution["external_ids"][0]["type"] == "valid"

    # ---------- merge_results (integration) ----------

    def test_merge_results_complete(self):
        """Full merge_results orchestrates all merge methods."""
        results = {
            "crossref": {
                "title": "Full Test",
                "authors": [{"name": "Author One", "given": "A", "family": "One"}],
                "abstract": "Full abstract.",
                "journal": "Test Journal",
                "publication_date": "2023-01-15",
                "citation_count": 15,
                "volume": "5",
                "issue": "2",
                "page": "10-20",
                "publisher": "Test Publisher",
                "issn": "1111-2222",
                "type": "journal-article",
                "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
                "funders": [{"name": "NSF", "award": ["12345"]}],
                "DOI": "10.1000/test",
                "references_count": 20,
            },
            "openalex": {
                "title": "Should Not Use",
                "citation_count": 10,
                "ids": {
                    "openalex": "W99999",
                    "doi": "https://doi.org/10.1000/test",
                },
                "biblio": {"first_page": "10"},
                "referenced_works_count": 18,
                "cited_by_count": 50,
                "related_works": ["W1"],
                "topics": [{"id": "T1", "display_name": "Test Topic"}],
                "authors": [
                    {
                        "display_name": "Author One",
                        "orcid": "0000-0001-1111-1111",
                    },
                ],
            },
            "semantic_scholar": {
                "title": "Should Not Use Either",
                "citation_count": 12,
                "influential_citation_count": 8,
                "fields_of_study": ["Computer Science"],
                "reference_count": 22,
                "external_ids": {
                    "CorpusId": "C999",
                    "PubMed": "54321",
                },
                "authors": [
                    {"name": "Author One", "author_id": "A999"},
                ],
            },
            "unpaywall": {
                "is_oa": True,
                "oa_status": "gold",
                "best_oa_location": {"url": "https://oa.example.com"},
            },
            "datacite": {
                "creators": [
                    {
                        "name": "Author One",
                        "orcid": "0000-0001-1111-1111",
                    },
                ],
            },
            "ror": {
                "https://ror.org/01abc": {
                    "country": "United States",
                    "country_code": "US",
                    "city": "Cambridge",
                    "types": ["Education"],
                    "website": "https://example.edu",
                    "established": 1800,
                },
            },
        }
        merged = self.merger.merge_results(results)
        assert merged["title"] == "Full Test"
        assert merged["abstract"] == "Full abstract."
        assert merged["journal"] == "Test Journal"
        assert merged["publication_date"] == "2023-01-15"
        assert merged["citation_count"] == 15
        assert merged["is_oa"] is True
        assert merged["oa_status"] == "gold"
        assert merged["oa_url"] == "https://oa.example.com"
        assert merged["influential_citation_count"] == 8
        assert merged["fields_of_study"] == ["Computer Science"]
        assert merged["topics"] == [{"id": "T1", "display_name": "Test Topic"}]
        assert merged["license"] == [{"URL": "https://creativecommons.org/licenses/by/4.0/"}]
        assert merged["funding"] == [{"name": "NSF", "award": ["12345"]}]
        assert merged["external_ids"]["doi"] == "10.1000/test"
        assert merged["external_ids"]["openalex_id"] == "W99999"
        assert merged["external_ids"]["semantic_scholar_corpus_id"] == "C999"
        assert merged["biblio"]["volume"] == "5"
        assert merged["references"]["count"] == 22
        assert merged["references"]["cited_by_count"] == 50
        assert merged["authors"][0]["name"] == "Author One"

    def test_merge_results_empty(self):
        """merge_results returns empty dict with no input."""
        merged = self.merger.merge_results({})
        assert merged == {}
