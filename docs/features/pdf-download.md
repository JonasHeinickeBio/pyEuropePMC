# Downloading PDFs

This page covers saving the PDF of a paper: with the MCP tool `download_papers_pdf`, which saves up to 20 papers at a time and keeps a record of where each file came from, and with `FullTextClient` in Python. It explains which sources are asked and in what order, what comes back, how licences are reported, what the code does to keep a download safe, and what to do when a paper does not download.

Only open copies are fetched. Nothing here gets past a paywall, a login or a bot check, and a paper that has no open copy comes back as `no_pdf`.

## Save PDFs with the MCP tool

```text
download_papers_pdf(ids=["PMC9102987", "10.48550/arXiv.1706.03762", "PMC3525259"])
```

`ids` takes PMIDs, PMCIDs and DOIs, mixed, 1 to 20 per call. The PDFs are saved on the machine the server runs on, in the folder named by `PYEUROPEPMC_MCP_DOWNLOAD_DIR` (default `~/Downloads/pyeuropepmc`). With a remote HTTP server they are not sent to the caller. The caller cannot choose a path: the file name is built from the PMCID, or from the DOI for a paper outside PubMed Central.

| Variable | Effect |
|---|---|
| `PYEUROPEPMC_MCP_DOWNLOAD_DIR` | Folder the PDFs and `manifest.jsonl` are saved in. `~` is expanded; a blank value means the default. |
| `UNPAYWALL_EMAIL` | Contact address for Unpaywall, which asks for one. Without it the Unpaywall step is skipped; every other source still works. OpenAlex also uses it as its polite-pool address. |

`SEMANTIC_SCHOLAR_API_KEY`, if set, is sent to Semantic Scholar, which otherwise throttles anonymous requests. Set these in the environment of the server process, not in the tool call.

### What comes back

```json
{
  "requested": 3,
  "directory": "/home/you/Downloads/pyeuropepmc",
  "manifest": "/home/you/Downloads/pyeuropepmc/manifest.jsonl",
  "by_status": {"ok": 3},
  "results": [
    {
      "id": "PMC9102987", "id_type": "pmcid", "status": "ok",
      "pmcid": "PMC9102987", "doi": "10.3389/fpsyg.2021.804954", "open_access": true,
      "source": "pmc_open_data",
      "source_url": "https://pmc-oa-opendata.s3.amazonaws.com/PMC9102987.1/PMC9102987.1.pdf",
      "license": "cc-by", "license_source": "pmc_open_data", "md5_verified": true,
      "from_cache": false,
      "path": "/home/you/Downloads/pyeuropepmc/PMC9102987.pdf",
      "size_bytes": 3227366, "sha256": "a0174a12…"
    }
  ]
}
```

Each result has a `status`:

| Status | Meaning |
|---|---|
| `ok` | The PDF was fetched and saved. |
| `exists` | A valid PDF is already saved under that name; nothing was fetched. Pass `overwrite=true` to fetch it again. |
| `no_pdf` | No source had an open PDF that passed the checks. The `error` field says which sources were asked. |
| `not_found` | Europe PMC has no record for that PMID or PMCID. |
| `not_in_pmc` | Europe PMC has the paper but it has neither a PMCID nor a DOI, so there is nothing to ask for. |
| `invalid` | The input is not a PMID, PMCID or DOI. |
| `duplicate` | Another input in the same call names the same paper (`duplicate_of` is its position). It is fetched once. |
| `error` | The lookup failed, the file could not be written, or the download was discarded because it was not a PDF or was over the size limit. |

The fields of an `ok` or `exists` result:

