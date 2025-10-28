# Installation Guide

## Requirements

- **Python**: 3.10 or higher
- **Operating System**: Windows, macOS, or Linux

## Installation Methods

### From PyPI (Recommended)

```bash
pip install pyeuropepmc
```

### From Source

```bash
git clone https://github.com/JonasHeinickeBio/pyEuropePMC.git
cd pyEuropePMC
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/JonasHeinickeBio/pyEuropePMC.git
cd pyEuropePMC
pip install -e ".[dev]"
pre-commit install
```

## Optional Dependencies

### Future Extensions

When additional modules become available:

```bash
# For fulltext PDF processing
pip install pyeuropepmc[fulltext]

# For ontology integration
pip install pyeuropepmc[ontology]

# Install all optional dependencies
pip install pyeuropepmc[all]
```

## Verification

Test your installation:

```python
import pyeuropepmc
print(pyeuropepmc.__version__)

# Quick test
from pyeuropepmc.search import SearchClient
with SearchClient() as client:
    count = client.get_hit_count("test")
    print(f"API connection successful! Found {count} results for 'test'")
```

## Troubleshooting

### Common Issues

**Import Error**: Make sure you have Python 3.10+ installed

```bash
python --version
```

**Network Issues**: Check your internet connection and firewall settings

- Europe PMC API endpoint: `https://www.ebi.ac.uk/europepmc/webservices/rest/`

**Rate Limiting**: If you encounter rate limit errors, increase the delay:

```python
client = SearchClient(rate_limit_delay=2.0)  # 2 second delay
```

## Next Steps

- [Quick Start Guide](quickstart.md)
- [Basic Usage Examples](basic-usage.md)
- [API Reference](api/search-client.md)
