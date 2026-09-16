# Real PubMed EFetch records

PubMed records as NCBI's EFetch service returns them, fetched verbatim from

    https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=<PMID>&retmode=xml

They back `tests/features/literature/unit/test_pubmed_efetch_records.py`,
which compares what `PubMedClient._parse_efetch_xml()` returns with what each
record says. The hand-written EFetch XML in the other tests put
`<ArticleIdList>` inside `<MedlineCitation>`, where NCBI never puts it, and so
agreed with a parser that could not find a single DOI.

| File | Why it is here |
| --- | --- |
| `PMID39737640.xml` | PMC11687933 (eLife): 22 authors, ORCIDs, several affiliations per author, labelled abstract |
| `PMID38150479.xml` | PMC10775981 (PLOS): DOI in both `<ArticleIdList>` and `<ELocationID>` |
| `PMID39725716.xml` | PMC11671585: 16 authors, 4 with an ORCID |
| `PMID17254312.xml` | PMC1764484 (BMC): DOI only in `<ArticleIdList>`, no `<ELocationID>` |
| `PMID28424752.xml` | PMC5393345: a labelled abstract section with inline `<i>` markup, which cut the section short at its first inline element |
| `PMID33093664.xml` | No PMCID of its own, while 91 cited references carry an `<ArticleIdList>`; one reference's PMCID was returned as the record's |

Every file ends with the newline the repository's `end-of-file-fixer` hook
adds; otherwise keep them as the service returned them.
