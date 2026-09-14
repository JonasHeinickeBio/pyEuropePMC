# Real Europe PMC full text

Open-access JATS documents, fetched verbatim from

    https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML

They back `tests/features/fulltext/real_data/`, which asserts invariants the
parser must hold on documents as Europe PMC actually serves them. Hand-written
fixtures cannot stand in: every defect fixed in #217–#229 was found by
measuring against real files, and several only occur in markup nobody writes
by hand.

| File | Why it is here |
| --- | --- |
| `PMC3258128.xml`  | DTD-based JATS, no XML declaration |
| `PMC3359999.xml`  | `<author-notes>` and `<ack>` back matter |
| `PMC12311175.xml` | Large document (~800 KB), MathML |
| `PMC12738713.xml` | XML declaration, `xml:lang`, modern tagging |
| `PMC12018715.xml` | 23 structured `<mixed-citation>` references — the fields were being filled by regex from flattened text (#226) |
| `PMC13567752.xml` | 9 peer-review `<sub-article>` elements, each with its own `<body>` and `<contrib>` — these were returned as article sections (#222) and article authors (#227) |

Keep them as the service returned them, apart from the trailing newline the
repository's `end-of-file-fixer` hook adds — every file here has one, and it
does not affect parsing. Editing a fixture to make a test pass removes the
reason it is here; fix the parser, or add a fixture that shows the new shape.
