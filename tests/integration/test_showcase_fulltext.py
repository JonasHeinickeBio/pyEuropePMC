"""Real-world showcase: full-text XML download over 50 papers.

Seeds 50 real open-access papers from a live Europe PMC search, then for each:

1. tries **Europe PMC only** (``extra_strategies=False``),
2. if that fails, retries with the **extra strategies** (PMC OA service,
   NCBI efetch, BioC-PMC, DOI negotiation, bioRxiv).

Reports the overall success rate, which step won each paper, how many the
extra strategies rescued, and download sizes / latency.

    pytest tests/integration/test_showcase_fulltext.py --run-integration -s
"""

from __future__ import annotations

from _showcase import Timer, _fmt_hist, pct, summary_stats, write_report
import pytest

from pyeuropepmc.core.exceptions import FullTextError
from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient
from pyeuropepmc.features.literature.search import SearchClient

_SEED_QUERIES = [
    "cancer immunotherapy",
    "crispr genome editing",
    "covid-19 vaccine",
    "single cell transcriptomics",
    "alzheimer disease biomarker",
    "microbiome gut brain",
    "climate change health",
    "deep learning medical imaging",
]


def _seed_pmcids(n: int = 50) -> list[dict]:
    client = SearchClient(rate_limit_delay=0.5)
    seen: set[str] = set()
    out: list[dict] = []
    try:
        per_q = -(-n // len(_SEED_QUERIES))
        for q in _SEED_QUERIES:
            recs = client.search_and_parse(
                f"{q} AND (OPEN_ACCESS:y AND IN_EPMC:y)", format="json", pageSize=per_q + 5
            )
            for r in recs:
                pmcid = r.get("pmcid")
                if not pmcid or pmcid in seen:
                    continue
                seen.add(pmcid)
                out.append({"pmcid": pmcid, "doi": r.get("doi")})
                if len(out) >= n:
                    return out
    finally:
        client.close()
    return out


@pytest.mark.integration
@pytest.mark.timeout(1800)
def test_fulltext_xml_showcase(tmp_path) -> None:
    papers = _seed_pmcids(50)
    assert len(papers) >= 45, f"could only seed {len(papers)} PMCIDs"

    client = FullTextClient(enable_cache=False, rate_limit_delay=0.34)

    per_item: list[dict] = []
    winner_hist: dict[str, int] = {}
    sizes: list[float] = []
    latencies: list[float] = []
    epmc_only_ok = extra_rescued = total_ok = 0

    for _i, p in enumerate(papers):
        pmcid, doi = p["pmcid"], p["doi"]
        out = tmp_path / f"{pmcid}.xml"
        row: dict = {"pmcid": pmcid}

        with Timer() as t:
            # Pass 1: Europe PMC only
            epmc_ok = False
            try:
                client.download_xml_by_pmcid(pmcid, output_path=out, extra_strategies=False)
                epmc_ok = True
            except FullTextError:
                pass
            except Exception as exc:  # noqa: BLE001
                row["error"] = type(exc).__name__

            winner = client.last_xml_source if epmc_ok else None

            # Pass 2: extra strategies for the EPMC misses
            if not epmc_ok and "error" not in row:
                try:
                    client.download_xml_by_pmcid(
                        pmcid, output_path=out, doi=doi, extra_strategies=True
                    )
                    winner = client.last_xml_source
                    extra_rescued += 1
                except FullTextError:
                    winner = None
                except Exception as exc:  # noqa: BLE001
                    row["error"] = type(exc).__name__
                    winner = None

        latencies.append(t.elapsed)
        if epmc_ok:
            epmc_only_ok += 1
        if winner and out.exists() and out.stat().st_size > 0:
            total_ok += 1
            winner_hist[winner] = winner_hist.get(winner, 0) + 1
            sizes.append(out.stat().st_size / 1024)

        row.update(
            {
                "won_by": winner or "-",
                "kb": round(out.stat().st_size / 1024, 1) if out.exists() else 0,
                "sec": round(t.elapsed, 1),
            }
        )
        per_item.append(row)

    n = len(papers)
    headline = {
        "papers (OA, in EPMC)": n,
        "XML retrieved": f"{total_ok} ({pct(total_ok, n):.0f}%)",
        "Europe PMC alone": f"{epmc_only_ok} ({pct(epmc_only_ok, n):.0f}%)",
        "rescued by extra strategies": extra_rescued,
        "download size KB": summary_stats(sizes),
        "latency / paper (s)": summary_stats(latencies),
    }
    sections = {
        "Which step produced the XML": _fmt_hist(winner_hist, max(total_ok, 1)),
    }
    write_report("fulltext_xml", headline=headline, per_item=per_item, sections=sections)

    assert pct(total_ok, n) >= 80, f"XML retrieval succeeded for only {total_ok}/{n}"
    # Europe PMC must carry the bulk of it.
    assert epmc_only_ok >= total_ok * 0.6, "Europe PMC is not the primary provider"
