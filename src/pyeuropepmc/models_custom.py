"""
Custom model methods for PyEuropePMC entities.

This file contains custom methods that extend the generated LinkML models.
These methods are not part of the LinkML schema and need to be added after
model generation.
"""

# mypy: ignore-errors
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def _add_custom_methods():
    """Add custom methods to generated model classes."""
    from pyeuropepmc.models import BaseEntity, Organization

    @classmethod
    def from_enrichment_dict(cls, inst_dict: dict[str, Any]) -> Organization:
        """
        Create an Organization from enrichment institution dictionary.

        Parameters
        ----------
        inst_dict : dict
            Institution dictionary from enrichment result

        Returns
        -------
        Organization
            Organization entity with enrichment data
        """
        # Handle relationships - extract labels from dicts
        relationships_data = inst_dict.get("relationships", [])
        if relationships_data and isinstance(relationships_data[0], dict):
            relationships_list = [r.get("label", "") for r in relationships_data]
        else:
            relationships_list = relationships_data

        # Extract individual identifiers from external_ids
        grid_id = None
        isni = None
        wikidata_id = None
        fundref_id = None

        external_ids = inst_dict.get("external_ids", [])
        if external_ids:
            for ext_id in external_ids:
                if isinstance(ext_id, dict):
                    id_type = ext_id.get("type")
                    id_value = ext_id.get("preferred") or (
                        ext_id.get("all", [None])[0] if ext_id.get("all") else None
                    )

                    if id_type == "grid" and id_value:
                        grid_id = id_value
                    elif id_type == "isni" and id_value:
                        isni = id_value
                    elif id_type == "wikidata" and id_value:
                        wikidata_id = id_value
                    elif id_type == "fundref" and id_value:
                        fundref_id = id_value

        org = cls(
            display_name=inst_dict.get("display_name", ""),
            ror_id=inst_dict.get("ror_id"),
            openalex_id=inst_dict.get("openalex_id") or inst_dict.get("id"),
            country=inst_dict.get("country"),
            country_code=inst_dict.get("country_code"),
            city=inst_dict.get("city"),
            latitude=inst_dict.get("latitude"),
            longitude=inst_dict.get("longitude"),
            institution_type=inst_dict.get("type"),
            grid_id=grid_id,
            isni=isni,
            wikidata_id=wikidata_id,
            fundref_id=fundref_id,
            website=inst_dict.get("website"),
            established=inst_dict.get("established"),
            domains=inst_dict.get("domains", []),
            relationships=relationships_list,
            # Additional ROR fields
            status=inst_dict.get("status"),
            types=inst_dict.get("types", []),
            names=inst_dict.get("names", []),
            locations=inst_dict.get("locations", []),
            links=inst_dict.get("links", []),
        )
        return org

    # Add the method to the Organization class
    Organization.from_enrichment_dict = from_enrichment_dict

    # For Pydantic v2, we need to use model_validator but it needs to be set before model is used
    # We'll monkey-patch __init__ to call post_init after validation
    _original_org_init = Organization.__init__

    def _new_org_init(self, *args, **kwargs):
        _original_org_init(self, *args, **kwargs)
        self.post_init()

    Organization.__init__ = _new_org_init

    def organization_post_init(self: Organization) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            object.__setattr__(self, "types", ["org:Organization"])
        if not self.label and self.display_name:
            object.__setattr__(self, "label", self.display_name)

    Organization.post_init = organization_post_init

    def validate(self: Organization) -> None:
        """Validate the organization entity.

        Raises
        ------
        ValueError
            If display_name is missing or empty after trimming
        """
        if self.display_name is None or self.display_name.strip() == "":
            raise ValueError("Organization must have a display_name")

    def normalize(self: Organization) -> None:
        """Normalize organization data by trimming whitespace."""
        if self.display_name is not None:
            self.display_name = self.display_name.strip()
        if self.ror_id is not None:
            self.ror_id = self.ror_id.strip()
        if self.city is not None:
            self.city = self.city.strip()

    # Add methods to Organization class
    Organization.validate = validate
    Organization.normalize = normalize

    # Add methods to BaseEntity
    from pyeuropepmc.models import JournalEntity

    def baseentity_post_init(self: BaseEntity) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            object.__setattr__(self, "types", [])
        if not self.label and self.id:
            object.__setattr__(self, "label", self.id)

    BaseEntity.post_init = baseentity_post_init

    _original_base_init = BaseEntity.__init__

    def _new_base_init(self, *args, **kwargs):
        _original_base_init(self, *args, **kwargs)
        self.post_init()

    BaseEntity.__init__ = _new_base_init

    def baseentity_validate(self: BaseEntity) -> None:
        """Validate the base entity."""
        pass

    def baseentity_normalize(self: BaseEntity) -> None:
        """Normalize the base entity (no-op)."""
        pass

    def baseentity_to_dict(self: BaseEntity) -> dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()

    def baseentity_to_rdf(
        self: BaseEntity,
        g,
        uri=None,
        mapper=None,
        related_entities=None,
        extraction_info=None,
        parent_uri=None,
    ) -> Any:
        """Convert to RDF using mapper."""
        from pyeuropepmc.models.rdf_methods import to_rdf

        if mapper is None:
            raise ValueError("RDF mapper required")
        return to_rdf(
            self,
            g=g,
            uri=uri,
            mapper=mapper,
            related_entities=related_entities,
            extraction_info=extraction_info,
            parent_uri=parent_uri,
        )

    def baseentity_mint_uri(self: BaseEntity, entity_type: str) -> Any:
        """Generate URI for the entity."""
        from urllib.parse import quote
        import uuid

        if self.id:
            encoded_id = quote(str(self.id))
            return f"http://example.org/data/{entity_type}/{encoded_id}"
        else:
            random_id = uuid.uuid4()
            return f"http://example.org/data/{entity_type}/{random_id}"

    BaseEntity.validate = baseentity_validate
    BaseEntity.normalize = baseentity_normalize
    BaseEntity.to_dict = baseentity_to_dict
    BaseEntity.to_rdf = baseentity_to_rdf
    BaseEntity.mint_uri = baseentity_mint_uri

    def journal_normalize(self: JournalEntity) -> None:
        """Normalize journal data by trimming whitespace."""
        if self.title:
            object.__setattr__(self, "title", self.title.strip())
        if self.issn:
            object.__setattr__(self, "issn", self.issn.strip())
        if self.essn:
            object.__setattr__(self, "essn", self.essn.strip())
        if self.publisher:
            object.__setattr__(self, "publisher", self.publisher.strip())
        if self.country:
            object.__setattr__(self, "country", self.country.strip())
        if self.nlmid:
            object.__setattr__(self, "nlmid", self.nlmid.strip())

    JournalEntity.normalize = journal_normalize

    @classmethod
    def from_enrichment_dict(cls, journal_dict: dict[str, Any]) -> JournalEntity:
        """
        Create a JournalEntity from enrichment journal dictionary.

        Parameters
        ----------
        journal_dict : dict
            Journal dictionary from enrichment result

        Returns
        -------
        JournalEntity
            Journal entity with enrichment data
        """
        issn_value = journal_dict.get("issn")
        # Handle ISSN conversion: if it's a list, take first element; if string, keep it
        issn = None
        if issn_value:
            if isinstance(issn_value, list):
                issn = issn_value[0] if issn_value else None
            else:
                issn = issn_value

        return cls(
            title=journal_dict.get("display_name", ""),
            issn=issn,
            openalex_id=journal_dict.get("id"),
            publisher=journal_dict.get("publisher"),
            country=journal_dict.get("country"),
            subject_areas=journal_dict.get("subjects"),
            impact_factor=journal_dict.get("impact_factor"),
            sjr=journal_dict.get("sjr"),
            h_index=journal_dict.get("h_index"),
        )

    JournalEntity.from_enrichment_dict = from_enrichment_dict


