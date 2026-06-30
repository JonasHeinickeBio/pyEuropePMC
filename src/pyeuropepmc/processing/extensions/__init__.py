"""
Extensions for the pyEuropePMC XML parser.

This package provides extended functionality for the fulltext XML parser:

1. **Content Blocks** - Typed content blocks preserving document structure
   for RAG/LLM pipelines (based on pmcgrab approach).
2. **lxml Backend** - Optional high-performance lxml parser backend.
3. **Peer Review** - Extraction of peer review materials from sub-articles.
4. **MathML Conversion** - MathML to LaTeX conversion.
5. **JATS4R Validation** - Compliance checking against NISO recommendations.
6. **Batch Processing** - Concurrent processing with rate limiting.
7. **Image Fetcher** - Asset reference extraction and downloading.
8. **Reference Resolver** - API-based reference enrichment.
9. **Pydantic Helpers** - Pydantic v2 model generation from dataclasses.
10. **Local Processing** - File/directory convenience methods.

All modules are designed to be modular, DRY, and reusable, leveraging the
existing ``BaseParser`` infrastructure and ``XMLHelper`` utilities.
"""

from pyeuropepmc.processing.extensions.batch_processor import (
    BatchProcessor,
    BatchResult,
    ProcessingResult,
)
from pyeuropepmc.processing.extensions.content_blocks import (
    ContentBlock,
    ContentBlockExtractor,
    ContentBlockType,
    StructuredSection,
)
from pyeuropepmc.processing.extensions.image_fetcher import (
    AssetFetchPolicy,
    AssetRef,
    AssetType,
    ImageFetcher,
)
from pyeuropepmc.processing.extensions.jats4r import (
    JATS4RValidator,
    ValidationFinding,
    ValidationReport,
)
from pyeuropepmc.processing.extensions.local_processing import (
    LocalXMLProcessor,
    extract_article_id_from_xml,
    parse_bits_book,
    parse_xml_directory,
    parse_xml_file,
    process_biorxiv_manifest,
    process_single_pmc,
)
from pyeuropepmc.processing.extensions.lxml_backend import (
    LXMLParser,
    is_lxml_available,
)
from pyeuropepmc.processing.extensions.mathml import MathMLConverter
from pyeuropepmc.processing.extensions.peer_review import (
    PeerReviewExtractor,
    PeerReviewMaterial,
    PeerReviewSet,
    PeerReviewType,
)
from pyeuropepmc.processing.extensions.reference_resolver import (
    ReferenceResolver,
    ResolvedReference,
)

# Conditionally import pydantic helpers if pydantic is installed
try:
    from pyeuropepmc.processing.extensions.pydantic_helpers import (  # noqa: F401
        PydanticModelGenerator,
        dataclass_to_pydantic,
    )

    _HAS_PYDANTIC = True
except ImportError:
    _HAS_PYDANTIC = False


__all__ = [
    # Content Blocks
    "ContentBlock",
    "ContentBlockType",
    "ContentBlockExtractor",
    "StructuredSection",
    # lxml Backend
    "LXMLParser",
    "is_lxml_available",
    # Peer Review
    "PeerReviewExtractor",
    "PeerReviewMaterial",
    "PeerReviewSet",
    "PeerReviewType",
    # MathML
    "MathMLConverter",
    # JATS4R
    "JATS4RValidator",
    "ValidationFinding",
    "ValidationReport",
    # Batch Processing
    "BatchProcessor",
    "BatchResult",
    "ProcessingResult",
    # Image Fetcher
    "AssetFetchPolicy",
    "AssetRef",
    "AssetType",
    "ImageFetcher",
    # Reference Resolver
    "ReferenceResolver",
    "ResolvedReference",
    # Local Processing
    "LocalXMLProcessor",
    "extract_article_id_from_xml",
    "parse_bits_book",
    "parse_xml_directory",
    "parse_xml_file",
    "process_biorxiv_manifest",
    "process_single_pmc",
]

# Conditionally include pydantic helpers only when available
if _HAS_PYDANTIC:
    __all__.extend(["PydanticModelGenerator", "dataclass_to_pydantic"])
