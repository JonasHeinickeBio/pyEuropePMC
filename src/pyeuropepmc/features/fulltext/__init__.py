"""Full-text XML parsing and analysis.

This slice provides tools for parsing, normalizing, and analyzing
full-text XML from Europe PMC, including JATS parsing, figure extraction,
full-text indexing, rhetorical highlighting, and annotation processing.
"""

from pyeuropepmc.features.fulltext.fulltext_client import (
    DownloadReport,
    DownloadStats,
    FullTextClient,
    ProgressInfo,
    RateLimiter,
    WorkerStat,
)
from pyeuropepmc.features.fulltext.fulltext_parser import (
    DocumentSchema,
    ElementPatterns,
    FullTextXMLParser,
)
from pyeuropepmc.features.fulltext.jats_normalizer import (
    JATSNormalizer,
    NormalizationConfig,
    classify_section,
    normalize_jats_text,
    normalize_jats_xml,
)
from pyeuropepmc.features.fulltext.figures import (
    FigureExtractor,
    FigureFormat,
    FigureInfo,
    extract_figures_from_pmc,
    extract_tables_from_pmc,
)
from pyeuropepmc.features.fulltext.index import (
    FullTextIndex,
    IndexEntry,
    SearchResult,
    create_index,
    open_index,
)
from pyeuropepmc.features.fulltext.rhetorical import (
    HighlightedDocument,
    RhetoricalHighlighter,
    RhetoricalRole,
    SentenceAnnotation,
    highlight_pdf_text,
    highlight_text,
)
from pyeuropepmc.features.fulltext.annotation_parser import (
    AnnotationParser,
    extract_entities,
    extract_relationships,
    extract_sentences,
    normalize_annotations_response,
    parse_annotations,
)

__all__ = [
    "AnnotationParser",
    "DocumentSchema",
    "DownloadReport",
    "DownloadStats",
    "ElementPatterns",
    "FigureExtractor",
    "FigureFormat",
    "FigureInfo",
    "FullTextClient",
    "FullTextIndex",
    "FullTextXMLParser",
    "HighlightedDocument",
    "IndexEntry",
    "JATSNormalizer",
    "NormalizationConfig",
    "ProgressInfo",
    "RateLimiter",
    "RhetoricalHighlighter",
    "RhetoricalRole",
    "SearchResult",
    "SentenceAnnotation",
    "WorkerStat",
    "classify_section",
    "create_index",
    "extract_entities",
    "extract_figures_from_pmc",
    "extract_relationships",
    "extract_sentences",
    "extract_tables_from_pmc",
    "highlight_pdf_text",
    "highlight_text",
    "normalize_annotations_response",
    "normalize_jats_text",
    "normalize_jats_xml",
    "open_index",
    "parse_annotations",
]