def _add_reference_methods():
    """Add custom methods to ReferenceEntity class."""
    import re

    from pyeuropepmc.models import ReferenceEntity

    def reference_post_init(self: ReferenceEntity) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            self.types = ["bibo:Document"]
        if not self.label:
            self.label = self.title or self.doi or "Untitled Reference"

    ReferenceEntity.post_init = reference_post_init

    _original_ref_init = ReferenceEntity.__init__

    def _new_ref_init(self, *args, **kwargs):
        _original_ref_init(self, *args, **kwargs)
        self.post_init()

    ReferenceEntity.__init__ = _new_ref_init

    def reference_normalize(self: ReferenceEntity) -> None:
        """Normalize reference data by trimming whitespace and normalizing DOI."""

        if self.title:
            object.__setattr__(self, "title", self.title.strip())
        if self.doi:
            doi = self.doi.strip().lower()
            doi = re.sub(r"^https://doi\.org/", "", doi)
            doi = re.sub(r"^http://doi\.org/", "", doi)
            doi = re.sub(r"^http://dx\.doi\.org/", "", doi)
            object.__setattr__(self, "doi", doi)
        if self.journal:
            if isinstance(self.journal, str):
                object.__setattr__(self, "journal", self.journal.strip())
        if self.authors:
            if isinstance(self.authors, str):
                object.__setattr__(self, "authors", self.authors.strip())
        if self.raw_citation:
            object.__setattr__(self, "raw_citation", self.raw_citation.strip())

    ReferenceEntity.normalize = reference_normalize

    @classmethod
    def from_enrichment_dict(cls, ref_dict: dict[str, Any]) -> ReferenceEntity:
        """
        Create a ReferenceEntity from enrichment dictionary.

        Parameters
        ----------
        ref_dict : dict
            Reference dictionary from enrichment result

        Returns
        -------
        ReferenceEntity
            Reference entity with enrichment data
        """
        return cls(
            title=ref_dict.get("title"),
            doi=ref_dict.get("doi"),
            journal=ref_dict.get("journal"),
            authors=ref_dict.get("authors"),
            publication_year=ref_dict.get("publication_year"),
            volume=ref_dict.get("volume"),
            pages=ref_dict.get("pages"),
            raw_citation=ref_dict.get("raw_citation"),
        )

    ReferenceEntity.from_enrichment_dict = from_enrichment_dict


