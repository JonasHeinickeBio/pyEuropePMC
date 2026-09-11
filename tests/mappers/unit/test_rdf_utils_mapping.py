"""Unit tests for the RDF triple-mapping helper functions in
pyeuropepmc.mappers.rdf_utils (field mapping, datatype inference, MeSH
ontology alignment, and external-identifier owl:sameAs links)."""

from __future__ import annotations

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import XSD

from pyeuropepmc.mappers import rdf_utils as ru
from pyeuropepmc.models.annotation import EntityAnnotation
from pyeuropepmc.models.mesh import MeSHHeadingEntity, MeSHQualifierEntity


def _entity(class_name: str, **attrs):
    cls = type(class_name, (object,), {})
    obj = cls()
    for k, v in attrs.items():
        setattr(obj, k, v)
    return obj


def resolve_predicate(s: str) -> URIRef:
    return URIRef(f"urn:pred:{s}")


class TestParsePredicateConfig:
    def test_dict_config(self):
        predicate, datatype = ru._parse_predicate_config(
            {"predicate": "dc:title", "datatype": "xsd:string"}
        )
        assert predicate == "dc:title"
        assert datatype == "xsd:string"

    def test_string_config(self):
        predicate, datatype = ru._parse_predicate_config("dc:title")
        assert predicate == "dc:title"
        assert datatype is None

    def test_dict_missing_keys(self):
        predicate, datatype = ru._parse_predicate_config({})
        assert predicate is None
        assert datatype is None


class TestHandleEntityAnnotationSpecialCases:
    def test_not_hasbody_predicate_returns_false(self):
        g = Graph()
        entity = EntityAnnotation()
        handled = ru._handle_entity_annotation_special_cases(
            g,
            URIRef("urn:s"),
            URIRef("urn:p"),
            entity,
            "entity_id",
            "x",
            "other:pred",
            None,
            False,
        )
        assert handled is False

    def test_hasbody_not_yet_added_returns_false(self):
        g = Graph()
        entity = EntityAnnotation()
        handled = ru._handle_entity_annotation_special_cases(
            g,
            URIRef("urn:s"),
            URIRef("urn:p"),
            entity,
            "entity_id",
            "x",
            "oa:hasBody",
            None,
            False,
        )
        assert handled is False

    def test_entity_id_with_resolvable_uri_no_context(self):
        g = Graph()
        subject = URIRef("urn:s")
        predicate = URIRef("urn:p")
        entity = EntityAnnotation(entity_id="CHEBI:16236")
        handled = ru._handle_entity_annotation_special_cases(
            g, subject, predicate, entity, "entity_id", "CHEBI:16236", "oa:hasBody", None, True
        )
        assert handled is True
        assert len(g) == 1

    def test_entity_id_with_context(self):
        ds = Dataset()
        context = URIRef("urn:ctx")
        subject = URIRef("urn:s")
        predicate = URIRef("urn:p")
        entity = EntityAnnotation(entity_id="CHEBI:16236")
        handled = ru._handle_entity_annotation_special_cases(
            ds, subject, predicate, entity, "entity_id", "CHEBI:16236", "oa:hasBody", context, True
        )
        assert handled is True
        assert len(list(ds.graph(context))) == 1

    def test_entity_id_unresolvable_falls_through(self):
        g = Graph()
        entity = EntityAnnotation(entity_id="plain text")
        handled = ru._handle_entity_annotation_special_cases(
            g,
            URIRef("urn:s"),
            URIRef("urn:p"),
            entity,
            "entity_id",
            "plain text",
            "oa:hasBody",
            None,
            True,
        )
        assert handled is False
        assert len(g) == 0

    def test_exact_with_existing_resolvable_entity_id_skips_literal(self):
        g = Graph()
        entity = EntityAnnotation(entity_id="CHEBI:16236", exact="glucose")
        handled = ru._handle_entity_annotation_special_cases(
            g,
            URIRef("urn:s"),
            URIRef("urn:p"),
            entity,
            "exact",
            "glucose",
            "oa:hasBody",
            None,
            True,
        )
        assert handled is True
        assert len(g) == 0

    def test_exact_without_entity_id_adds_literal(self):
        g = Graph()
        entity = EntityAnnotation(exact="glucose")
        handled = ru._handle_entity_annotation_special_cases(
            g,
            URIRef("urn:s"),
            URIRef("urn:p"),
            entity,
            "exact",
            "glucose",
            "oa:hasBody",
            None,
            True,
        )
        assert handled is True
        assert (URIRef("urn:s"), URIRef("urn:p"), Literal("glucose")) in g

    def test_exact_with_unresolvable_entity_id_adds_literal_with_context(self):
        ds = Dataset()
        context = URIRef("urn:ctx")
        entity = EntityAnnotation(entity_id="plain text", exact="glucose")
        handled = ru._handle_entity_annotation_special_cases(
            ds,
            URIRef("urn:s"),
            URIRef("urn:p"),
            entity,
            "exact",
            "glucose",
            "oa:hasBody",
            context,
            True,
        )
        assert handled is True
        assert len(list(ds.graph(context))) == 1

    def test_other_field_name_returns_false(self):
        g = Graph()
        entity = EntityAnnotation()
        handled = ru._handle_entity_annotation_special_cases(
            g,
            URIRef("urn:s"),
            URIRef("urn:p"),
            entity,
            "provider",
            "x",
            "oa:hasBody",
            None,
            True,
        )
        assert handled is False


