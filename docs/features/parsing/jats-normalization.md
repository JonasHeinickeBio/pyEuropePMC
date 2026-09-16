# JATS normalization

`JATSNormalizer` turns a JATS XML article into clean text for text mining. It removes display markup and figures, tables and boxed text from the body, normalizes entities, whitespace, dashes and identifiers, labels each section with a canonical type such as `methods`, and can emit BioC JSON. It parses the XML itself and does not use `FullTextXMLParser`.

> **Known limitation:** a document that writes `<` or `&` as a numeric character reference, such as `p &#x0003c; 0.05`, makes `normalize_xml()` raise `xml.etree.ElementTree.ParseError`. Europe PMC serves such documents: two of the six test articles in this repository (PMC3258128 and PMC12311175) fail. Parse those with [`FullTextXMLParser`](README.md) instead. See [Known limitations](#known-limitations).

## Normalize a document

```python
from pathlib import Path

from pyeuropepmc.features.fulltext import JATSNormalizer

xml_content = Path("PMC3359999.xml").read_text(encoding="utf-8")

normalizer = JATSNormalizer()
result = normalizer.normalize_xml(xml_content)

print(sorted(result))
print(result["body_text"][:80])
print(result["metadata"]["pmcid"], result["metadata"]["article_type"])
```

Output:

```text
['body_text', 'metadata', 'normalized_root', 'original_root', 'sections']
Introduction
A high prevalence of Taenia solium taeniosis/cysticercosis is repor
PMC3359999 research-article
```

`PMC3359999.xml` is the full-text XML of that article; see [Full-text retrieval](../fulltext/README.md) to download it.

`normalize_xml()` accepts `str` or `bytes`. `normalize_text(xml)` returns only `body_text` and `normalize_sections(xml)` only `sections`; both run the whole pipeline. The module functions `normalize_jats_xml(xml, **flags)` and `normalize_jats_text(xml)` create a normalizer and call it.

## What the result contains

| Key | Type | Description |
|---|---|---|
| `body_text` | `str` | Text of the article's `<body>` after all steps, one text fragment per line. Section titles are included; front and back matter are not |
| `sections` | `list[dict]` | One dict per `<sec>` in the body; `[]` when `section_types=False`. See [Sections](#sections) |
| `metadata` | `dict` | Article metadata; see the next table |
| `normalized_root` | `xml.etree.ElementTree.Element` | The cleaned tree, with namespace URIs removed from all tags |
| `original_root` | `xml.etree.ElementTree.Element` | The same object as `normalized_root`, not a copy of the input |
| `bio_c` | `dict` | BioC JSON; present only with `bio_c_output=True` |

`metadata` holds these keys, each only when the document has the information:

| Key | Type | Source |
|---|---|---|
| `title` | `str` | The first `<article-title>` |
| `doi`, `pmcid`, `pmid` | `str` | `<article-id>` elements anywhere in the document; when a type occurs more than once, the last one wins |
| `article_type` | `str` | The root element's `article-type` attribute, lower-cased |
| `authors` | `list[dict]` | Every `<contrib contrib-type="author">` with a `<name>`, anywhere in the document: `{"name": "Given Surname"}`, plus `"orcid"` when the contributor has an ORCID `<contrib-id>` |
| `journal` | `str` | The first `<journal-title>` |
| `license` | `str` | Text of the first `<license-p>`, or the `license-type` attribute |

With `normalize_identifiers=True` (the default) the DOI is lower-cased and loses a `doi:` or `https://doi.org/` prefix, the PMCID is upper-cased and gets a `PMC` prefix, the PMID keeps only digits, and ORCIDs are written as `0000-0000-0000-0000`.

## Normalization steps

`normalize_xml()` runs these steps in order. The flags are described under [Configuration](#configuration).

| Step | Runs when | What happens |
|---|---|---|
| 1 | always | `bytes` input is decoded as UTF-8 |
| 2 | always | In the raw text, named entities from a built-in table (`&alpha;` becomes `α`, `&nbsp;` a space, `&ndash;` a hyphen) and every numeric character reference (`&#x2013;`, `&#60;`) are replaced by their characters. `&amp;`, `&lt;`, `&gt;`, `&quot;` and `&apos;` are left to the XML parser |
| 3 | always | The text is parsed with defusedxml, and namespace URIs are removed from all tags |
| 4 | `normalize_entities` | Every text node is HTML-unescaped and put into Unicode NFC form |
| 5 | `strip_display_markup` or `flatten_xrefs` | In the body, `bold`, `italic`, `underline`, `strike`, `sc`, `sub`, `sup`, `monospace`, `roman`, `sans-serif`, `styled-content`, `named-content` and `overline` are removed and their text kept; `xref`, `ext-link`, `uri` and `email` are replaced by their text, or by their `rid` or `href` when they have none. Either flag switches on both |
| 6 | `remove_structural` | In the body, `fig`, `fig-group`, `table-wrap`, `table-wrap-foot`, `graphic`, `media`, `supplementary-material`, `supplementary`, `boxed-text`, `disp-formula` and `chem-struct-wrap` are removed together with their text |
| 7 | `drop_mathml` | MathML `math` elements are removed. Their text is kept only when the `math` element has text of its own, which MathML markup rarely has, so formula text is normally lost |
| 8 | `section_types` | `sections` is built from the tree as it is at this point |
| 9 | `normalize_whitespace` | In every text node, 14 Unicode space characters become an ASCII space, 9 zero-width and invisible characters are removed, runs of spaces are collapsed, and the node is stripped |
| 10 | `normalize_dashes` | Eleven Unicode dash, hyphen and minus characters become `-` |
| 11 | always | `metadata` is read from the tree; with `normalize_identifiers` the identifiers are normalized |
| 12 | always | `body_text` is collected from the body |
| 13 | `bio_c_output` | `bio_c` is built from `metadata` and `sections` |

Steps 9 and 10 run after the sections are built, so section titles and text keep no-break spaces, Unicode dashes and doubled spaces; `body_text` and `metadata` do not.

## Configuration

The flags are keyword arguments of `JATSNormalizer(...)` and fields of `NormalizationConfig`, which the normalizer keeps as `normalizer.config`. An unknown keyword raises `TypeError`.

| Flag | Type | Default | When `True` |
|---|---|---|---|
| `normalize_entities` | `bool` | `True` | Step 4 |
| `strip_display_markup` | `bool` | `True` | Step 5 |
| `flatten_xrefs` | `bool` | `True` | Step 5 |
| `remove_structural` | `bool` | `True` | Step 6 |
| `drop_mathml` | `bool` | `True` | Step 7 |
| `section_types` | `bool` | `True` | Step 8; with `False`, `sections` is `[]` |
| `normalize_whitespace` | `bool` | `True` | Step 9 |
| `normalize_dashes` | `bool` | `True` | Step 10 |
| `normalize_identifiers` | `bool` | `True` | Identifier normalization in step 11 |
| `bio_c_output` | `bool` | `False` | Step 13 |

`normalize_jats_xml()` accepts the same keywords except `remove_structural` and `drop_mathml`, which keep their defaults.

```python
from pyeuropepmc.features.fulltext import JATSNormalizer

xml = (
    "<article><body><sec><title>Intro</title>"
    "<p>Before &#x02013; x.</p>"
    "<boxed-text><p>Boxed prose.</p></boxed-text>"
    "<fig><caption><p>Figure caption.</p></caption></fig>"
    "<p>After.</p></sec></body></article>"
)
print(repr(JATSNormalizer().normalize_xml(xml)["body_text"]))
print(repr(JATSNormalizer(remove_structural=False).normalize_xml(xml)["body_text"]))
```

Output:

```text
'Intro\nBefore - x.\nAfter.'
'Intro\nBefore - x.\nBoxed prose.\nFigure caption.\nAfter.'
```

## Sections

Each entry in `sections`:

| Key | Type | Description |
|---|---|---|
| `type` | `str` | `classify_section()` applied to the title |
| `title` | `str` | Section title; `""` for an untitled section |
| `level` | `int` | Nesting depth; `0` for a top-level section |
| `text` | `str` | The section's own `<p>` and `<list>` children, joined by newlines. Subsections are separate entries |
| `passages` | `list[dict]` | The same content as `{"type": "paragraph" or "list", "text": ...}` dicts |

The list is not in document order. Top-level sections run from last to first, and each is followed by its own subsections, also from last to first. This function rebuilds document order from `level`:

```python
from pathlib import Path

from pyeuropepmc.features.fulltext import JATSNormalizer


def document_order(sections):
    """Return JATSNormalizer sections in document order."""
    stack = []
    for section in reversed(sections):
        children = []
        while stack and stack[-1][0] > section["level"]:
            children[:0] = stack.pop()[1]
        stack.append((section["level"], [section, *children]))
    return [s for _, subtree in stack for s in subtree]


sections = JATSNormalizer().normalize_sections(Path("PMC3359999.xml").read_text(encoding="utf-8"))
print([s["title"] for s in sections[:3]])
for section in document_order(sections)[:6]:
    print(section["level"], section["type"], section["title"])
```

Output:

```text
['Discussion', 'Results', 'Risk factors and prevalence of infection']
0 intro Introduction
0 methods Materials and Methods
1 methods Study design and population
1 other Household questionnaire
1 methods Statistical analysis
1 methods Ethical approval
```

The section types here are about content. The structured sections of `FullTextXMLParser.get_full_text_sections_structured()` use a different vocabulary: their `section_type` (`front`, `body`, `back`, `appendix`) says where a section sits. You can apply `classify_section()` to their titles.

## Classify section headings

```python
from pyeuropepmc.features.fulltext import classify_section

for heading in ["Materials and Methods", "2.3 Statistical analysis", "Background",
                "Data Availability", "Ethical Approval", "Preface"]:
    print(heading, "->", classify_section(heading))
```

Output:

```text
Materials and Methods -> methods
2.3 Statistical analysis -> methods
Background -> background
Data Availability -> data_availability
Ethical Approval -> methods
Preface -> other
```

`classify_section(heading)` lower-cases the heading and removes leading numbering such as `1.`, `2.3.1` or `(3)`. It then tries the patterns below in order and returns the type of the first one whose text the heading starts with, or `other`. The heading only has to start with the text, so "Methodological considerations" is `methods`, and because earlier rows win, "Ethical approval" and "Experimental results" are `methods` and "Summary" is `conclusion`.

| Order | Type | The heading starts with |
|---|---|---|
| 1 | `intro` | introduction; general introduction |
| 2 | `methods` | method, methods, methodology; material(s) and method(s); experimental; study design, population, participant(s), sample or data; statistical analysis or method(s); data collection, analysis, extraction or source(s); search strategy or method(s); inclusion and exclusion; eligibility criteria; ethical; protocol; procedure; technique(s); approach; computational |
| 3 | `results` | result(s), including "results and discussion"; finding(s); observation(s); outcome(s); main result(s); statistical result(s); clinical result(s) |
| 4 | `discussion` | discussion; general discussion; interpretation; comment; implication(s); consideration(s); limitation(s) |
| 5 | `conclusion` | conclusion(s); summary; concluding remark(s) or comment(s); final remark(s); closing; wrap up, wrap-up or wrapup |
| 6 | `abstract` | abstract; graphical abstract; structured abstract |
| 7 | `background` | background; context; rationale |
| 8 | `ack` | acknowledgment(s); acknowledgement(s) |
| 9 | `references` | reference(s); bibliography; literature cited; work(s) cited |
| 10 | `supplementary` | supplementary; supplement or supplemental followed by material(s), data, information, file or appendix |
| 11 | `appendix` | appendix; appendices; annex, annexe, annexes |
| 12 | `author_contributions` | author contribution(s); author information; "contributor ship" as two words |
| 13 | `data_availability` | data availability; data access; data sharing; data statement; data resources |
| 14 | `funding` | funding; financial support, disclosure or declaration; grant, grants, granted by |
| 15 | `ethics` | ethics; competing interest(s); conflict(s) of interest; disclosure; declaration(s); consent |
| 16 | `caption` | figure; "fig" followed by a number ("Fig. 1"); table |
| – | `other` | anything else, for example "Case report" or "Materials & Methods" |

## BioC output

```python
from pathlib import Path

from pyeuropepmc.features.fulltext import JATSNormalizer

xml_content = Path("PMC3359999.xml").read_text(encoding="utf-8")
bioc = JATSNormalizer(bio_c_output=True).normalize_xml(xml_content)["bio_c"]

document = bioc["documents"][0]
print(bioc["source"], document["id"], len(document["passages"]))
print(document["passages"][0]["infons"])
```

Output:

```text
pyeuropepmc PMC3359999 8
{'section_type': 'discussion', 'section_title': 'Discussion'}
```

`bio_c` is a BioC collection:

- `source` is `"pyeuropepmc"`; `date` and `key` are `""`.
- `infons` holds `doi`, `pmcid` and `article_type` when the metadata has them.
- `documents` holds one document with `id` (the PMCID, else the DOI, else `"unknown"`), the same `infons`, and `passages`.
- There is one passage per section with non-empty `text`, in the order of `sections`. Each passage has `offset` (running character offset: the previous passage's offset plus its text length plus one), `infons` with `section_type` and `section_title`, `text`, and an empty `annotations` list. The title and abstract are not included.

## Command line

The `pyeuropepmc normalize` commands need Rich, which the `standard` extra installs: `pip install "pyeuropepmc[standard]"`.

```bash
pyeuropepmc normalize text PMC3359999.xml -o PMC3359999.txt
pyeuropepmc normalize sections PMC3359999.xml -o sections.json
pyeuropepmc normalize bioc PMC3359999.xml -o PMC3359999.bioc.json
pyeuropepmc normalize classify "Materials and Methods"
pyeuropepmc normalize batch xml_dir/ out_dir/ --output-format sections
```

| Command | Output | Options |
|---|---|---|
| `text INPUT` | `body_text`, printed, or written to the file given with `-o/--output` | `--no-entities`, `--no-markup`, `--no-sections`, `--no-ids`, `--remove-structural/--no-remove-structural` |
| `sections INPUT` | A table of type, title, depth and word count; with `-o`, also the `sections` list as JSON | `-o/--output`, `--no-entities`, `--no-markup`, `--no-sections` |
| `bioc INPUT` | BioC JSON, printed or written with `-o` | `-o/--output` |
| `classify HEADING` | `HEADING -> type` | none |
| `batch INPUT_DIR OUTPUT_DIR` | One file per `*.xml`: `NAME.txt`, `NAME.sections.json` or `NAME.bioc.json`, then a summary line | `--output-format text\|sections\|bioc` (default `text`), `--recursive/--no-recursive` (default `--no-recursive`), `--no-entities`, `--no-markup`, `--no-sections` |

Differences from the Python defaults:

- `text` defaults to `--no-remove-structural`, so figure captions, tables and boxed text stay in the output. `sections`, `bioc` and `batch` always remove them.
- `--no-markup` sets only `strip_display_markup=False`. Because `flatten_xrefs` stays on, markup is still stripped (step 5), so the option has no effect.

`text`, `sections` and `bioc` print through Rich, which treats square brackets as markup: a `[/i]` in the document stops the command with an error, and bracketed words such as `[a]` disappear from the printed text. Use `-o` to write the output to a file instead.

## Known limitations

- Numeric character references for `<` or `&` (`&#x0003c;`, `&#60;`, `&#x00026;`, `&#38;`) are decoded before parsing, which breaks the XML: `normalize_xml()` and the `normalize` commands raise `xml.etree.ElementTree.ParseError`. Other numeric references, such as `&#x02013;`, are fine.
- Parse errors are not wrapped. Malformed XML raises `xml.etree.ElementTree.ParseError`; a document that declares an entity in its DOCTYPE raises `defusedxml.EntitiesForbidden`, a `ValueError` subclass. Catch both: `except (xml.etree.ElementTree.ParseError, ValueError)`.
- `sections` is not in document order, and its titles and text are not whitespace- or dash-normalized.
- By default boxed text is removed from `body_text`, and MathML formula text is dropped.
- `metadata` searches the whole document, so the DOI and the author list can come from peer-review sub-articles. `FullTextXMLParser.extract_metadata()` reads the article's own front matter.
- `bytes` input is decoded as UTF-8 even when the XML declaration names another encoding.
- The CLI option `--no-markup` has no effect, and `normalize batch` exits with status 0 even when files fail.