def _add_paper_methods():
    """Add custom methods to PaperEntity class."""
    from pyeuropepmc.models import JournalEntity, PaperEntity

    def paper_post_init(self: PaperEntity) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            self.types = ["bibo:AcademicArticle"]
        if not self.label:
            self.label = self.title or self.doi or self.pmcid or ""

    PaperEntity.post_init = paper_post_init

    # Monkey-patch __init__ to call post_init
    _original_paper_init = PaperEntity.__init__

    def _new_paper_init(self, *args, **kwargs):
        _original_paper_init(self, *args, **kwargs)
        self.post_init()

    PaperEntity.__init__ = _new_paper_init

    # Monkey-patch normalize to use __dict__ to bypass validation
    def paper_normalize(self: PaperEntity) -> None:
        """Normalize PaperEntity by trimming whitespace."""
        import re

        if self.title:
            object.__setattr__(self, "title", self.title.strip())
        if self.doi:
            doi = self.doi.strip().lower()
            # Remove DOI URL prefixes
            doi = re.sub(r"^https://doi\.org/", "", doi)
            doi = re.sub(r"^http://doi\.org/", "", doi)
            doi = re.sub(r"^http://dx\.doi\.org/", "", doi)
            object.__setattr__(self, "doi", doi)
        if self.pmcid:
            object.__setattr__(self, "pmcid", self.pmcid.strip().upper())
        if self.journal:
            self.journal.normalize()

    PaperEntity.normalize = paper_normalize

    def paper_validate(self: PaperEntity) -> None:
        """Validate the paper entity.

        Raises
        ------
        ValueError
            If paper has no identifiers (title, doi, pmcid, pmid)
        """
        has_id = self.title or self.doi or self.pmcid or self.pmid
        if not has_id:
            raise ValueError("PaperEntity must have at least one identifier")

    PaperEntity.validate = paper_validate

    @classmethod
    def from_enrichment_result(cls, enrichment_result: dict[str, Any]) -> PaperEntity:
        """
        Create a PaperEntity from enrichment result.

        Parameters
        ----------
        enrichment_result : dict
            Enrichment result dictionary

        Returns
        -------
        PaperEntity
            Paper entity with enrichment data
        """
        merged = enrichment_result.get("merged", {})
        biblio = merged.get("biblio", {})
        references = merged.get("references", {})
        external_ids = merged.get("external_ids", {})

        # Use merged external IDs to populate main fields if not already set
        final_doi = enrichment_result.get("doi") or external_ids.get("doi")
        final_pmid = enrichment_result.get("pmid") or external_ids.get("pmid")

        # Handle journal ISSN - convert list to first element if needed
        journal_issn = biblio.get("issn")
        if journal_issn and isinstance(journal_issn, list):
            journal_issn = journal_issn[0] if journal_issn else None

        # Create journal entity
        journal = None
        if merged.get("journal") or biblio.get("issn") or biblio.get("publisher"):
            journal_dict = {
                "display_name": merged.get("journal"),
                "issn": journal_issn,
                "publisher": biblio.get("publisher"),
            }
            journal = JournalEntity.from_enrichment_dict(journal_dict)

        return cls(
            doi=final_doi,
            pmcid=enrichment_result.get("pmcid"),
            pmid=final_pmid,
            semantic_scholar_id=enrichment_result.get("semantic_scholar_id"),
            title=merged.get("title"),
            abstract=merged.get("abstract"),
            authors=merged.get("authors"),
            citation_count=merged.get("citation_count"),
            influential_citation_count=merged.get("influential_citation_count"),
            topics=merged.get("topics"),
            fields_of_study=merged.get("fields_of_study"),
            grants=merged.get("funders"),
            is_oa=merged.get("is_oa"),
            oa_status=merged.get("oa_status"),
            oa_url=merged.get("oa_url"),
            license=merged.get("license"),
            publication_year=merged.get("publication_year"),
            publication_date=merged.get("publication_date"),
            journal=journal,
            volume=biblio.get("volume"),
            pages=biblio.get("pages"),
            issue=biblio.get("issue"),
            publisher=biblio.get("publisher"),
            issn=journal_issn,
            publication_type=biblio.get("type"),
            first_page=biblio.get("first_page"),
            last_page=biblio.get("last_page"),
            external_ids=external_ids,
            external_id_conflicts=merged.get("external_id_conflicts"),
            semantic_scholar_corpus_id=external_ids.get("semantic_scholar_corpus_id"),
            openalex_id=external_ids.get("openalex_id"),
            reference_count=references.get("count"),
            cited_by_count=references.get("cited_by_count"),
            related_works=references.get("related_works"),
        )

    PaperEntity.from_enrichment_result = from_enrichment_result