class TestMapSingleValueFields:
    def test_none_value_skipped(self):
        g = Graph()
        entity = _entity("PaperEntity", title=None)
        ru.map_single_value_fields(
            g, URIRef("urn:s"), entity, {"title": "dc:title"}, resolve_predicate
        )
        assert len(g) == 0

    def test_predicate_none_skipped(self):
        g = Graph()
        entity = _entity("PaperEntity", title="T")
        ru.map_single_value_fields(g, URIRef("urn:s"), entity, {"title": {}}, resolve_predicate)
        assert len(g) == 0

    def test_plain_string_literal_no_context(self):
        g = Graph()
        entity = _entity("PaperEntity", title="A Title")
        ru.map_single_value_fields(
            g, URIRef("urn:s"), entity, {"title": "dc:title"}, resolve_predicate
        )
        assert (URIRef("urn:s"), resolve_predicate("dc:title"), Literal("A Title")) in g

    def test_explicit_datatype(self):
        g = Graph()
        entity = _entity("PaperEntity", citation_count="5")
        ru.map_single_value_fields(
            g,
            URIRef("urn:s"),
            entity,
            {"citation_count": {"predicate": "dc:count", "datatype": "xsd:integer"}},
            resolve_predicate,
        )
        triple = (
            URIRef("urn:s"),
            resolve_predicate("dc:count"),
            Literal("5", datatype=XSD.integer),
        )
        assert triple in g

    def test_with_context(self):
        ds = Dataset()
        context = URIRef("urn:ctx")
        entity = _entity("PaperEntity", title="A Title")
        ru.map_single_value_fields(
            ds, URIRef("urn:s"), entity, {"title": "dc:title"}, resolve_predicate, context
        )
        assert len(list(ds.graph(context))) == 1

    def test_entity_id_field_non_hasbody_constructs_uri(self):
        g = Graph()
        entity = _entity("SomeEntity", entity_id="CHEBI:16236")
        ru.map_single_value_fields(
            g, URIRef("urn:s"), entity, {"entity_id": "skos:related"}, resolve_predicate
        )
        assert (
            URIRef("urn:s"),
            resolve_predicate("skos:related"),
            URIRef("http://purl.obolibrary.org/obo/CHEBI_16236"),
        ) in g

    def test_entity_id_field_with_context(self):
        ds = Dataset()
        context = URIRef("urn:ctx")
        entity = _entity("SomeEntity", entity_id="CHEBI:16236")
        ru.map_single_value_fields(
            ds, URIRef("urn:s"), entity, {"entity_id": "skos:related"}, resolve_predicate, context
        )
        assert len(list(ds.graph(context))) == 1

    def test_entity_annotation_hasbody_flow(self):
        g = Graph()
        entity = EntityAnnotation(entity_id="CHEBI:16236", exact="glucose")
        ru.map_single_value_fields(
            g,
            URIRef("urn:s"),
            entity,
            {"entity_id": "oa:hasBody", "exact": "oa:hasBody"},
            resolve_predicate,
        )
        # The special-case handler requires hasbody_added to already be True
        # to fire, which never happens on the first oa:hasBody field, so both
        # fields fall through to the normal literal path.
        assert len(g) == 2


