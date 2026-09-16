# Real Europe PMC full text: figures and assets

Open-access JATS documents, fetched verbatim from

    https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML

They back the figure and asset tests in `tests/features/fulltext/`, which need
markup that ties a file to the block it belongs to. Both shapes below were
found by comparing the extractors' output against the article as Europe PMC
renders it; neither occurs in any document in `../fulltext_downloads/`.

| File | Why it is here |
| --- | --- |
| `PMC10775981.xml` | Fig 3's caption holds three inline formulas, each an `<alternatives><graphic>`. They precede the figure's own `<graphic>`, so a `.//graphic` search returned a fragment of an equation (`pcbi.1011761.e012.jpg`) as the figure's image. 21 formula images in all, plus three `<supplementary-material>` blocks with `.yaml`, `.m` and `.pdf` files |
| `PMC11687933.xml` | eLife figure supplements: five `<fig>` elements nested inside their parent figure's `<p>`. Their graphics are descendants of the parent too, so they were reported under the parent's label instead of their own, and the parent's image could resolve to a supplement's. Nine `<supplementary-material>` source-data files |

This directory is deliberately separate from `../fulltext_downloads/`, whose
files are parametrised into every test in `tests/features/fulltext/real_data/`.
`PMC11687933.xml` also carries five peer-review `<sub-article>` elements with
affiliations of their own, which `extract_affiliations()` returns alongside the
article's — a limitation listed in `docs/features/parsing/README.md` and not
this directory's subject.

Keep them as the service returned them, apart from the trailing newline the
repository's `end-of-file-fixer` hook adds. Editing a fixture to make a test
pass removes the reason it is here; fix the parser, or add a fixture that shows
the new shape.
