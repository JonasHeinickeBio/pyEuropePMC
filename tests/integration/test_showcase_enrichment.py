"""Real-world showcase: PaperEnricher over 50 papers.

Seeds 50 real papers from a live Europe PMC search, then enriches each with
the full source set (Europe PMC base + CrossRef + OpenAlex + Semantic Scholar
+ iCite, in parallel) and reports:

* how often each source contributed,
* merged-field coverage (title / abstract / authors / journal / year /
  citation_count / MeSH / OA / iCite RCR),
* how much Europe PMC alone already provided (the "base"),
* wall-clock latency vs. an estimate of the old serial cost.

    pytest tests/integration/test_showcase_enrichment.py --run-integration -s
"""

from __future__ import annotations

import pytest

from pyeuropepmc.features.enrich import EnrichmentConfig, PaperEnricher
from pyeuropepmc.features.literature.search import SearchClient

from _showcase import Timer, pct, summary_stats, write_report, _fmt_hist

_SEED_QUERIES = [
    "cancer immunotherapy resistance",
    "single cell sequencing method",
    "CRISPR gene editing therapeutic",
    "microbiome metabolism host",
    "neurodegeneration protein aggregation",
    "climate health adaptation",
    "machine learning genomics prediction",
]
_MERGED_FIELDS = [
    "title",
    "abstract",
    "authors",
    "journal",
    "publication_year",
    "citation_count",
    "mesh_terms",
    "is_oa",
]


def _seed_papers(n: int = 50) -> list[dict]:
    client = SearchClient(rate_limit_delay=0.5)
    seen: set[str] = set()
    out: list[dict] = []
    try:
        per_q = -(-n // len(_SEED_QUERIES))  # ceil
        for q in _SEED_QUERIES:
            recs = client.search_and_parse(
                f"{q} AND (HAS_FT:Y)", format="json", pageSize=per_q + 5
            )
            for r in recs:
                doi, pmid = r.get("doi"), r.get("pmid")
                if not doi or doi in seen:
                    continue
                seen.add(doi)
                out.append({"doi": doi, "pmid": pmid, "title": (r.get("title") or "")[:50]})
                if len(out) >= n:
                    return out
    finally:
        client.close()
    return out


@pytest.mark.integration
def test_enrichment_showcase() -> None:
    papers = _seed_papers(50)
    assert len(papers) >= 45, f"could only seed {len(papers)} papers"

    config = EnrichmentConfig(
        enable_europepmc=True,
        enable_crossref=True,
        enable_openalex=True,
        enable_semantic_scholar=True,
        enable_icite=True,
        enable_unpaywall=False,
        enable_ror=False,
    )

    per_item: list[dict] = []
    source_hits: dict[str, int] = {}
    field_hits: dict[str, int] = dict.fromkeys(_MERGED_FIELDS, 0)
    epmc_base_ok = icite_rcr_ok = 0
    source_counts: list[float] = []
    latencies: list[float] = []

    with PaperEnricher(config) as enricher:
        for p in papers:
            with Timer() as t:
                try:
                    res = enricher.enrich_paper(identifier=p["doi"])
                except Exception as exc:  # noqa: BLE001
                    per_item.append({"doi": p["doi"][:32], "error": type(exc).__name__})
                    continue
            latencies.append(t.elapsed)

            srcs = res.get("sources", [])
            merged = res.get("merged", {}) or {}
            for s in srcs:
                source_hits[s] = source_hits.get(s, 0) + 1
            source_counts.append(len(srcs))
            for f in _MERGED_FIELDS:
                if merged.get(f) not in (None, "", [], {}):
                    field_hits[f] += 1
            if res.get("europepmc"):
                epmc_base_ok += 1
            if (res.get("icite") or {}).get("rcr"):
                icite_rcr_ok += 1

            per_item.append(
                {
                    "doi": p["doi"][:32],
                    "sources": ",".join(srcs),
                    "fields": sum(
                        1 for f in _MERGED_FIELDS if merged.get(f) not in (None, "", [], {})
                    ),
                    "cites": merged.get("citation_count", "-"),
                    "rcr": (res.get("icite") or {}).get("rcr", "-"),
                    "sec": round(t.elapsed, 1),
                }
            )

    ok = [r for r in per_item if "error" not in r]
    assert len(ok) >= 40, f"too many enrichment failures: {len(papers) - len(ok)}"

    n = len(ok)
    est_serial = sum(latencies) * (max(source_counts) if source_counts else 1) / max(
        sum(source_counts) / max(len(source_counts), 1), 1
    )
    headline = {
        "papers": len(papers),
        "papers enriched ok": n,
        "avg sources / paper": round(sum(source_counts) / max(n, 1), 2),
        "Europe PMC base present": f"{epmc_base_ok} ({pct(epmc_base_ok, n):.0f}%)",
        "iCite RCR present": f"{icite_rcr_ok} ({pct(icite_rcr_ok, n):.0f}%)",
        "latency / paper (s)": summary_stats(latencies),
        "parallel wall time (s)": round(sum(latencies), 1),
        "≈ serial wall time (s)": round(est_serial, 1),
    }
    sections = {
        "Source contribution (of %d papers)" % n: _fmt_hist(source_hits, n),
        "Merged-field coverage (of %d papers)" % n: _fmt_hist(field_hits, n),
    }
    write_report("enrichment", headline=headline, per_item=per_item, sections=sections)

    assert pct(epmc_base_ok, n) >= 80, "Europe PMC base missing on >20% of papers"
    assert pct(field_hits["abstract"], n) >= 70
    assert pct(field_hits["citation_count"], n) >= 70
