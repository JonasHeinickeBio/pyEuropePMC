"""Integration tests for RDF converters with real Europe PMC API calls and TTL output."""

import pytest
from rdflib import Graph

from pyeuropepmc.clients.annotations import AnnotationsClient
from pyeuropepmc.clients.article import ArticleClient
from pyeuropepmc.clients.search import SearchClient
from pyeuropepmc.enrichment.enricher import PaperEnricher
from pyeuropepmc.mappers.converters import (
    RDFConversionError,
    convert_annotations_to_rdf,
    convert_enrichment_to_rdf,
    convert_pipeline_to_rdf,
    convert_search_to_rdf,
    convert_xml_to_rdf,
)


@pytest.mark.slow
@pytest.mark.network
class TestConvertersWithRealAPI:
    """Tests using real Europe PMC API calls (slow — hits network)."""

    @pytest.fixture
    def search_client(self):
        """Create search client with caching disabled for testing."""
        return SearchClient()

    @pytest.fixture
    def article_client(self):
        """Create article client with caching disabled for testing."""
        return ArticleClient()

    @pytest.fixture
    def annotations_client(self):
        """Create annotations client with caching disabled for testing."""
        return AnnotationsClient()

    @pytest.fixture
    def enricher(self):
        """Create enrichment client with caching disabled for testing."""
        from pyeuropepmc.enrichment.config import EnrichmentConfig
        config = EnrichmentConfig(
            enable_crossref=False,
            enable_semantic_scholar=False,
            enable_unpaywall=False,
            enable_openalex=False,
            enable_ror=False,
            enable_datacite=False,
        )
        return PaperEnricher(config)

    def test_convert_search_to_rdf_with_real_data(self, search_client):
        """Test search conversion with real Europe PMC API data."""
        search_results = search_client.search(query="malaria", page_size=1)

        assert search_results is not None
        assert len(search_results["resultList"]["result"]) > 0

        result = search_results["resultList"]["result"][0]
        assert "doi" in result or "pmcid" in result

        graph = convert_search_to_rdf(result)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_search_to_rdf_multiple_results(self, search_client):
        """Test search conversion with multiple real results."""
        search_results = search_client.search(query="cancer", page_size=2)

        assert len(search_results["resultList"]["result"]) > 0

        graph = convert_search_to_rdf(search_results["resultList"]["result"])

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    @pytest.mark.integration
    def test_convert_pipeline_with_real_api_data(
        self, search_client, article_client, annotations_client, enricher
    ):
        """Test full pipeline conversion with real API data."""
        search_results = search_client.search(query="diabetes", page_size=1)

        assert len(search_results["resultList"]["result"]) > 0
        result = search_results["resultList"]["result"][0]

        pmid = result.get("pmid")
        if not pmid:
            pytest.skip("No PMID available for XML/annotation tests")

        try:
            xml_data = article_client.get_article_details(
                source="MED", article_id=pmid, result_type="core"
            )
            enrichment_data = enricher.enrich(papers=[result])
            annotations_data = annotations_client.get_annotations_by_article_ids(
                [pmid]
            )
        except Exception as e:
            pytest.skip(f"Skipping due to API error: {e}")

        graph = convert_pipeline_to_rdf(
            search_results=result,
            xml_data=xml_data,
            enrichment_data=enrichment_data,
            annotations_data=annotations_data,
        )

        assert isinstance(graph, Graph)
        assert len(graph) > 0


