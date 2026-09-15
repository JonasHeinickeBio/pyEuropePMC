# XML element types in a Europe PMC article

This page explains the 93 JATS element types that occur in one Europe PMC full-text article, PMC12311175 (a review article in *Signal Transduction and Targeted Therapy*). It is a glossary for reading JATS XML and the output of the parser's schema tools.

The list comes from `FullTextXMLParser.list_element_types()`, which returns the sorted tag names with namespace URIs removed. The **Recognized** column shows whether `validate_schema_coverage()` counts the tag as recognized: 63 of the 93 are. "Recognized" means the tag name appears in the parser's pattern configuration or in its list of common structural elements. It does not mean the element's content is extracted, nor does "no" mean it is ignored: `article-meta` and `license` are not "recognized", yet `extract_metadata()` and `extract_license()` read them.

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser

parser = FullTextXMLParser(Path("PMC12311175.xml").read_text(encoding="utf-8"))
types = parser.list_element_types()
coverage = parser.validate_schema_coverage()
print(len(types), coverage["recognized_count"], coverage["unrecognized_elements"][:3])
```

Output:

```text
93 63 ['address', 'article-categories', 'article-meta']
```

Other articles use other elements; see [XML parsing](../features/parsing/README.md#inspect-the-document-structure) to list them for your own files.

## Document structure

| Element | Meaning | Recognized |
|---|---|---|
| `article` | Root element of the article | yes |
| `front` | Front matter: journal and article metadata | yes |
| `body` | Main text of the article | yes |
| `back` | Back matter: acknowledgements, notes, references | yes |
| `sec` | Section; sections nest | yes |
| `title` | Title of a section, list, caption or back-matter part | yes |
| `label` | Label of a figure, table, reference or footnote, such as "Fig. 1" | yes |
| `caption` | Caption of a figure or table | yes |
| `p` | Paragraph | yes |
| `ack` | Acknowledgements | yes |
| `notes` | Notes, such as a data availability or competing interests statement | yes |

## Journal metadata

| Element | Meaning | Recognized |
|---|---|---|
| `journal-meta` | Container for journal metadata | no |
| `journal-id` | Journal identifier; the `journal-id-type` attribute names the scheme (for example `nlm-ta`) | no |
| `journal-title-group` | Container for journal titles | no |
| `journal-title` | Full journal title | yes |
| `issn` | ISSN; `pub-type` distinguishes print and electronic | yes |
| `publisher` | Container for publisher information | yes |
| `publisher-name` | Publisher name | yes |
| `publisher-loc` | Publisher location | yes |

## Article metadata

| Element | Meaning | Recognized |
|---|---|---|
| `article-meta` | Container for article metadata | no |
| `article-id` | Article identifier; `pub-id-type` is `pmid`, `pmcid`, `doi` or `publisher-id` | yes |
| `article-categories` | Container for subject categories | no |
| `subj-group` | Group of subjects, for example the article type heading | no |
| `subject` | One subject term | no |
| `title-group` | Container for the article title | no |
| `article-title` | Article title; also the title of a cited work inside a reference | yes |
| `abstract` | Abstract | yes |
| `kwd-group` | Group of keywords | yes |
| `kwd` | One keyword | yes |
| `pub-date` | Publication date; `pub-type` or `date-type` gives its kind | yes |
| `history` | Dates in the editorial history | yes |
| `date` | One history date; `date-type` is `received`, `rev-recd` or `accepted` | yes |
| `day` | Day of a date | yes |
| `month` | Month of a date | yes |
| `year` | Year of a date, or of a cited work | yes |
| `volume` | Journal volume, of the article or of a cited work | yes |
| `fpage` | First page, of the article or of a cited work | yes |
| `lpage` | Last page, of the article or of a cited work | yes |
| `elocation-id` | Electronic article number used instead of page numbers | no |
| `custom-meta-group` | Container for publisher-defined metadata | no |
| `custom-meta` | One publisher-defined metadata item | no |
| `meta-name` | Name of a custom metadata item | no |
| `meta-value` | Value of a custom metadata item | no |

## Contributors and affiliations

| Element | Meaning | Recognized |
|---|---|---|
| `contrib-group` | Group of contributors | yes |
| `contrib` | One contributor; `contrib-type` is usually `author` | yes |
| `contrib-id` | Contributor identifier, usually an ORCID | no |
| `name` | Personal name, of a contributor or of an author in a reference | yes |
| `surname` | Family name | yes |
| `given-names` | Given names or initials | yes |
| `email` | E-mail address | yes |
| `address` | Contact address of a contributor | no |
| `aff` | Affiliation | yes |
| `institution-wrap` | Container for an institution and its identifiers | yes |
| `institution` | Institution name | no |
| `institution-id` | Institution identifier such as a ROR, GRID or ISNI | no |

## Permissions

| Element | Meaning | Recognized |
|---|---|---|
| `permissions` | Container for copyright and licence information | no |
| `copyright-statement` | Copyright statement | yes |
| `copyright-year` | Copyright year | yes |
| `license` | Licence | no |
| `license-p` | Paragraph of licence text | no |
| `license_ref` | Licence URL, from the `ali` (Access and License Indicators) namespace | no |

## Funding

| Element | Meaning | Recognized |
|---|---|---|
| `funding-group` | Container for funding information | yes |
| `award-group` | One grant or award | no |
| `funding-source` | Funder name, often with a funder identifier | no |
| `award-id` | Grant number | no |
| `principal-award-recipient` | Person or organisation that received the award | no |

## Footnotes

| Element | Meaning | Recognized |
|---|---|---|
| `fn-group` | Group of footnotes | no |
| `fn` | One footnote | no |

## Figures and tables

| Element | Meaning | Recognized |
|---|---|---|
| `fig` | Figure | yes |
| `graphic` | Image file reference; the file name is in `xlink:href` | yes |
| `table-wrap` | Table with its label, caption and footnotes | yes |
| `table` | The table itself, in XHTML table markup | yes |
| `thead` | Table header rows | yes |
| `tbody` | Table body rows | yes |
| `tr` | Table row | yes |
| `th` | Header cell | yes |
| `td` | Data cell | yes |

## Inline markup and links

| Element | Meaning | Recognized |
|---|---|---|
| `bold` | Bold text | yes |
| `italic` | Italic text | yes |
| `sup` | Superscript, including citation numbers in some journals | yes |
| `xref` | Cross-reference to a reference, figure, table or affiliation; `ref-type` gives the target kind and `rid` the target ID | yes |
| `ext-link` | Link to an external resource | yes |

## References

| Element | Meaning | Recognized |
|---|---|---|
| `ref-list` | Reference list | yes |
| `ref` | One reference | yes |
| `citation-alternatives` | Container for alternative forms of one citation | no |
| `element-citation` | Citation tagged field by field | yes |
| `mixed-citation` | Citation with tagged fields and punctuation text between them | yes |
| `person-group` | Authors or editors of a cited work | yes |
| `etal` | Marks an author list truncated with "et al." | yes |
| `source` | Journal or book title of a cited work | yes |
| `pub-id` | Identifier of a cited work; `pub-id-type` is `doi`, `pmid` or `pmcid` | yes |

## Processing metadata

| Element | Meaning | Recognized |
|---|---|---|
| `processing-meta` | Information about how the XML was produced, such as the tagset and version | no |
| `restricted-by` | Restriction on the tagset used, inside `processing-meta` | no |

## JATS background

JATS (Journal Article Tag Suite, NISO Z39.96) is the XML standard Europe PMC and PubMed Central use for full-text articles. The same tag can appear in several contexts: `title` names sections, captions and lists; `year`, `volume`, `fpage` and `lpage` occur in the article metadata and in each reference. Elements are optional, and which ones a document uses depends on the journal's tagging practice.