class TestTryDatabaseFormat:
    def test_chebi(self):
        uri = ru._try_database_format("CHEBI:16236")
        assert uri == URIRef("http://purl.obolibrary.org/obo/CHEBI_16236")

    def test_mesh(self):
        uri = ru._try_database_format("MESH:D000001")
        assert uri == URIRef("http://id.nlm.nih.gov/mesh/D000001")

    def test_uniprot_fallback_branch(self):
        uri = ru._try_database_format("UNIPROT:P12345")
        assert uri == URIRef("https://identifiers.org/uniprot/P12345")

    def test_unknown_prefix_returns_none(self):
        assert ru._try_database_format("FOO:123") is None

    def test_no_colon_returns_none(self):
        assert ru._try_database_format("noformat") is None

    def test_multiple_colons_uses_first_split(self):
        uri = ru._try_database_format("GO:0008150:extra")
        assert uri == URIRef("http://purl.obolibrary.org/obo/GO_0008150_extra")


class TestConstructEntityUri:
    def test_none_returns_none(self):
        assert ru._construct_entity_uri(None) is None

    def test_empty_string_returns_none(self):
        assert ru._construct_entity_uri("") is None

    def test_non_string_returns_none(self):
        assert ru._construct_entity_uri(123) is None

    def test_full_uri_passthrough(self):
        uri = ru._construct_entity_uri("http://example.org/x")
        assert uri == URIRef("http://example.org/x")

    def test_database_format_delegation(self):
        uri = ru._construct_entity_uri("DOID:12365")
        assert uri == URIRef("http://purl.obolibrary.org/obo/DOID_12365")

    def test_unrecognized_text_returns_none(self):
        assert ru._construct_entity_uri("metabolic failure") is None


class TestParseDatatype:
    def test_empty_returns_none(self):
        assert ru._parse_datatype("") is None

    def test_known_xsd_type(self):
        assert ru._parse_datatype("xsd:integer") == XSD.integer

    def test_unknown_xsd_local_name_returns_none(self):
        assert ru._parse_datatype("xsd:notreal") is None

    def test_non_xsd_prefix_returns_none(self):
        assert ru._parse_datatype("foaf:name") is None


class TestInferDatatype:
    def test_publication_year_four_digit_string(self):
        assert ru._infer_datatype("publication_year", "2020") == XSD.gYear

    def test_publication_year_int(self):
        assert ru._infer_datatype("publication_year", 2020) == XSD.gYear

    def test_publication_year_wrong_length_falls_to_integer(self):
        assert ru._infer_datatype("publication_year", 202) == XSD.integer

    def test_integer(self):
        assert ru._infer_datatype("count", 5) == XSD.integer

    def test_bool_is_not_integer(self):
        assert ru._infer_datatype("flag", True) == XSD.boolean

    def test_float(self):
        assert ru._infer_datatype("score", 1.5) == XSD.decimal

    def test_iso_date(self):
        assert ru._infer_datatype("date", "2020-01-01") == XSD.date

    def test_year_only_string(self):
        assert ru._infer_datatype("year", "2020") == XSD.gYear

    def test_url(self):
        assert ru._infer_datatype("link", "https://example.org") == XSD.anyURI

    def test_plain_string_returns_none(self):
        assert ru._infer_datatype("title", "hello") is None


class TestMapMultiValueFields:
    def test_none_values_skipped(self):
        g = Graph()
        entity = _entity("PaperEntity", keywords=None)
        ru.map_multi_value_fields(
            g, URIRef("urn:s"), entity, {"keywords": "dc:subject"}, resolve_predicate
        )
        assert len(g) == 0

    def test_non_list_value_skipped(self):
        g = Graph()
        entity = _entity("PaperEntity", keywords="not-a-list")
        ru.map_multi_value_fields(
            g, URIRef("urn:s"), entity, {"keywords": "dc:subject"}, resolve_predicate
        )
        assert len(g) == 0

    def test_list_values_added(self):
        g = Graph()
        entity = _entity("PaperEntity", keywords=["a", "b", None])
        ru.map_multi_value_fields(
            g, URIRef("urn:s"), entity, {"keywords": "dc:subject"}, resolve_predicate
        )
        assert len(g) == 2

    def test_with_context(self):
        ds = Dataset()
        context = URIRef("urn:ctx")
        entity = _entity("PaperEntity", keywords=["a"])
        ru.map_multi_value_fields(
            ds, URIRef("urn:s"), entity, {"keywords": "dc:subject"}, resolve_predicate, context
        )
        assert len(list(ds.graph(context))) == 1


