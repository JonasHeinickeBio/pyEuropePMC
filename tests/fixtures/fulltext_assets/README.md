# Real Europe PMC full text: figures and assets

An open-access JATS document, fetched verbatim from

    https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML

It backs the figure and asset tests in `tests/features/fulltext/`, which need
markup that ties a file to the block it belongs to. The shape below was found by
comparing the extractors' output against the article as Europe PMC renders it,
and occurs in no document in `../fulltext_downloads/`. The caption-formula case,
`PMC10775981.xml`, is there.

| File | Why it is here |
| --- | --- |
| `PMC11687933.xml` | eLife figure supplements: five `<fig>` elements nested inside their parent figure's `<p>`. Their graphics are descendants of the parent too, so they were reported under the parent's label instead of their own, and the parent's image could resolve to a supplement's. Nine `<supplementary-material>` source-data files |

It is kept apart from `../fulltext_downloads/`, whose files are parametrised
into every test in `tests/features/fulltext/real_data/`: it also carries five
peer-review `<sub-article>` elements with affiliations of their own, which
`extract_affiliations()` returns alongside the article's — a limitation listed in
`docs/features/parsing/README.md` and not this directory's subject.

Keep it as the service returned it, apart from the trailing newline the
repository's `end-of-file-fixer` hook adds. Editing a fixture to make a test
pass removes the reason it is here; fix the parser, or add a fixture that shows
the new shape.