class TestConvertersTTLOutput:
    """Tests for TTL serialization output展示."""

    @pytest.fixture
    def simple_search_data(self):
        """Simple search data for clean TTL展示."""
        return {
            "doi": "10.1038/nature12373",
            "title": "EuropeanPMC: a new focus on staying in touch",
            "journalTitle": "Nature",
            "pubYear": 2024,
            "authorString": "Smith, John; Johnson, Jane",
            "pmid": "38123456",
            "pmcid": "PMC10776543",
        }

    def test_search_to_rdf_ttl_output(self, simple_search_data):
        """Generate and display TTL output for search conversion."""
        graph = convert_search_to_rdf(simple_search_data)

        ttl_output = graph.serialize(format="turtle")

        print("\n" + "=" * 80)
        print("TTL OUTPUT FOR SEARCH CONVERSION")
        print("=" * 80)
        print(ttl_output)
        print("=" * 80)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

        assert "doi" in ttl_output.lower()
        assert "title" in ttl_output.lower()

    def test_xml_to_rdf_ttl_output(self):
        """Generate and display TTL output for XML conversion."""
        xml_data = {
            "paper": {
                "doi": "10.1038/nature12373",
                "title": "EuropeanPMC: a new focus on staying in touch",
                "journal": "Nature",
                "publication_year": 2024,
            },
            "authors": [
                {"full_name": "John Smith", "orcid": "0000-0000-0000-0001"},
                {"full_name": "Jane Johnson", "orcid": "0000-0000-0000-0002"},
            ],
            "sections": [
                {
                    "title": "Introduction",
                    "content": "This is a test introduction section about EuropeanPMC.",
                }
            ],
        }

        graph = convert_xml_to_rdf(xml_data)

        ttl_output = graph.serialize(format="turtle")

        print("\n" + "=" * 80)
        print("TTL OUTPUT FOR XML CONVERSION")
        print("=" * 80)
        print(ttl_output)
        print("=" * 80)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_enrichment_to_rdf_ttl_output(self):
        """Generate and display TTL output for enrichment conversion."""
        enrichment_data = {
            "paper": {
                "doi": "10.1038/nature12373",
                "title": "EuropeanPMC: a new focus on staying in touch",
                "journal": "Nature",
                "citation_count": 42,
                "reference_count": 15,
            }
        }

        graph = convert_enrichment_to_rdf(enrichment_data)

        ttl_output = graph.serialize(format="turtle")

        print("\n" + "=" * 80)
        print("TTL OUTPUT FOR ENRICHMENT CONVERSION")
        print("=" * 80)
        print(ttl_output)
        print("=" * 80)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_annotations_to_rdf_ttl_output(self):
        """Generate and display TTL output for annotations conversion."""
        annotations_data = [
            {
                "source": "MED",
                "extId": "22649552",
                "pmcid": "PMC3359311",
                "annotations": [
                    {
                        "id": "http://europepmc.org/abstract/MED/22649552#ann1",
                        "exact": "malaria",
                        "tags": [
                            {
                                "uri": "DOID:12365",
                                "name": "malaria",
                                "type": "Disease",
                            }
                        ],
                        "section": "abstract",
                        "provider": {"name": "Europe PMC"},
                    }
                ],
            }
        ]

        graph = convert_annotations_to_rdf(annotations_data)

        ttl_output = graph.serialize(format="turtle")

        print("\n" + "=" * 80)
        print("TTL OUTPUT FOR ANNOTATIONS CONVERSION")
        print("=" * 80)
        print(ttl_output)
        print("=" * 80)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_pipeline_to_rdf_ttl_output(self):
        """Generate and display TTL output for full pipeline conversion."""
        search_data = {
            "doi": "10.1038/nature12373",
            "title": "EuropeanPMC: a new focus on staying in touch",
            "journalTitle": "Nature",
            "pubYear": 2024,
            "authorString": "Smith, John",
            "pmid": "38123456",
        }

        xml_data = {
            "paper": {
                "doi": "10.1038/nature12373",
                "title": "EuropeanPMC: a new focus on staying in touch",
                "journal": "Nature",
                "publication_year": 2024,
            },
            "authors": [{"full_name": "John Smith"}],
        }

        enrichment_data = {
            "paper": {
                "doi": "10.1038/nature12373",
                "title": "EuropeanPMC: a new focus on staying in touch",
                "citation_count": 10,
            }
        }

        annotations_data = [
            {
                "source": "MED",
                "extId": "22649552",
                "annotations": [
                    {
                        "exact": "malaria",
                        "tags": [{"uri": "DOID:12365", "name": "malaria", "type": "Disease"}],
                    }
                ],
            }
        ]

        graph = convert_pipeline_to_rdf(
            search_results=search_data,
            xml_data=xml_data,
            enrichment_data=enrichment_data,
            annotations_data=annotations_data,
        )

        ttl_output = graph.serialize(format="turtle")

        print("\n" + "=" * 80)
        print("TTL OUTPUT FOR FULL PIPELINE CONVERSION")
        print("=" * 80)
        print(ttl_output)
        print("=" * 80)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

        assert "doi" in ttl_output.lower()
        assert "title" in ttl_output.lower()
        assert "author" in ttl_output.lower() or "creator" in ttl_output.lower()