class TestMapPaperOntologyAlignments:
    def test_no_mesh_no_keywords(self):
        g = Graph()
        entity = _entity("PaperEntity", mesh_terms=None, keywords=None)
        ru.map_paper_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0

    def test_no_mesh_but_keywords_maps_simple_terms(self):
        g = Graph()
        entity = _entity("PaperEntity", mesh_terms=None, keywords=["Cancer", "  "])
        ru.map_paper_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_structured_mesh_term_with_qualifiers_and_ui(self):
        g = Graph()
        qualifier = MeSHQualifierEntity(qualifier_name="therapy", abbreviation="TH")
        heading = MeSHHeadingEntity(
            descriptor_name="Neoplasms", qualifiers=[qualifier], descriptor_ui="D009369"
        )
        entity = _entity("PaperEntity", mesh_terms=[heading])
        ru.map_paper_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) > 0
        assert (
            URIRef("http://id.nlm.nih.gov/mesh/Neoplasms"),
            resolve_predicate("meshv:identifier"),
            Literal("D009369"),
        ) in g

    def test_structured_mesh_term_without_qualifiers_or_ui(self):
        g = Graph()
        heading = MeSHHeadingEntity(descriptor_name="Humans")
        entity = _entity("PaperEntity", mesh_terms=[heading])
        ru.map_paper_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert (
            URIRef("urn:s"),
            resolve_predicate("meshv:hasDescriptor"),
            URIRef("http://id.nlm.nih.gov/mesh/Humans"),
        ) in g

    def test_string_mesh_terms(self):
        g = Graph()
        entity = _entity("PaperEntity", mesh_terms=["Cancer", "", "  "])
        ru.map_paper_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_with_context(self):
        ds = Dataset()
        context = URIRef("urn:ctx")
        entity = _entity("PaperEntity", mesh_terms=["Cancer"])
        ru.map_paper_ontology_alignments(ds, URIRef("urn:s"), entity, resolve_predicate, context)
        assert len(list(ds.graph(context))) == 1


class TestAddMeshQualifierNoAbbreviation:
    def test_qualifier_without_abbreviation_adds_no_abbreviation_triple(self):
        g = Graph()
        qualifier = MeSHQualifierEntity(qualifier_name="diagnosis")
        ru._add_mesh_qualifier(
            g, URIRef("urn:s"), URIRef("urn:mesh"), qualifier, "Neoplasms", resolve_predicate, None
        )
        predicates = {p for _, p, _ in g}
        assert resolve_predicate("meshv:abbreviation") not in predicates
        assert resolve_predicate("meshv:hasQualifier") in predicates

    def test_qualifier_with_context(self):
        ds = Dataset()
        context = URIRef("urn:ctx")
        qualifier = MeSHQualifierEntity(qualifier_name="therapy", abbreviation="TH")
        ru._add_mesh_qualifier(
            ds,
            URIRef("urn:s"),
            URIRef("urn:mesh"),
            qualifier,
            "Neoplasms",
            resolve_predicate,
            context,
        )
        assert len(list(ds.graph(context))) > 0


class TestFinalizeOntologyAlignments:
    def test_keywords_and_research_domain(self):
        g = Graph()
        entity = _entity("PaperEntity", keywords=["cancer"], research_domain="oncology")
        ru._finalize_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 2

    def test_no_keywords_no_domain(self):
        g = Graph()
        entity = _entity("PaperEntity", keywords=None)
        ru._finalize_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0

    def test_with_context(self):
        ds = Dataset()
        context = URIRef("urn:ctx")
        entity = _entity("PaperEntity", keywords=["cancer"], research_domain="oncology")
        ru._finalize_ontology_alignments(ds, URIRef("urn:s"), entity, resolve_predicate, context)
        assert len(list(ds.graph(context))) == 2


class TestOtherOntologyAlignments:
    def test_map_author_ontology_alignments_is_noop(self):
        g = Graph()
        ru.map_author_ontology_alignments(
            g, URIRef("urn:s"), _entity("AuthorEntity"), resolve_predicate
        )
        assert len(g) == 0

    def test_map_reference_ontology_alignments_is_noop(self):
        g = Graph()
        ru.map_reference_ontology_alignments(
            g, URIRef("urn:s"), _entity("ReferenceEntity"), resolve_predicate
        )
        assert len(g) == 0

    def test_map_institution_ontology_alignments_with_geo(self):
        g = Graph()
        entity = _entity("InstitutionEntity", latitude=1.0, longitude=2.0)
        ru.map_institution_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_map_institution_ontology_alignments_without_geo(self):
        g = Graph()
        entity = _entity("InstitutionEntity")
        ru.map_institution_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0