def _add_table_methods():
    """Add custom methods to TableEntity and TableRowEntity classes."""
    from pyeuropepmc.models import TableEntity, TableRowEntity

    def tablerow_post_init(self: TableRowEntity) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            object.__setattr__(self, "types", ["bibo:Row"])
        if not self.label:
            if self.cells:
                object.__setattr__(self, "label", f"Row with {len(self.cells)} cells")
            else:
                object.__setattr__(self, "label", "Untitled Row")

    TableRowEntity.post_init = tablerow_post_init

    _original_tablerow_init = TableRowEntity.__init__

    def _new_tablerow_init(self, *args, **kwargs):
        _original_tablerow_init(self, *args, **kwargs)
        self.post_init()

    TableRowEntity.__init__ = _new_tablerow_init

    def tablerow_normalize(self: TableRowEntity) -> None:
        """Normalize table row data by trimming whitespace from cells."""
        if self.cells:
            object.__setattr__(self, "cells", [c.strip() for c in self.cells if c])

    TableRowEntity.normalize = tablerow_normalize

    def table_post_init(self: TableEntity) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            object.__setattr__(self, "types", ["bibo:Table"])
        if not self.label:
            if self.table_label:
                object.__setattr__(self, "label", self.table_label)
            else:
                object.__setattr__(self, "label", "Untitled Table")
        # Set defaults for multivalued fields if not provided
        if self.headers is None:
            object.__setattr__(self, "headers", [])
        if self.rows is None:
            object.__setattr__(self, "rows", [])

    TableEntity.post_init = table_post_init

    def table_normalize(self: TableEntity) -> None:
        """Normalize table data by trimming whitespace."""
        if self.table_label is not None:
            object.__setattr__(self, "table_label", self.table_label.strip())
        if self.caption is not None:
            object.__setattr__(self, "caption", self.caption.strip())
        if self.headers is not None:
            object.__setattr__(self, "headers", [h.strip() for h in self.headers if h])

        for row in self.rows:
            row.normalize()

    TableEntity.normalize = table_normalize

    def table_validate(self: TableEntity) -> None:
        """Validate the table entity.

        Checks that all rows have consistent column counts and headers match if provided.

        Raises
        ------
        ValueError
            If rows have inconsistent column counts or headers don't match row length
        """
        if self.headers and self.rows:
            header_count = len(self.headers)
            for i, row in enumerate(self.rows):
                if row.cells and len(row.cells) != header_count:
                    raise ValueError(f"Headers must match number of columns in row {i}")

        if self.rows and len(self.rows) > 1:
            row_lengths = [len(row.cells) for row in self.rows if row.cells]
            if row_lengths and len(set(row_lengths)) > 1:
                raise ValueError("All rows must have the same number of columns")

    TableEntity.validate = table_validate