| Field | Meaning |
|---|---|
| `pmcid`, `doi` | What Europe PMC lists for the paper (a DOI input Europe PMC does not know keeps the DOI it was given). |
| `open_access` | Europe PMC's `isOpenAccess` flag; absent when it did not say. |
| `source` | The step or service that supplied the file; see [the sources](#where-a-pdf-comes-from). |
| `source_url` | Where the bytes were fetched from. `null` when the file came from the cache and its origin was not recorded. |
| `license`, `license_source` | The licence and who reported it; see [Licences](#licences). |
| `md5_verified` | `true` when the PMC open-data bucket publishes an MD5 for this PDF and the downloaded file matched it. |
| `from_cache` | `true` when the client's own file cache supplied the file; `source`, `source_url` and `license` are then those recorded when it was first downloaded. |
| `path`, `size_bytes`, `sha256` | The saved file. |
| `manifest_error` | Present only when the manifest line could not be written; the PDF is saved anyway. |

## Where a PDF comes from

A paper in PubMed Central is fetched by its PMCID through the steps below, in this order, and the first that serves a valid PDF wins. A paper outside PubMed Central, or a PMC paper none of these could serve, is then looked for by its DOI.

| Order | `source` | What it asks | Notes |
|---|---|---|---|
| 1 | `europepmc_render` | `europepmc.org/articles/PMC{id}?pdf=render` | Behind a Cloudflare browser check for scripted clients since November 2026. |
| 2 | `europepmc_backend` | `europepmc.org/backend/ptpmcrender.fcgi` | Same. |
| 3 | `pmc_open_data` | NCBI's PMC Open Access Subset on AWS open data, `pmc-oa-opendata.s3.amazonaws.com` | Open-access articles only; the newest version with a PDF. Public, no key. Its metadata file gives the licence and the PDF's MD5. |
| 4 | `europepmc_ftp_zip` | Europe PMC's bulk copy on `ftp.ebi.ac.uk/pub/databases/pmc/pdf/OA/PMCxxxx{n}/PMC{id}.zip` | Open-access articles only. `n` is the PMC ID divided by 10,000, rounded up, in at least three digits. Slow to answer (often 10 s or more). |
| 5 | `unpaywall` | The best open location Unpaywall knows, if it links straight to a PDF | Needs `UNPAYWALL_EMAIL`. |

A paper that Europe PMC lists as not open access skips steps 3 and 4, which only hold open-access articles. After Europe PMC has answered with the browser check, steps 1 and 2 are skipped for ten minutes, so a batch does not knock on a closed door for every paper.

For the DOI route the services are asked in this order, and the first link that serves a PDF wins:

| `source` | What it asks |
|---|---|
| `arxiv` | For a `10.48550/arXiv.*` DOI, `arxiv.org/pdf/{id}`. |
| `unpaywall` | Every location with a direct PDF link, best first. Needs `UNPAYWALL_EMAIL`. After the PMC steps this one is not asked again. |
| `openalex` | `best_oa_location` and `locations` of the work. |
| `semantic_scholar` | `openAccessPdf`. |

A link that only leads to a landing page, such as a repository record page, is not a PDF and is skipped. The Nature paper `10.1038/nature14539` is an example: its open copy is a HAL record page.

## The manifest

Each PDF that is saved adds one line to `manifest.jsonl` in the download folder. The file is JSON Lines, so it can be read with any tool:

```json
{"saved_at":"2026-11-06T16:01:39+00:00","file":"PMC9102987.pdf","pmcid":"PMC9102987","doi":"10.3389/fpsyg.2021.804954","source":"pmc_open_data","url":"https://pmc-oa-opendata.s3.amazonaws.com/PMC9102987.1/PMC9102987.1.pdf","license":"cc-by","license_source":"pmc_open_data","md5_verified":true,"from_cache":false,"sha256":"a0174a12…","size_bytes":3227366,"pyeuropepmc":"4.7.0"}
```

| Field | Meaning |
|---|---|
| `saved_at` | UTC time, to the second. |
| `file` | The file name inside the folder, not a path, so the manifest stays valid when the folder moves. |
| `pmcid`, `doi` | The paper; `null` when not known. |
| `source`, `url` | Which step or service supplied the file and the URL it was fetched from. |
| `license`, `license_source` | The licence and who reported it. |
| `md5_verified`, `from_cache` | As in the result. |
| `sha256`, `size_bytes` | Of the saved file. |
| `pyeuropepmc` | The package version that saved it. |

Rules:

- A line is added for every file the tool saves. Files that already existed (`exists`) and failed downloads add nothing.
- Downloading a file again (`overwrite=true`, or after the file was removed) adds a second line. The last line for a `file` is the current one.
- Lines are appended whole under a lock, so several downloads at once do not interleave.
- If the manifest cannot be written, the result carries `manifest_error` and the PDF stays.
- Only this tool writes the manifest. `FullTextClient` does not.

To list what a folder holds, with the licence of each file:

```python
import json
from pathlib import Path

lines = Path("~/Downloads/pyeuropepmc/manifest.jsonl").expanduser().read_text().splitlines()
latest = {entry["file"]: entry for entry in map(json.loads, lines)}  # the last line wins
for entry in latest.values():
    print(entry["file"], entry["source"], entry["license"])
```

## Licences

The licence recorded is the first of these that has one:

1. The source that supplied the file: the `license_code` in the PMC open-data metadata, the location's `license` in Unpaywall or OpenAlex, or the `license` of Semantic Scholar's `openAccessPdf`.
2. The licence Europe PMC lists for the article (the tool asks Europe PMC for its `core` records to get it); `license_source` is `europepmc`.
3. `null`: nobody said.

`null` does not mean the paper is closed, and a licence is not a statement that you may redistribute the file. Old open-access papers often have no licence recorded anywhere. The licence of a *version* can differ from the article's: the PMC open-data copy of PMC7029158 version 1 says `CC BY-NC-ND`, while version 2, the one downloaded, has no licence code, so Europe PMC's value is used.

The sources spell licences differently; every value is normalized to one lowercase form:

| As reported | Recorded |
|---|---|
| `CC BY-NC-ND` (PMC), `cc by-nc-nd` (Europe PMC), `cc-by-nc-nd` (Unpaywall, OpenAlex), `CCBYNCND` (Semantic Scholar) | `cc-by-nc-nd` |
| `CC BY` | `cc-by` |
| `cc by 4.0` | `cc-by-4.0` |
| `CC0` | `cc0` |
| Anything else, such as `other-oa` or `Elsevier TDM` | Lowercase, spaces become hyphens: `other-oa`, `elsevier-tdm` |

## What keeps a download safe

- **The caller never chooses a path.** The name is `<PMCID>.pdf`, or `<doi>-<hash>.pdf` for a DOI (lowercase; characters other than letters, digits, `.`, `_` and `-` become `_`, and a short hash keeps two DOIs apart). Both are built from an identifier that was validated against a strict pattern, so nothing in a request can write outside the folder.
- **Every file is checked.** It must start with `%PDF`, be at least 1,024 bytes and no more than 100 MB. The size limit is enforced while the file downloads, from the declared size and again from the bytes counted, so a source that sends more is abandoned. A file that fails is removed.
- **Links from third-party records are not trusted.** For the DOI route, a link is fetched only if it is `http` or `https`, has no credentials in it, and every address its host resolves to is public. Loopback, private and link-local ranges, which include cloud metadata services, are refused. Redirects are followed by hand, at most five, and each target is checked the same way. The address can change between the check and the connection, so this narrows the risk rather than removing it.
- **A failed download never costs you the file you have.** A download is staged in a temporary file, checked there (PDF header, size, and for the PMC bucket the published MD5) and moved onto the target in one step only if it passes. With `overwrite=true`, a source that sends rubbish leaves the existing PDF as it was.
- **Two downloads of the same file do not collide.** Calls for the same file wait for each other; different files download in parallel, two at a time.
- **No bot protection is bypassed.** When Europe PMC answers with its browser check, the tool does not try to pass it and does not change how it identifies itself. It uses the sources that serve the same open-access files without a check.
- **Files are readable by you only.** They are written through a temporary file with mode 600, which is kept.

## Use it from Python

`FullTextClient` has three methods. Give the client a contact address to enable Unpaywall.

```python
from pyeuropepmc import FullTextClient

with FullTextClient(enable_cache=False, email="you@example.org") as client:
    result = client.download_pdf_with_provenance("PMC9102987", "papers/PMC9102987.pdf")
    print(result)
```

```text
PdfResult(path=PosixPath('papers/PMC9102987.pdf'), source='pmc_open_data', url='https://pmc-oa-opendata.s3.amazonaws.com/PMC9102987.1/PMC9102987.1.pdf', license='cc-by', md5_verified=True, from_cache=False)
```

`download_pdf_with_provenance()` returns a `PdfResult`, or `None` when no step succeeded. `download_pdf_by_pmcid()` takes the same arguments and returns just the `Path` (or `None`). For a paper outside PubMed Central:

```python
    result = client.download_pdf_by_doi("10.48550/arXiv.1706.03762", "papers/attention.pdf")
    print(result.source, result.url, result.license)
```

```text
arxiv https://arxiv.org/pdf/1706.03762 None
```

The useful arguments:

| Argument | Effect |
|---|---|
| `max_bytes` | Refuse a PDF over this size, from its declared size or while it downloads, in every step. `None` means no limit. |
| `doi` | The paper's DOI for the Unpaywall step, which saves a lookup. |
| `open_access` | Pass `False` when Europe PMC says the article is not open access to skip the two open-access-only copies. |
| `skip` (`download_pdf_by_doi`) | Source names not to ask, for example `("unpaywall",)`. |

With the file cache on (the default), the origin of each cached PDF is stored beside the cache, in `pdf-provenance/PMC{id}.json`, together with the file's SHA-256. A later cache hit reports the original `source`, `url` and `license` with `from_cache=True`; if that record is missing or belongs to a different file, `source` is just `cache`. See the [FullTextClient reference](../api/fulltext-client.md) for the signatures.

## How many papers have a PDF

On 6 November 2026, from one machine, 100 papers sampled across the years 2000 to 2025 were checked against the sources that work without getting past a browser check:

| | Papers with a PDF |
|---|---|
| NCBI PMC open data | 93 |
| Europe PMC bulk copy on `ftp.ebi.ac.uk` | 93 (the same 93) |
| Unpaywall, with a direct PDF link | 76 (10 of the 100 had no DOI) |
| Any of them | 95 |

All 93 papers that Europe PMC lists as open access had a PDF in both the bucket and the bulk copy. Of the 7 that it lists as not open access, 2 had one, both through Unpaywall. Downloading 15 of them through the whole chain gave the same result: the 8 open-access papers in 1 to 4 seconds, 2 of the 7 others in 12 to 18 seconds (measured before closed papers skipped the two open-access-only copies), and 5 with no PDF. The 5 with no PDF anywhere have no DOI at all.

Treat these as a rough guide. Europe PMC returns search results by relevance, not at random, so the sample was 93% open access, more than PMC as a whole. Expect fewer PDFs for recent closed-access papers.

## When a paper does not download

| What you see | Why, and what to do |
|---|---|
| `no_pdf` for a recent paper from a subscription journal | There is no open copy. Nothing is bypassed; ask the publisher or your library. |
| `no_pdf` for a paper that is open access | Set `UNPAYWALL_EMAIL`. If the only open copy is a repository page rather than a PDF, as with some HAL records, it is skipped. |
| `not_in_pmc` | Europe PMC has the paper without a PMCID or a DOI. Look the DOI up yourself and pass that. |
| Log line "is showing a browser check to scripted clients" | `europepmc.org` is not serving its PDF pages to scripts. The tool uses the other sources, and tries `europepmc.org` again after ten minutes. Only Europe PMC can lift the check. |
| Downloads take 10 s or longer | The bulk copy on `ftp.ebi.ac.uk` is slow to answer, and a paper that is not in it costs that wait. A paper Europe PMC lists as not open access skips it. |
| Requests to one host take 40 s or more to fail | An address of that host does not answer (IPv6 to some Cloudflare hosts did not on one test machine) and each address is tried in turn. On the DOI route connect timeouts are 5 to 8 seconds, so this costs a few seconds per address. Fix the route, or disable IPv6 for the process. |
| `manifest_error` | The folder is not writable for the manifest, or `manifest.jsonl` is a directory. The PDF is saved. |
| `error` with "Discarded the download" | The source sent something that is not a PDF, or one over 100 MB. |

## Known limits

- **`FTPDownloader` and the XML archive step need `europepmc.org/ftp/`, which is behind the same browser check.** `FTPDownloader` lists and downloads from `https://europepmc.org/ftp/pdf/`, and `download_xml_by_pmcid()` tries `https://europepmc.org/ftp/oa/` among its steps. Both returned HTTP 403 with a challenge on 6 November 2026. `download_xml_by_pmcid()` falls through to the REST API, which works; `FTPDownloader` has no fallback yet. The same folders exist on `ftp.ebi.ac.uk/pub/databases/pmc/pdf/OA/`.
- The tool reads no text out of the PDFs and does not check that the file is the paper that was asked for.
- Without `SEMANTIC_SCHOLAR_API_KEY`, Semantic Scholar may refuse with HTTP 429; that source then gives no link.
- At most two files are fetched at a time, which keeps the load on each source low. A call with 20 papers is not instant.