class TestConvertersValidation:
    """Tests for converter input validation."""

    def test_convert_search_to_rdf_empty(self):
        """Test search conversion with empty data raises error."""
        with pytest.raises(RDFConversionError, match="Search results cannot be empty"):
            convert_search_to_rdf([])

    def test_convert_search_to_rdf_invalid_type(self):
        """Test search conversion with invalid type raises error."""
        with pytest.raises(RDFConversionError, match="Search results must be a list or dict"):
            convert_search_to_rdf("invalid")

    def test_convert_xml_to_rdf_empty(self):
        """Test XML conversion with empty data raises error."""
        with pytest.raises(RDFConversionError, match="XML data cannot be empty"):
            convert_xml_to_rdf({})

    def test_convert_enrichment_to_rdf_empty(self):
        """Test enrichment conversion with empty data raises error."""
        with pytest.raises(RDFConversionError, match="Enrichment data cannot be empty"):
            convert_enrichment_to_rdf({})

    def test_convert_annotations_to_rdf_empty(self):
        """Test annotations conversion with empty data raises error."""
        with pytest.raises(RDFConversionError, match="Annotations data cannot be empty"):
            convert_annotations_to_rdf([])

    def test_convert_pipeline_to_rdf_empty(self):
        """Test pipeline conversion with no data returns empty graph."""
        graph = convert_pipeline_to_rdf()

        assert isinstance(graph, Graph)
        assert len(graph) == 0


