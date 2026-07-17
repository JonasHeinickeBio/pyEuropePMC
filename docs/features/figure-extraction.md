# Figure Extraction from PMC

Extract figures, images, and tables from PubMed Central Open Access articles.

## Basic Usage

```python
from pyeuropepmc.processing import FigureExtractor

extractor = FigureExtractor()

# Extract figures from a PMC article
figures = extractor.extract_figures("PMC1234567")
for fig in figures:
    print(f"Figure {fig.label}: {fig.caption}")
    print(f"Format: {fig.format}")
    print(f"URL: {fig.image_url}")
```

## FigureInfo Object

Each extracted figure returns a `FigureInfo` object:

```python
from pyeuropepmc.processing import FigureFormat

for fig in figures:
    print(f"Label: {fig.label}")       # "Figure 1", "Table 2"
    print(f"Caption: {fig.caption}")    # Figure caption text
    print(f"Image URL: {fig.image_url}")  # Direct image URL
    print(f"Format: {fig.format}")       # FigureFormat enum
    print(f"Width: {fig.width}x{fig.height}")  # Dimensions
```

## File Formats

The `FigureFormat` enum provides format detection:

- `FigureFormat.IMAGE` — General image
- `FigureFormat.TABLE` — Table
- `FigureFormat.DIAGRAM` — Diagram or chart
- `FigureFormat.OTHER` — Other figure type

## Table Extraction

```python
tables = extractor.extract_tables("PMC1234567")
for table in tables:
    print(f"Table {table.label}: {table.caption}")
```

## Behind the Scenes

The FigureExtractor uses the Europe PMC Annotations API to locate images and their captions within PMC articles. It returns direct image URLs from the PMC image server.

## Requirements

- Works with any PubMed Central Open Access article (PMC ID)
- Some articles may not have accessible figures if not in the OA subset
- No additional API keys required — uses the Europe PMC API
