"""Real-world showcase: UnifiedSearch over 50 queries.

Shows how well the Europe-PMC-anchored federated search performs — how much
of each merged result set is anchored on Europe PMC, what the other sources
add on top, the dedup rate, and per-source reliability / latency.

    pytest tests/integration/test_showcase_unified_search.py --run-integration -s
"""

from __future__ import annotations

import pytest

from pyeuropepmc.features.search import UnifiedSearch

from _showcase import Timer, pct, summary_stats, write_report, _fmt_hist

QUERIES: list[str] = [
    "CRISPR base editing off-target",
    "long COVID chronic fatigue",
    "GLP-1 receptor agonist weight loss",
    "AlphaFold protein structure prediction",
    "mRNA vaccine lipid nanoparticle delivery",
    "tumor microenvironment immune evasion",
    "gut microbiome depression axis",
    "single cell RNA sequencing atlas",
    "antibiotic resistance gene transfer",
    "Alzheimer amyloid beta clearance",
    "CAR-T cell therapy solid tumors",
    "photosynthesis quantum coherence",
    "graphene biosensor glucose",
    "machine learning drug discovery",
    "climate change vector borne disease",
    "senescence cellular reprogramming aging",
    "organoid brain development model",
    "wastewater surveillance SARS-CoV-2",
    "ferroptosis cancer cell death",
    "epigenetic clock DNA methylation",
    "phage therapy multidrug resistant infection",
    "exosome biomarker liquid biopsy",
    "CRISPR screen functional genomics",
    "immune checkpoint inhibitor resistance",
    "microplastics human health exposure",
    "deep learning protein design",
    "circadian rhythm metabolism insulin",
    "tumor mutational burden immunotherapy response",
    "stem cell derived pancreatic beta cells",
    "antimicrobial peptide mechanism membrane",
    "spatial transcriptomics tissue architecture",
    "mitochondrial dysfunction neurodegeneration",
    "vaccine hesitancy social media misinformation",
    "CRISPR gene drive malaria mosquito",
    "PROTAC targeted protein degradation",
    "neoantigen cancer vaccine personalized",
    "air pollution cardiovascular mortality",
    "synthetic biology metabolic engineering",
    "T cell exhaustion transcription factor",
    "blood brain barrier drug delivery nanoparticle",
    "obesity adipose tissue inflammation",
    "antiviral drug broad spectrum coronavirus",
    "wearable sensor continuous health monitoring",
    "tau propagation neurodegeneration prion",
    "CRISPR diagnostics SHERLOCK DETECTR",
    "immunotherapy microbiome modulation",
    "quantum computing molecular simulation",
    "gene therapy AAV capsid engineering",
    "insulin resistance skeletal muscle signaling",
    "cancer cachexia muscle wasting mechanism",
    "RNA splicing disease therapeutic targeting",
]


@pytest.mark.integration
def test_unified_search_showcase() -> None:
    assert len(QUERIES) == 50

    sources = ["europepmc", "pubmed", "arxiv", "openalex", "semantic_scholar"]
    searcher = UnifiedSearch(sources=sources, primary="europepmc", timeout=40)

    per_item: list[dict] = []
    source_hit_totals: dict[str, int] = dict.fromkeys(sources, 0)
    source_fail_counts: dict[str, int] = dict.fromkeys(sources, 0)
    added_by_source_totals: dict[str, int] = {}
    total_raw = total_merged = total_epmc_anchored = 0
    latencies: list[float] = []
    epmc_share: list[float] = []

    try:
        for q in QUERIES:
            with Timer() as t:
                try:
                    merged, report = searcher.search(q, limit=15)
                except Exception as exc:  # noqa: BLE001
                    per_item.append({"query": q[:40], "error": type(exc).__name__})
                    continue
            latencies.append(t.elapsed)

            meta = report.metadata
            counts = meta.get("source_counts", {})
            errors = meta.get("source_errors", {})
            raw = sum(counts.values())
            anchored = meta.get("primary_records", 0)
            added = meta.get("added_by_source", {})

            total_raw += raw
            total_merged += len(merged)
            total_epmc_anchored += anchored
            for s in sources:
                source_hit_totals[s] += counts.get(s, 0)
                if s in errors:
                    source_fail_counts[s] += 1
            for s, n in added.items():
                added_by_source_totals[s] = added_by_source_totals.get(s, 0) + n
            if merged:
                epmc_share.append(pct(anchored, len(merged)))

            per_item.append(
                {
                    "query": q[:40],
                    "raw": raw,
                    "merged": len(merged),
                    "epmc_anchored": anchored,
                    "added": sum(added.values()),
                    "dedup_%": round(report.dedup_rate * 100, 1),
                    "sec": round(t.elapsed, 1),
                    "failed_sources": ",".join(errors) or "-",
                }
            )
    finally:
        searcher.close()

    ok = [r for r in per_item if "error" not in r]
    assert len(ok) >= 45, f"too many query failures: {50 - len(ok)}"

    headline = {
        "queries": len(QUERIES),
        "queries_ok": len(ok),
        "raw hits (all sources)": total_raw,
        "merged results": total_merged,
        "dedup rate": f"{pct(total_raw - total_merged, total_raw):.1f}%",
        "merged results anchored on Europe PMC": f"{total_epmc_anchored} "
        f"({pct(total_epmc_anchored, total_merged):.1f}%)",
        "records added by satellite sources": sum(added_by_source_totals.values()),
        "latency (s)": summary_stats(latencies),
    }

    sections = {
        "Per-source raw hits (sum over 50 queries)": _fmt_hist(source_hit_totals, total_raw),
        "Records contributed on top of Europe PMC": _fmt_hist(
            added_by_source_totals, max(sum(added_by_source_totals.values()), 1)
        ),
        "Per-source failure count (of 50)": [
            f"  {s:<20} {n:>3}" for s, n in sorted(source_fail_counts.items())
        ],
    }

    write_report(
        "unified_search", headline=headline, per_item=per_item, sections=sections
    )

    # Europe PMC should genuinely be the spine.
    assert pct(total_epmc_anchored, total_merged) >= 40, (
        "Europe PMC anchors <40% of merged results — not acting as the base"
    )
    # And the other sources should still be adding value.
    assert sum(added_by_source_totals.values()) > 0