def _add_author_methods():
    """Add custom methods to AuthorEntity class."""
    from pyeuropepmc.models import AuthorEntity, Organization

    def author_post_init(self: AuthorEntity) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            object.__setattr__(self, "types", ["foaf:Person"])
        if not self.label and self.full_name:
            object.__setattr__(self, "label", self.full_name)

    AuthorEntity.post_init = author_post_init

    _original_author_init = AuthorEntity.__init__

    def _new_author_init(self, *args, **kwargs):
        _original_author_init(self, *args, **kwargs)
        self.post_init()

    AuthorEntity.__init__ = _new_author_init

    def author_normalize(self: AuthorEntity) -> None:
        """Normalize author data by trimming whitespace."""
        if self.full_name is not None:
            object.__setattr__(self, "full_name", self.full_name.strip())
        if self.first_name is not None:
            object.__setattr__(self, "first_name", self.first_name.strip())
        if self.last_name is not None:
            object.__setattr__(self, "last_name", self.last_name.strip())
        if self.orcid is not None:
            object.__setattr__(self, "orcid", self.orcid.strip())
        if self.affiliation_text is not None:
            object.__setattr__(self, "affiliation_text", self.affiliation_text.strip())
        if self.email is not None:
            object.__setattr__(self, "email", self.email.strip())

    AuthorEntity.normalize = author_normalize

    def author_validate(self: AuthorEntity) -> None:
        """Validate the author entity.

        Raises
        ------
        ValueError
            If full_name is missing, empty, or contains only whitespace
        """
        if self.full_name is None or self.full_name.strip() == "":
            raise ValueError("AuthorEntity must have either full_name or name")

    AuthorEntity.validate = author_validate

    @classmethod
    def from_enrichment_dict(cls, author_dict: dict[str, Any]) -> AuthorEntity:
        """
        Create an AuthorEntity from enrichment author dictionary.

        Parameters
        ----------
        author_dict : dict
            Author dictionary from enrichment result

        Returns
        -------
        AuthorEntity
            Author entity with enrichment data
        """
        # Convert institution dictionaries to Organization objects
        institutions_data = author_dict.get("institutions", [])
        institution_entities = []

        for inst_data in institutions_data:
            if isinstance(inst_data, dict):
                institution_entities.append(Organization.from_enrichment_dict(inst_data))
            elif isinstance(inst_data, Organization):
                institution_entities.append(inst_data)

        return cls(
            full_name=author_dict.get("name", ""),
            first_name=author_dict.get("given_name"),
            last_name=author_dict.get("family_name"),
            orcid=author_dict.get("orcid"),
            openalex_id=author_dict.get("openalex_id") or author_dict.get("id"),
            semantic_scholar_id=author_dict.get("semantic_scholar_id"),
            semantic_scholar_author_id=author_dict.get("semantic_scholar_author_id"),
            scopus_author_id=author_dict.get("scopus_author_id"),
            researcher_id=author_dict.get("researcher_id"),
            institutions=institution_entities if institution_entities else None,
            position=author_dict.get("position"),
            sources=author_dict.get("sources", []),
            affiliation_text=author_dict.get("affiliation"),
            email=author_dict.get("email"),
            orcid_works_count=author_dict.get("orcid_works_count"),
            h_index=author_dict.get("h_index"),
            citation_count=author_dict.get("citation_count"),
            paper_count=author_dict.get("paper_count"),
            data_sources=author_dict.get("data_sources", []),
            last_updated=author_dict.get("last_updated"),
        )

    AuthorEntity.from_enrichment_dict = from_enrichment_dict


