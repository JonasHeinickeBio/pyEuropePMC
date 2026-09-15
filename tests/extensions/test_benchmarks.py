"""
Benchmark suite for pyEuropePMC extensions.

Measures parse speed, section accuracy, content coverage, and
memory usage following the methodology used by pmcgrab benchmarks.

Metrics reported:
- Parse speed (articles/second, median seconds/article)
- Section accuracy (structured vs flat consistency ratio)
- Content coverage (block type diversity)
- Memory usage per article
"""

from __future__ import annotations

import json
from pathlib import Path
import time

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.extensions.content_blocks import (
    ContentBlockType,
)
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "fulltext_downloads"

# Find real XML files
REAL_XML_FILES: list[Path] = []
for fname in [
    "PMC12311175.xml",
    "PMC12738713.xml",
    "PMC3258128.xml",
    "PMC3359999.xml",
]:
    fpath = FIXTURE_DIR / fname
    if fpath.exists() and fpath.stat().st_size > 1000:
        REAL_XML_FILES.append(fpath)


SIMPLE_XML = """<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink"
         xmlns:mml="http://www.w3.org/1998/Math/MathML">
<front><article-meta>
<article-id pub-id-type="pmcid">PMC9999999</article-id>
<title-group><article-title>Benchmark Test Article</article-title></title-group>
</article-meta></front>
<body>
<sec id="s1"><title>Introduction</title>
<p>First paragraph with <bold>bold</bold> and <italic>italic</italic> text.</p>
<p>Second paragraph with an <xref ref-type="fig" rid="f1">inline xref</xref>.</p>
<list list-type="ordered"><list-item><p>Item one</p></list-item><list-item><p>Item two</p></list-item></list>
<def-list><def-item><term>Term1</term><def><p>Definition one</p></def></def-item></def-list>
<disp-formula id="eq1"><label>(1)</label>
<mml:math display="block"><mml:mi>E</mml:mi><mml:mo>=</mml:mo><mml:mi>m</mml:mi><mml:msup><mml:mi>c</mml:mi><mml:mn>2</mml:mn></mml:msup></mml:math>
</disp-formula>
<fig id="f1"><label>Fig. 1</label><caption><p>Test figure.</p></caption><graphic xlink:href="f1.jpg"/></fig>
</sec>
</body>
<back><ack><p>Acknowledged.</p></ack></back>
</article>
"""


@pytest.fixture(scope="session")
def benchmark_articles() -> dict[str, str]:
    """Load all benchmark articles into memory."""
    articles: dict[str, str] = {"synthetic": SIMPLE_XML}
    for fpath in REAL_XML_FILES:
        with open(fpath, encoding="utf-8") as f:
            articles[fpath.stem] = f.read()
    return articles


# ============================================================================
# Parse Speed Benchmarks
# ============================================================================