class TestAddPaperIdentifiers:
    def test_all_absent(self):
        g = Graph()
        entity = _entity("PaperEntity", doi=None, pmcid=None, pmid=None)
        ru.add_paper_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0

    def test_doi(self):
        g = Graph()
        entity = _entity("PaperEntity", doi="10.1/x", pmcid=None, pmid=None)
        ru.add_paper_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert (
            URIRef("urn:s"),
            resolve_predicate("owl:sameAs"),
            URIRef("https://doi.org/10.1/x"),
        ) in g

    def test_pmcid_with_prefix(self):
        g = Graph()
        entity = _entity("PaperEntity", doi=None, pmcid="PMC123", pmid=None)
        ru.add_paper_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert (
            URIRef("urn:s"),
            resolve_predicate("owl:sameAs"),
            URIRef("https://europepmc.org/article/PMC/123/"),
        ) in g

    def test_pmcid_without_prefix(self):
        g = Graph()
        entity = _entity("PaperEntity", doi=None, pmcid="123", pmid=None)
        ru.add_paper_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert (
            URIRef("urn:s"),
            resolve_predicate("owl:sameAs"),
            URIRef("https://europepmc.org/article/PMC/123/"),
        ) in g

    def test_pmid(self):
        g = Graph()
        entity = _entity("PaperEntity", doi=None, pmcid=None, pmid="999")
        ru.add_paper_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert (
            URIRef("urn:s"),
            resolve_predicate("owl:sameAs"),
            URIRef("https://europepmc.org/article/MED/999"),
        ) in g


class TestAddAuthorIdentifiers:
    def test_orcid(self):
        g = Graph()
        entity = _entity("AuthorEntity", orcid="0000-0002-1825-0097")
        ru.add_author_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_openalex(self):
        g = Graph()
        entity = _entity("AuthorEntity", openalex_id="https://openalex.org/A1")
        ru.add_author_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_no_attrs(self):
        g = Graph()
        entity = _entity("AuthorEntity")
        ru.add_author_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0


class TestAddInstitutionIdentifiers:
    def test_all_present(self):
        g = Graph()
        entity = _entity(
            "InstitutionEntity",
            ror_id="https://ror.org/1",
            openalex_id="https://openalex.org/I1",
            wikidata_id="Q1",
        )
        ru.add_institution_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 3

    def test_none_present(self):
        g = Graph()
        entity = _entity("InstitutionEntity")
        ru.add_institution_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0


class TestAddReferenceIdentifiers:
    def test_doi_and_pmid(self):
        g = Graph()
        entity = _entity("ReferenceEntity", doi="10.1/x", pmid="123")
        ru.add_reference_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 2

    def test_neither(self):
        g = Graph()
        entity = _entity("ReferenceEntity")
        ru.add_reference_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0


class TestAddEntityAnnotationIdentifiers:
    def test_entity_id_present(self):
        g = Graph()
        entity = _entity("EntityAnnotation", entity_id="http://example.org/c1")
        ru.add_entity_annotation_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_entity_id_absent(self):
        g = Graph()
        entity = _entity("EntityAnnotation")
        ru.add_entity_annotation_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0


class TestAddExternalIdentifiers:
    def test_dispatch_paper(self):
        g = Graph()
        entity = _entity("PaperEntity", doi="10.1/x", pmcid=None, pmid=None)
        ru.add_external_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_unknown_class_noop(self):
        g = Graph()
        entity = _entity("SomethingElse")
        ru.add_external_identifiers(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0


class TestMapOntologyAlignments:
    def test_paper_dispatch_includes_external_identifiers(self):
        g = Graph()
        entity = _entity(
            "PaperEntity", mesh_terms=None, keywords=None, doi="10.1/x", pmcid=None, pmid=None
        )
        ru.map_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_author_dispatch(self):
        g = Graph()
        entity = _entity("AuthorEntity", orcid="0000-0002-1825-0097")
        ru.map_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_institution_dispatch(self):
        g = Graph()
        entity = _entity(
            "InstitutionEntity", latitude=1.0, longitude=2.0, ror_id="https://ror.org/1"
        )
        ru.map_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 2

    def test_reference_dispatch(self):
        g = Graph()
        entity = _entity("ReferenceEntity", doi="10.1/x", pmid=None)
        ru.map_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 1

    def test_unknown_class_only_external_identifiers_attempted(self):
        g = Graph()
        entity = _entity("SomethingElse")
        ru.map_ontology_alignments(g, URIRef("urn:s"), entity, resolve_predicate)
        assert len(g) == 0