def _add_figure_methods():
    """Add custom methods to FigureEntity class."""
    from pyeuropepmc.models import FigureEntity

    def figure_post_init(self: FigureEntity) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            object.__setattr__(self, "types", ["bibo:Image"])
        if not self.label:
            if self.figure_label:
                object.__setattr__(self, "label", self.figure_label)
            else:
                object.__setattr__(self, "label", "Untitled Figure")

    FigureEntity.post_init = figure_post_init

    _original_figure_init = FigureEntity.__init__

    def _new_figure_init(self, *args, **kwargs):
        _original_figure_init(self, *args, **kwargs)
        self.post_init()

    FigureEntity.__init__ = _new_figure_init

    def figure_normalize(self: FigureEntity) -> None:
        """Normalize figure data by trimming whitespace."""
        if self.figure_label is not None:
            object.__setattr__(self, "figure_label", self.figure_label.strip())
        if self.caption is not None:
            object.__setattr__(self, "caption", self.caption.strip())
        if self.graphic_uri is not None:
            object.__setattr__(self, "graphic_uri", self.graphic_uri.strip())

    FigureEntity.normalize = figure_normalize


def _add_section_methods():
    """Add custom methods to SectionEntity class."""
    from pyeuropepmc.models import SectionEntity

    def section_post_init(self: SectionEntity) -> None:
        """Initialize types and label after model initialization."""
        if not self.types:
            object.__setattr__(self, "types", ["bibo:DocumentPart", "nif:Context"])
        if not self.label:
            if self.title:
                object.__setattr__(self, "label", self.title)
            else:
                object.__setattr__(self, "label", "Untitled Section")

    SectionEntity.post_init = section_post_init

    _original_section_init = SectionEntity.__init__

    def _new_section_init(self, *args, **kwargs):
        _original_section_init(self, *args, **kwargs)
        self.post_init()

    SectionEntity.__init__ = _new_section_init

    def section_normalize(self: SectionEntity) -> None:
        """Normalize section data by trimming whitespace."""
        if self.title is not None:
            object.__setattr__(self, "title", self.title.strip())
        if self.content is not None:
            object.__setattr__(self, "content", self.content.strip())

    SectionEntity.normalize = section_normalize

    def section_validate(self: SectionEntity) -> None:
        """Validate the section entity.

        Raises
        ------
        ValueError
            If content is missing or empty
        """
        if self.content is None or self.content.strip() == "":
            raise ValueError("SectionEntity must have content")

    SectionEntity.validate = section_validate


# Apply all custom methods when this module is imported
_add_custom_methods()
_add_reference_methods()
_add_paper_methods()
_add_table_methods()
_add_author_methods()
_add_figure_methods()
_add_section_methods()
