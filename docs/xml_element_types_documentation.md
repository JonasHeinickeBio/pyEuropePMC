# XML Element Types in Europe PMC Full Text Articles
# Generated from PMC12311175.xml using FullTextXMLParser.list_element_types()
# Date: December 3, 2025
# Total unique elements: 93

This document provides explanations for all XML element types found in a typical
Europe PMC full text article in JATS (Journal Article Tag Suite) format.

## Document Structure Elements

### Root and Main Containers
- **article**: Root element containing the entire article
- **front**: Contains article metadata (title, authors, abstract, etc.)
- **body**: Contains the main article content (sections, paragraphs)
- **back**: Contains supplementary material (references, acknowledgments, etc.)

### Metadata Containers
- **article-meta**: Article-level metadata
- **journal-meta**: Journal-level metadata
- **title-group**: Container for article title elements
- **contrib-group**: Container for author/contributor information
- **aff**: Affiliation information
- **institution-wrap**: Institutional affiliation wrapper
- **funding-group**: Funding information
- **custom-meta-group**: Custom metadata fields

## Content Elements

### Text and Formatting
- **p**: Paragraph
- **title**: Section or figure title
- **bold**: Bold text formatting
- **italic**: Italic text formatting
- **sup**: Superscript
- **sub**: Subscript (though not found in this sample)

### Sections and Structure
- **sec**: Section container
- **label**: Label for sections, figures, tables
- **caption**: Caption for figures/tables

### References and Citations
- **ref**: Individual reference entry
- **ref-list**: Container for all references
- **citation-alternatives**: Alternative citation formats
- **element-citation**: Structured citation with XML elements
- **mixed-citation**: Formatted citation text
- **person-group**: Author group in citations
- **etal**: "et al." indicator
- **source**: Journal or source title
- **year**: Publication year
- **volume**: Journal volume
- **fpage**: First page
- **lpage**: Last page
- **elocation-id**: Electronic location identifier

### Figures and Tables
- **fig**: Figure container
- **table-wrap**: Table container
- **table**: HTML table element
- **thead**: Table header
- **tbody**: Table body
- **tr**: Table row
- **th**: Table header cell
- **td**: Table data cell
- **graphic**: Image reference

## Metadata Elements

### Identifiers
- **article-id**: Article identifiers (PMCID, PMID, DOI)
- **pub-id**: Publication identifier within citations
- **contrib-id**: Contributor identifier (ORCID, etc.)
- **institution-id**: Institutional identifier (ROR, etc.)
- **journal-id**: Journal identifier
- **award-id**: Funding award identifier

### Names and Affiliations
- **name**: Person name container
- **surname**: Family name
- **given-names**: Given/first names
- **email**: Email address
- **institution**: Institutional name
- **address**: Physical address

### Publication Information
- **pub-date**: Publication date
- **date**: Generic date element
- **day**: Day of month
- **month**: Month
- **year**: Year
- **volume**: Journal volume
- **issn**: ISSN identifier
- **publisher**: Publisher information
- **publisher-name**: Publisher name
- **publisher-loc**: Publisher location

### Keywords and Categories
- **kwd**: Individual keyword
- **kwd-group**: Keyword group container
- **article-categories**: Article categorization
- **subj-group**: Subject category group
- **subject**: Subject category

## Special Purpose Elements

### Permissions and Licensing
- **permissions**: Copyright and licensing information
- **license**: License details
- **license-p**: License paragraph
- **license_ref**: License reference
- **copyright-statement**: Copyright statement
- **copyright-year**: Copyright year

### Footnotes and Notes
- **fn**: Footnote
- **fn-group**: Footnote group
- **notes**: General notes section
- **ack**: Acknowledgments section

### Cross-references
- **xref**: Cross-reference to figures, tables, sections
- **ext-link**: External link

### Processing and Technical
- **processing-meta**: Processing metadata
- **restricted-by**: Access restrictions
- **history**: Publication history
- **custom-meta**: Custom metadata field
- **meta-name**: Metadata field name
- **meta-value**: Metadata field value

## JATS Schema Context

This XML follows the JATS (Journal Article Tag Suite) standard, which is the
NISO standard for markup of journal articles and other scholarly material.
Europe PMC uses JATS for archiving and distributing full-text articles.

Key characteristics of this document:
- **Namespace-aware**: Uses xlink namespace for links
- **Modular structure**: Clear separation of front matter, body, and back matter
- **Rich metadata**: Extensive bibliographic and administrative metadata
- **Structured citations**: Both structured (element-citation) and formatted (mixed-citation) references
- **Multimedia support**: References to figures, tables, and supplementary materials

## Usage Notes

- Elements may appear in different contexts (e.g., `title` for article title, section title, figure title)
- Some elements are optional and may not appear in all articles
- The presence of certain elements depends on the journal's tagging practices
- Namespace prefixes are stripped in the element type listing but present in the actual XML