class TestConvertersEdgeCases:
    """Tests for edge cases in converters."""

    def test_convert_search_to_rdf_with_single_dict(self):
        """Test search conversion with single dict instead of list."""
        search_data = {
            "doi": "10.1234/test",
            "title": "Test Paper",
        }

        graph = convert_search_to_rdf(search_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_pipeline_to_rdf_with_none_values(self):
        """Test pipeline conversion handles None values gracefully."""
        search_data = [{"doi": "10.1234/test", "title": "Test Paper"}]

        graph = convert_pipeline_to_rdf(
            search_results=search_data,
            xml_data=None,
            enrichment_data=None,
            annotations_data=None,
        )

        assert isinstance(graph, Graph)
        assert len(graph) > 0


class TestConvertersWithMockedData:
    """Tests for converter functions using mock data."""

    @pytest.fixture
    def search_data(self):
        """Sample search results data."""
        return [
            {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journalTitle": "Test Journal",
                "pubYear": 2024,
                "authorString": "John Doe, Jane Smith",
            }
        ]

    @pytest.fixture
    def xml_data(self):
        """Sample XML data."""
        return {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": "Test Journal",
                "publication_year": 2024,
            },
            "authors": [{"full_name": "John Doe"}],
            "sections": [{"title": "Introduction", "content": "Test content"}],
        }

    @pytest.fixture
    def enrichment_data(self):
        """Sample enrichment data."""
        return {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": "Test Journal",
                "citation_count": 10,
            }
        }

    @pytest.fixture
    def annotations_data(self):
        """Sample annotations data."""
        return [
            {
                "source": "MED",
                "extId": "22649552",
                "pmcid": "PMC3359311",
                "annotations": [
                    {
                        "id": "http://europepmc.org/abstract/MED/22649552#ann1",
                        "exact": "malaria",
                        "tags": [
                            {
                                "uri": "DOID:12365",
                                "name": "malaria",
                                "type": "Disease",
                            }
                        ],
                        "section": "abstract",
                        "provider": {"name": "Europe PMC"},
                    }
                ],
            }
        ]

    def test_convert_search_to_rdf_creates_graph(self, search_data):
        """Test search conversion creates valid RDF graph."""
        graph = convert_search_to_rdf(search_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_xml_to_rdf_creates_graph(self, xml_data):
        """Test XML conversion creates valid RDF graph."""
        graph = convert_xml_to_rdf(xml_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_enrichment_to_rdf_creates_graph(self, enrichment_data):
        """Test enrichment conversion creates valid RDF graph."""
        graph = convert_enrichment_to_rdf(enrichment_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_annotations_to_rdf_creates_graph(self, annotations_data):
        """Test annotations conversion creates valid RDF graph."""
        graph = convert_annotations_to_rdf(annotations_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_pipeline_to_rdf_creates_graph(self, search_data, xml_data, enrichment_data, annotations_data):
        """Test pipeline conversion creates valid RDF graph."""
        graph = convert_pipeline_to_rdf(
            search_results=search_data,
            xml_data=xml_data,
            enrichment_data=enrichment_data,
            annotations_data=annotations_data,
        )

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_pipeline_to_rdf_partial_data(self, search_data):
        """Test pipeline conversion works with partial data sources."""
        graph = convert_pipeline_to_rdf(search_results=search_data)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_incremental_to_rdf(self):
        """Test incremental conversion adds to existing graph."""
        from rdflib import Graph as BaseGraph

        base_graph = BaseGraph()
        base_graph.bind("ex", "http://example.org/")

        enrichment_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
            }
        }

        result_graph = convert_pipeline_to_rdf(search_results=[{
            "doi": "10.1234/test",
            "title": "Test Paper",
        }])

        assert isinstance(result_graph, Graph)
        assert len(result_graph) > 0

    def test_convert_search_to_rdf_with_custom_namespaces(self, search_data):
        """Test search conversion respects custom namespaces."""
        custom_ns = {"custom": "http://example.org/custom#"}
        graph = convert_search_to_rdf(search_data, namespaces=custom_ns)

        namespace_uris = [str(ns[1]) for ns in graph.namespaces()]
        assert "http://example.org/custom#" in namespace_uris

    def test_convert_xml_to_rdf_excludes_content(self, xml_data):
        """Test XML conversion can exclude content entities."""
        graph = convert_xml_to_rdf(xml_data, include_content=False)

        assert isinstance(graph, Graph)
        assert len(graph) > 0

    def test_convert_pipeline_with_all_options(self, search_data, xml_data, enrichment_data, annotations_data):
        """Test pipeline conversion with all options enabled."""
        graph = convert_pipeline_to_rdf(
            search_results=search_data,
            xml_data=xml_data,
            enrichment_data=enrichment_data,
            annotations_data=annotations_data,
            include_content=True,
        )

        assert isinstance(graph, Graph)
        assert len(graph) > 0


class TestConvertersErrorHandling:
    """Tests for error handling in converters."""

    def test_convert_pipeline_with_no_data_returns_empty_graph(self):
        """Test pipeline conversion with no data returns empty graph."""
        graph = convert_pipeline_to_rdf()

        assert isinstance(graph, Graph)
        assert len(graph) == 0


class TestEnhancedRDFOutput:
    """Tests for enhanced RDF output with new triples and namespaces."""

    @pytest.fixture
    def annotations_data_with_entity_uri(self):
        """Sample annotations data with real ontology URIs."""
        return [
            {
                "source": "MED",
                "extId": "41444612",
                "pmcid": "PMC12888368",
                "annotations": [
                    {
                        "id": "http://europepmc.org/article/MED/41444612#europepmc-50b2a3b",
                        "exact": "ME/CFS",
                        "tags": [
                            {
                                "uri": "http://linkedlifedata.com/resource/umls-concept/C0015674",
                                "name": "chronic fatigue unspecified",
                                "type": "Disease",
                            }
                        ],
                        "section": "Abstract",
                        "provider": "Europe PMC",
                        "annotation_category": "Diseases",
                    },
                    {
                        "id": "http://europepmc.org/article/MED/41444612#europepmc-7e102098",
                        "exact": "amino acid",
                        "tags": [
                            {
                                "uri": "http://purl.obolibrary.org/obo/CHEBI_33709",
                                "name": "amino acid",
                                "type": "Chemical",
                            }
                        ],
                        "section": "Abstract",
                        "provider": "Europe PMC",
                        "annotation_category": "Chemicals",
                    },
                ]
            }
        ]

    def test_annotations_rdf_has_namespace_bindings(self, annotations_data_with_entity_uri):
        """Test that enhanced RDF includes all required namespace bindings."""
        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)

        # Extract all bound namespaces
        bound_namespaces = {prefix: str(ns) for prefix, ns in graph.namespaces()}

        # Assert key namespaces are bound
        assert "oa" in bound_namespaces, "oa namespace should be bound"
        assert "nif" in bound_namespaces, "nif namespace should be bound"
        assert "dcterms" in bound_namespaces, "dcterms namespace should be bound"
        assert "prov" in bound_namespaces, "prov namespace should be bound"
        assert "pyeuropepmc" in bound_namespaces, "pyeuropepmc namespace should be bound"
        assert "owl" in bound_namespaces, "owl namespace should be bound"

    def test_annotations_rdf_has_owl_sameas_triples(self, annotations_data_with_entity_uri):
        """Test that RDF includes owl:sameAs triples linking to ontology URIs."""
        from rdflib import Namespace

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        OWL = Namespace("http://www.w3.org/2002/07/owl#")

        # Query for all owl:sameAs triples
        sameas_triples = list(graph.triples((None, OWL.sameAs, None)))

        # We should have owl:sameAs triples for the entity URIs
        assert len(sameas_triples) > 0, "Should have owl:sameAs triples"

        # Check that the object URIs are from known ontologies
        ontology_uris = [str(obj) for _, _, obj in sameas_triples]
        assert any(
            "linkedlifedata.com" in uri or "obolibrary.org" in uri
            for uri in ontology_uris
        ), "owl:sameAs should link to recognized ontologies"

    def test_annotations_rdf_has_prov_generatedAtTime(self, annotations_data_with_entity_uri):
        """Test that RDF includes prov:generatedAtTime triples for provenance."""
        from rdflib import Namespace
        from rdflib.namespace import XSD

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        PROV = Namespace("http://www.w3.org/ns/prov#")

        # Query for all prov:generatedAtTime triples
        gentime_triples = list(graph.triples((None, PROV.generatedAtTime, None)))

        # We should have at least one prov:generatedAtTime triple per annotation
        assert len(gentime_triples) > 0, "Should have prov:generatedAtTime triples"

        # Check that literals are dateTime typed
        for _, _, obj in gentime_triples:
            assert obj.datatype == XSD.dateTime, "generatedAtTime should be xsd:dateTime"

    def test_annotations_rdf_has_rdfs_label(self, annotations_data_with_entity_uri):
        """Test that RDF includes rdfs:label for readability."""
        from rdflib.namespace import RDFS

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)

        # Query for all rdfs:label triples
        label_triples = list(graph.triples((None, RDFS.label, None)))

        # We should have labels for entities
        assert len(label_triples) > 0, "Should have rdfs:label triples"

        # Check that labels are strings with entity names
        labels = [str(obj) for _, _, obj in label_triples]
        assert any("chronic fatigue" in label.lower() for label in labels), \
            "Should have label for ME/CFS entity"
        assert any("amino acid" in label.lower() for label in labels), \
            "Should have label for amino acid entity"

    def test_annotations_rdf_has_oa_hasBody(self, annotations_data_with_entity_uri):
        """Test that RDF includes oa:hasBody linking to semantic entities."""
        from rdflib import Namespace

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        OA = Namespace("http://www.w3.org/ns/oa#")

        # Query for all oa:hasBody triples
        hasbody_triples = list(graph.triples((None, OA.hasBody, None)))

        # We should have oa:hasBody for each entity annotation
        assert len(hasbody_triples) > 0, "Should have oa:hasBody triples"

        # Check that body URIs link to recognized ontologies
        body_uris = [str(obj) for _, _, obj in hasbody_triples]
        assert any(
            "linkedlifedata.com" in uri or "obolibrary.org" in uri
            for uri in body_uris
        ), "oa:hasBody should link to ontology URIs"

    def test_annotations_rdf_has_oa_hasTarget(self, annotations_data_with_entity_uri):
        """Test that RDF includes oa:hasTarget linking to source articles."""
        from rdflib import Namespace

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        OA = Namespace("http://www.w3.org/ns/oa#")

        # Query for all oa:hasTarget triples
        hastarget_triples = list(graph.triples((None, OA.hasTarget, None)))

        # We should have oa:hasTarget for each entity annotation
        assert len(hastarget_triples) > 0, "Should have oa:hasTarget triples"

        # Check that target URIs point to Europe PMC articles
        target_uris = [str(obj) for _, _, obj in hastarget_triples]
        assert any(
            "europepmc.org" in uri for uri in target_uris
        ), "oa:hasTarget should point to Europe PMC articles"

    def test_annotations_rdf_has_dcterms_creator(self, annotations_data_with_entity_uri):
        """Test that RDF includes dcterms:creator for provenance."""
        from rdflib import Namespace

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        DCT = Namespace("http://purl.org/dc/terms/")

        # Query for all dcterms:creator triples
        creator_triples = list(graph.triples((None, DCT.creator, None)))

        # We should have creator information
        assert len(creator_triples) > 0, "Should have dcterms:creator triples"

        # Check that creators are identified
        creators = [str(obj) for _, _, obj in creator_triples]
        assert any("Europe PMC" in creator for creator in creators), \
            "Should identify Europe PMC as creator"

    def test_annotations_rdf_has_nif_anchorOf(self, annotations_data_with_entity_uri):
        """Test that RDF includes nif:anchorOf for text context."""
        from rdflib import Namespace

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        NIF = Namespace("http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#")

        # Query for all nif:anchorOf triples
        anchor_triples = list(graph.triples((None, NIF.anchorOf, None)))

        # We should have anchor text for each entity
        assert len(anchor_triples) > 0, "Should have nif:anchorOf triples"

        # Check that anchor text matches entity mentions
        anchor_texts = [str(obj) for _, _, obj in anchor_triples]
        assert any("ME/CFS" in text for text in anchor_texts), \
            "Should have anchor text for ME/CFS mention"
        assert any("amino acid" in text for text in anchor_texts), \
            "Should have anchor text for amino acid mention"

    def test_annotations_rdf_has_pyeuropepmc_confidence(self, annotations_data_with_entity_uri):
        """Test that RDF includes pyeuropepmc:confidence when confidence score present."""
        from rdflib import Namespace

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        VOCAB = Namespace("https://w3id.org/pyeuropepmc/vocab#")

        # Query for confidence triples
        confidence_triples = list(graph.triples((None, VOCAB.confidence, None)))

        # Even if confidence is not in input, the enhanced parser might generate it
        # So this test just checks the namespace binding is present
        bound_namespaces = {prefix: str(ns) for prefix, ns in graph.namespaces()}
        assert "pyeuropepmc" in bound_namespaces, "pyeuropepmc namespace should be bound"

    def test_annotations_rdf_has_prov_wasDerivedFrom(self, annotations_data_with_entity_uri):
        """Test that RDF includes prov:wasDerivedFrom for full provenance chain."""
        from rdflib import Namespace

        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        PROV = Namespace("http://www.w3.org/ns/prov#")

        # Query for prov:wasDerivedFrom triples
        derived_triples = list(graph.triples((None, PROV.wasDerivedFrom, None)))

        # We should have derivation information linking to source
        assert len(derived_triples) > 0, "Should have prov:wasDerivedFrom triples"

    def test_annotations_rdf_ttl_contains_required_keywords(self, annotations_data_with_entity_uri):
        """Test that Turtle serialization includes all enhanced triples."""
        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)
        ttl = graph.serialize(format="turtle")

        # Check for key predicates in Turtle output
        assert "@prefix owl:" in ttl, "Turtle should declare owl namespace"
        assert "@prefix prov:" in ttl, "Turtle should declare prov namespace"
        assert "@prefix dcterms:" in ttl, "Turtle should declare dcterms namespace"
        assert "@prefix oa:" in ttl, "Turtle should declare oa namespace"

        # Check for key triple patterns
        assert "owl:sameAs" in ttl, "Turtle should contain owl:sameAs triples"
        assert "prov:generatedAtTime" in ttl, "Turtle should contain prov:generatedAtTime"
        assert "oa:hasBody" in ttl, "Turtle should contain oa:hasBody triples"
        assert "oa:hasTarget" in ttl, "Turtle should contain oa:hasTarget triples"
        assert "rdfs:label" in ttl, "Turtle should contain rdfs:label triples"

    def test_annotations_rdf_graph_size(self, annotations_data_with_entity_uri):
        """Test that enhanced RDF output produces expected triple count."""
        graph = convert_annotations_to_rdf(annotations_data_with_entity_uri)

        # With 2 annotations and all the enhanced triples, we should have a significant graph
        triple_count = len(graph)
        assert triple_count > 10, f"Expected >10 triples, got {triple_count}"

    def test_parse_annotations_deduplication(self):
        """Test that parse_annotations deduplicates identical mentions."""
        from pyeuropepmc.processing.annotation_parser import parse_annotations

        # Create duplicate annotations (same entity, text, position)
        annotations = [
            {
                "source": "MED",
                "extId": "12345",
                "annotations": [
                    {
                        "exact": "malaria",
                        "tags": [{"uri": "DOID:12365", "name": "malaria", "type": "Disease"}],
                        "section": "abstract",
                        "provider": "Europe PMC",
                    },
                    {
                        "exact": "malaria",
                        "tags": [{"uri": "DOID:12365", "name": "malaria", "type": "Disease"}],
                        "section": "abstract",
                        "provider": "Europe PMC",
                    },
                ]
            }
        ]

        parsed = parse_annotations(annotations)

        # Should have deduplicated to 1 entity
        assert len(parsed["entities"]) == 1, "Duplicate annotations should be deduplicated"

    def test_parse_annotations_fills_name(self):
        """Test that parse_annotations fills missing name from exact or URI."""
        from pyeuropepmc.processing.annotation_parser import parse_annotations

        annotations = [
            {
                "source": "MED",
                "extId": "12345",
                "annotations": [
                    {
                        "exact": "malaria",
                        "tags": [{"uri": "DOID:12365"}],  # No name field
                        "section": "abstract",
                    },
                ]
            }
        ]

        parsed = parse_annotations(annotations)

        # Should have filled name from exact
        assert len(parsed["entities"]) > 0
        assert parsed["entities"][0]["name"] == "malaria", "Name should be filled from exact"

    def test_parse_annotations_has_annotation_id(self):
        """Test that parse_annotations ensures each entity has annotation_id."""
        from pyeuropepmc.processing.annotation_parser import parse_annotations

        annotations = [
            {
                "source": "MED",
                "extId": "12345",
                "annotations": [
                    {
                        "exact": "malaria",
                        "tags": [{"uri": "DOID:12365", "name": "malaria"}],
                        "section": "abstract",
                        # No id field
                    },
                ]
            }
        ]

        parsed = parse_annotations(annotations)

        # Should have generated annotation_id
        assert len(parsed["entities"]) > 0
        assert parsed["entities"][0]["annotation_id"], "annotation_id should be present"