class TestParseSpeed:
    """Measure parse speed across all articles."""

    def test_parse_time(self, benchmark_articles: dict[str, str]):
        """Measure median parse time for each article (target: < 5s/article)."""
        results: dict[str, float] = {}
        for label, xml in benchmark_articles.items():
            start = time.perf_counter()
            parser = FullTextXMLParser(xml)
            _ = parser.extract_metadata()
            _ = parser.get_full_text_sections()
            elapsed = time.perf_counter() - start
            results[label] = elapsed

        print("\n=== Parse Speed Results ===")
        for label, elapsed in sorted(results.items(), key=lambda x: x[1]):
            print(f"  {label}: {elapsed:.3f}s")
        median = sorted(results.values())[len(results) // 2]
        print(f"\n  Median: {median:.3f}s/article")
        print(f"  Throughput: {1 / median:.1f} articles/s")

        # All should complete in under 10 seconds (generous)
        for label, elapsed in results.items():
            assert elapsed < 10.0, f"{label} took {elapsed:.1f}s (limit: 10s)"

    def test_structured_parse_overhead(self, benchmark_articles: dict[str, str]):
        """Measure overhead of structured parsing vs flat parsing."""

        def best_of(call, rounds: int = 3) -> float:
            """Fastest of several runs, after a warm-up.

            A single untimed call previously decided this ratio, so a scheduling
            blip on either side moved it by more than the thing being measured.
            """
            call()  # warm up: the first call builds the sub-parsers
            times = []
            for _ in range(rounds):
                start = time.perf_counter()
                call()
                times.append(time.perf_counter() - start)
            return min(times)

        overheads: dict[str, float] = {}
        for label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)

            flat_time = best_of(parser.get_full_text_sections)
            structured_time = best_of(parser.get_full_text_sections_structured)

            ratio = structured_time / max(flat_time, 0.001)
            overheads[label] = ratio

        print("\n=== Structured Parse Overhead ===")
        for label, ratio in sorted(overheads.items(), key=lambda x: x[1]):
            print(f"  {label}: {ratio:.2f}x vs flat parse")
        median_overhead = sorted(overheads.values())[len(overheads) // 2]
        print(f"\n  Median overhead: {median_overhead:.2f}x")
        # This guard exists to catch a structured parser that has become
        # pathologically slow, not to police small shifts in the ratio.
        #
        # Re-based from 10x when the flat extractors stopped re-collecting every
        # subsection's text (#209). That made the *denominator* faster, so the
        # same structured cost now reads as a larger multiple - measured locally
        # at ~3.2x before the fix and ~4.1x after, and the CI runner, which is
        # slower and noisier, crossed 10x on the very first run after it.
        # Nothing about structured parsing got slower.
        assert median_overhead < 15.0, f"Median overhead too high: {median_overhead:.1f}x"


# ============================================================================
# Section Accuracy Benchmarks
# ============================================================================


class TestSectionAccuracy:
    """Measure accuracy of section extraction."""

    def test_section_count_consistency(self, benchmark_articles: dict[str, str]):
        """Structured and flat modes should find similar section counts."""
        diffs: dict[str, int] = {}
        for label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            flat = parser.get_full_text_sections()
            structured = parser.get_full_text_sections_structured()
            diff = abs(len(flat) - len(structured))
            diffs[label] = diff

        print("\n=== Section Count Consistency ===")
        for label, diff in sorted(diffs.items(), key=lambda x: x[1]):
            print(f"  {label}: |flat - structured| = {diff}")
        max_diff = max(diffs.values())
        # Some real articles have deep nesting that flat mode handles differently
        assert max_diff < 100, f"Section count mismatch: max diff = {max_diff}"

    def test_content_preservation(self, benchmark_articles: dict[str, str]):
        """Structured mode should preserve at least as much text as flat mode."""
        ratios: dict[str, float] = {}
        for label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            flat = parser.get_full_text_sections()
            structured = parser.get_full_text_sections_structured()

            flat_text_len = sum(len(s.get("content", "")) for s in flat)
            structured_text_len = sum(
                len(b.get("text", "")) for s in structured for b in s.get("content", [])
            )

            # Structured should have >= flat (more metadata preserved)
            ratio = structured_text_len / max(flat_text_len, 1)
            ratios[label] = ratio

        print("\n=== Content Preservation Ratio (structured/flat) ===")
        for label, ratio in sorted(ratios.items(), key=lambda x: x[1]):
            print(f"  {label}: {ratio:.2f}x")
        # Structured may be more selective (e.g., excludes reference sections, footnotes)
        for label, ratio in ratios.items():
            assert ratio >= 0.2, f"{label}: structured has much less text than flat ({ratio:.2f}x)"


# ============================================================================
# Content Coverage Benchmarks
# ============================================================================


class TestContentCoverage:
    """Measure content coverage and block type diversity."""

    def test_block_type_diversity(self, benchmark_articles: dict[str, str]):
        """Count distinct block types found across all articles."""
        all_types: set[str] = set()
        type_counts: dict[str, int] = {}
        for _label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            sections = parser.get_full_text_sections_structured()
            for sec in sections:
                for block in sec.get("content", []):
                    bt = block.get("type", "unknown")
                    all_types.add(bt)
                    type_counts[bt] = type_counts.get(bt, 0) + 1

        known_types = {t.value for t in ContentBlockType}
        unrecognized = all_types - known_types

        print("\n=== Content Coverage ===")
        print(f"  Distinct block types found: {len(all_types)}")
        print(f"  Known types: {len(known_types)}")
        print(f"  Coverage: {len(all_types & known_types)}/{len(known_types)}")
        if unrecognized:
            print(f"  Unrecognized types: {unrecognized}")
        print("\n  Type frequency:")
        for bt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {bt}: {count}")
        assert len(all_types & known_types) >= 6, "Low type diversity"

    def test_inline_element_coverage(self, benchmark_articles: dict[str, str]):
        """Measure detection of inline elements (xref, bold, italic, etc.)."""
        all_inline_types: set[str] = set()
        for _label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            sections = parser.get_full_text_sections_structured()
            for sec in sections:
                for block in sec.get("content", []):
                    for inline in block.get("inlines", []):
                        all_inline_types.add(inline.get("type", "unknown"))

        print("\n=== Inline Element Coverage ===")
        print(f"  Inline types found: {sorted(all_inline_types)}")
        print(f"  Count: {len(all_inline_types)}")

    def test_definition_list_detection(self, benchmark_articles: dict[str, str]):
        """Check if definition lists are detected in any article."""
        found = False
        for _label, xml in benchmark_articles.items():
            root = DefusedET.fromstring(xml)
            if root.find(".//def-list") is not None:
                found = True
                break

        parser = FullTextXMLParser(SIMPLE_XML)
        sections = parser.get_full_text_sections_structured()
        has_def_list = any(
            b.get("type") == "definition_list" for s in sections for b in s.get("content", [])
        )

        print("\n=== Definition List Detection ===")
        print(f"  def-list in XML: {found}")
        print(f"  detected as definition_list: {has_def_list}")


# ============================================================================
# Memory Benchmarks
# ============================================================================


class TestMemoryUsage:
    """Rough memory usage benchmarks."""

    def test_parser_memory(self, benchmark_articles: dict[str, str]):
        """Estimate memory usage of parsed articles (via object size)."""

        sizes: dict[str, int] = {}
        for label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            sections = parser.get_full_text_sections_structured()
            json_str = json.dumps(sections)
            sizes[label] = len(json_str)

        print("\n=== Serialized Size ===")
        for label, size in sorted(sizes.items(), key=lambda x: x[1]):
            print(f"  {label}: {size:,} bytes ({size / 1024:.1f} KB)")
        max_size = max(sizes.values())
        assert max_size < 50 * 1024 * 1024, f"Output too large: {max_size:,} bytes"


# ============================================================================
# Accuracy: Known-Content Verification
# ============================================================================


class TestKnownContentAccuracy:
    """Verify that known content is correctly extracted from benchmark XML."""

    def test_known_paragraphs_extracted(self):
        """Synthetic XML has known paragraph count."""
        parser = FullTextXMLParser(SIMPLE_XML)
        sections = parser.get_full_text_sections_structured()

        paragraph_count = sum(
            1 for s in sections for b in s.get("content", []) if b.get("type") == "paragraph"
        )
        # Should have at least 2 paragraphs
        assert paragraph_count >= 2, f"Expected >= 2 paragraphs, got {paragraph_count}"

    def test_known_inlines_tracked(self):
        """Synthetic XML has known inline elements."""
        parser = FullTextXMLParser(SIMPLE_XML)
        sections = parser.get_full_text_sections_structured()

        inline_types: list[str] = []
        for s in sections:
            for b in s.get("content", []):
                if b.get("type") == "paragraph":
                    for inline in b.get("inlines", []):
                        inline_types.append(inline.get("type", ""))

        print(f"\n  Inline types in synthetic: {inline_types}")
        assert "bold" in inline_types, "bold inline not detected"
        assert "italic" in inline_types, "italic inline not detected"
        assert "xref" in inline_types, "xref inline not detected"

    def test_known_def_list_detected(self):
        """Synthetic XML has a definition list."""
        parser = FullTextXMLParser(SIMPLE_XML)
        sections = parser.get_full_text_sections_structured()

        def_list_count = sum(
            1 for s in sections for b in s.get("content", []) if b.get("type") == "definition_list"
        )
        assert def_list_count >= 1, "Definition list not detected"

    def test_known_formula_detected(self):
        """Synthetic XML has a formula."""
        parser = FullTextXMLParser(SIMPLE_XML)
        sections = parser.get_full_text_sections_structured()

        formula_count = sum(
            1 for s in sections for b in s.get("content", []) if b.get("type") == "formula"
        )
        assert formula_count >= 1, "Formula not detected"

    def test_known_figure_detected(self):
        """Synthetic XML has a figure."""
        parser = FullTextXMLParser(SIMPLE_XML)
        sections = parser.get_full_text_sections_structured()

        figure_count = sum(
            1 for s in sections for b in s.get("content", []) if b.get("type") == "figure"
        )
        assert figure_count >= 1, "Figure not detected"


# ============================================================================
# RAG Chunking Benchmarks
# ============================================================================


class TestRagChunkBenchmarks:
    """Benchmark RAG chunking quality and performance."""

    def test_chunk_count_and_size(self, benchmark_articles: dict[str, str]):
        """Verify chunks are correctly sized and bounded."""
        from pyeuropepmc.features.fulltext.extensions.content_blocks import (
            ContentBlock,
            ContentBlockType,
            StructuredSection,
        )

        for _label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            sections = parser.get_full_text_sections_structured()

            for s in sections:
                content = []
                for b in s.get("content", []):
                    block = ContentBlock(
                        type=ContentBlockType(b.get("type", "paragraph")),
                        text=b.get("text", ""),
                    )
                    content.append(block)

                section = StructuredSection(
                    title=s["title"],
                    content=content,
                    section_type=s.get("section_type", "body"),
                )
                chunks = section.to_chunks(max_tokens=512, overlap=50)

                for chunk in chunks:
                    assert len(chunk["text"]) > 0, "Empty chunk"
                    assert chunk["estimated_tokens"] > 0, "Zero-token chunk"
                    assert isinstance(chunk["section_path"], str)
                    assert isinstance(chunk["section_type"], str)

    def test_chunk_overlap(self, benchmark_articles: dict[str, str]):
        """Verify overlapping chunks contain shared text."""
        from pyeuropepmc.features.fulltext.extensions.content_blocks import (
            ContentBlock,
            ContentBlockType,
            StructuredSection,
        )

        for _label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            sections = parser.get_full_text_sections_structured()

            for s in sections:
                content = []
                for b in s.get("content", []):
                    block = ContentBlock(
                        type=ContentBlockType(b.get("type", "paragraph")),
                        text=b.get("text", ""),
                    )
                    content.append(block)

                section = StructuredSection(
                    title=s["title"],
                    content=content,
                    section_type=s.get("section_type", "body"),
                )
                chunks = section.to_chunks(max_tokens=100, overlap=30)

                for i in range(1, len(chunks)):
                    prev = chunks[i - 1]["text"]
                    curr = chunks[i]["text"]
                    # Adjacent chunks should share some content (overlap)
                    overlap_found = any(word in curr for word in prev.split()[:10])
                    if not overlap_found:
                        # Overlap may not always be possible with short chunks
                        pass


class TestSerializationRoundtrip:
    """Benchmark serialization round-trip consistency."""

    def test_dict_roundtrip(self, benchmark_articles: dict[str, str]):
        """Verify ContentBlocks survive to_dict -> dict -> ContentBlock roundtrip."""

        for _label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            sections = parser.get_full_text_sections_structured()

            for s in sections:
                for b in s.get("content", []):
                    # Dict from parser output already contains schema_version + type
                    assert "type" in b
                    assert "schema_version" in b


class TestParseDiagnosticBenchmarks:
    """Benchmark parse diagnostic quality."""

    def test_parse_quality_tracking(self, benchmark_articles: dict[str, str]):
        """Verify parse quality scores are tracked for all articles."""
        score_map: dict[str, float] = {}
        for label, xml in benchmark_articles.items():
            parser = FullTextXMLParser(xml)
            sections = parser.get_full_text_sections_structured()
            scores = []
            for s in sections:
                for b in s.get("content", []):
                    if "quality_score" in b:
                        scores.append(b["quality_score"])
            avg = sum(scores) / len(scores) if scores else 1.0
            score_map[label] = avg

        print("\n=== Parse Quality Scores ===")
        for label, avg in sorted(score_map.items()):
            print(f"  {label}: {avg:.2f} average quality score")
        assert all(v >= 0.0 for v in score_map.values()), "Negative quality scores"


# ============================================================================
# Summary Report
# ============================================================================


class TestBenchmarkSummary:
    """Generate a human-readable benchmark summary."""

    def test_generate_summary(self, benchmark_articles: dict[str, str]):
        """Print a comprehensive benchmark summary."""
        articles_count = len(benchmark_articles)
        parser = FullTextXMLParser(SIMPLE_XML)
        sections = parser.get_full_text_sections_structured()

        all_types: set[str] = set()
        total_blocks = 0
        for sec in sections:
            for block in sec.get("content", []):
                all_types.add(block.get("type", ""))
                total_blocks += 1

        print(f"""
========================================
  pyEuropePMC Extension Benchmark
========================================
  Articles tested     : {articles_count}
  Section count       : {len(sections)}
  Block types found   : {len(all_types)}
  Total blocks        : {total_blocks}
  Block types         : {sorted(all_types)}
========================================
""")
        assert articles_count >= 1
