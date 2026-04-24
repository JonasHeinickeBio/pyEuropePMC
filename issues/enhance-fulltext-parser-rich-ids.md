# Enhance FullText Parser and Data Models with Rich Identifier Support

## Context
PMC12311175.xml contains significantly richer structured data and identifiers than currently extracted. Analysis shows critical missing data that should be captured for comprehensive knowledge graph generation.

## Current State
- ✅ Basic metadata: pmcid, doi, title, abstract, authors, affiliations (text only)
- ✅ References with pmid, doi
- ❌ Institution IDs (ROR, GRID, ISNI) in affiliations - **currently dumped as text**
- ❌ Funding information (FundRef, award IDs, recipients)
- ❌ Publisher-id, license info, ISSNs, journal IDs

## Priority Enhancements

### 🔥 HIGH PRIORITY

#### 1. Institution IDs in Affiliations
**Current**: Affiliation text contains "1https://ror.org/00f1zfq44grid.216417.70000 0001 0379 7164Department of..."
**Target**: Extract as structured fields:
```python
{
  "id": "Aff1",
  "text": "Department of Oral and Maxillofacial Surgery...",
  "institution": "Central South University",
  "institution_ids": {
    "ROR": "https://ror.org/00f1zfq44",
    "GRID": "grid.216417.7",
    "ISNI": "0000 0001 0379 7164"
  },
  "city": "Changsha",
  "country": "China"
}
```

**Implementation**:
- Update `extract_affiliations()` in `fulltext_parser.py`
- Add `institution_ids` dict field
- Parse `<institution-id>` elements by type
- Update affiliation data model if needed

#### 2. Funding Information
**Current**: Not extracted
**Target**: Extract structured funding data:
```python
{
  "funding_groups": [
    {
      "source": "National Natural Science Foundation of China",
      "fundref_doi": "https://doi.org/10.13039/501100001809",
      "award_id": "82170974",
      "recipient": "Li, Ning"
    }
  ]
}
```

**Implementation**:
- Add `extract_funding()` method to `fulltext_parser.py`
- Parse `<award-group>` elements
- Extract FundRef DOIs, award IDs, recipients
- Add to paper metadata

#### 3. Article-level publisher-id
**Current**: Only pmcid and doi extracted
**Target**: Extract all article IDs:
```python
{
  "identifiers": {
    "pmcid": "12311175",
    "pmid": "40739089",
    "doi": "10.1038/s41392-025-02280-1",
    "publisher_id": "2280"
  }
}
```

**Implementation**:
- Update `extract_metadata()` to extract all `<article-id>` types
- Add to paper metadata `identifiers` field

### 📊 MEDIUM PRIORITY

#### 4. License Information
```python
{
  "license": {
    "type": "open-access",
    "url": "https://creativecommons.org/licenses/by/4.0/"
  }
}
```

#### 5. Publisher Information
```python
{
  "publisher": {
    "name": "Nature Publishing Group UK",
    "location": "London"
  }
}
```

#### 6. Journal IDs and ISSNs
```python
{
  "journal": {
    "title": "Signal Transduction and Targeted Therapy",
    "nlm_ta": "Signal Transduct Target Ther",
    "iso_abbrev": "Signal Transduct Target Ther",
    "issn_print": "2095-9907",
    "issn_electronic": "2059-3635"
  }
}
```

#### 7. Article Categories/Subjects
```python
{
  "article_type": "review-article",
  "subjects": ["Review Article"],
  "subject_type": "heading"
}
```

### 🔍 LOW PRIORITY

#### 8. Clean ORCID IDs
**Current**: `"orcid": "http://orcid.org/0000-0003-3442-7216"`
**Target**: `"orcid": "0000-0003-3442-7216"` (strip URL prefix)

## Impact on RDF Mapping

With these enhancements, RDF output will include:
- `org:Organization` entities for institutions with ROR/GRID/ISNI URIs
- `frapo:Grant` entities for funding with FundRef DOIs
- `dcterms:license` predicates linking to CC licenses
- Richer provenance via publisher metadata
- Better interoperability with external knowledge bases (ROR, FundRef)

## Implementation Plan

1. **Phase 1** (Current): Institution IDs + Funding + Publisher-ID
2. **Phase 2**: License, Publisher, Journal IDs, ISSNs
3. **Phase 3**: Article categories, clean ORCIDs

## Testing
- Use PMC12311175.xml as primary test case (rich in all ID types)
- Verify backward compatibility with simpler XMLs
- Update `test_converters.py` to validate new fields
- Ensure RDF mapping handles new data structures

## Files to Modify
- `src/pyeuropepmc/processing/fulltext_parser.py` - extraction methods
- `src/pyeuropepmc/models/entities.py` - data models (if needed)
- `src/pyeuropepmc/mappers/processors.py` - entity processing
- `src/pyeuropepmc/mappers/rdf_mapper.py` - RDF generation
- `tests/processing/unit/test_fulltext_parser.py` - unit tests
- `test_converters.py` - integration test validation
