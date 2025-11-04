# PyEuropePMC Documentation

<div align="center">

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-200%2B%20passed-green.svg)](../tests/)

**Complete documentation for PyEuropePMC** - A robust Python toolkit for scientific literature analysis from Europe PMC

[Quick Start](getting-started/quickstart.md) • [API Reference](api/) • [Examples](examples/) • [GitHub](https://github.com/JonasHeinickeBio/pyEuropePMC)

</div>

---

## 📖 Documentation Overview

This documentation is organized into focused sections to help you find what you need quickly.

### 🚀 [Getting Started](getting-started/)

**New to PyEuropePMC?** Start here!

- **[Installation](getting-started/installation.md)** - Install PyEuropePMC and dependencies
- **[Quick Start](getting-started/quickstart.md)** - Get running in 5 minutes
- **[FAQ](getting-started/faq.md)** - Common questions and troubleshooting

---

### ✨ [Features](features/)

**Explore what PyEuropePMC can do**

#### [🔍 Search](features/search/)
- Search Europe PMC with advanced queries
- Filter, sort, and paginate results
- Multiple output formats (JSON, XML, DC)

#### [📄 Full-Text Retrieval](features/fulltext/)
- Download PDFs, XML, and HTML content
- Bulk FTP downloads for large datasets
- Progress tracking and callbacks

#### [🔬 XML Parsing](features/parsing/)
- Parse full-text XML documents
- Extract metadata, tables, and references
- Convert to plaintext and Markdown
- Schema coverage validation
- Flexible configuration with custom patterns

#### [💾 Caching](features/caching/)
- Smart response caching
- Configurable cache strategies
- Performance optimization

---

### 📚 [API Reference](api/)

**Complete API documentation**

- **[SearchClient](api/search-client.md)** - Search and query the Europe PMC API
- **[FullTextClient](api/fulltext-client.md)** - Download full-text content
- **[ArticleClient](api/article-client.md)** - Article-specific operations
- **[FullTextXMLParser](api/xml-parser.md)** - Parse and extract from XML
- **[FTPDownloader](api/ftp-downloader.md)** - Bulk downloads via FTP
- **[Parser](api/parser.md)** - Response parsing utilities

---

### 🎯 [Examples](examples/)

**Learn by example**

- **[Basic Examples](examples/basic-examples.md)** - Common use cases
- **[Advanced Examples](examples/advanced-examples.md)** - Complex workflows
- **[Use Cases](examples/use-cases.md)** - Real-world applications
- **[Code Snippets](examples/snippets.md)** - Copy-paste solutions

---

### ⚙️ [Advanced](advanced/)

**Power user features**

- **[Configuration](advanced/configuration.md)** - Customize behavior
- **[Error Handling](advanced/error-handling.md)** - Robust error management
- **[Performance](advanced/performance.md)** - Optimization strategies
- **[Custom Patterns](advanced/custom-patterns.md)** - XML parsing configuration

---

### 🛠️ [Development](development/)

**Contributing to PyEuropePMC**

- **[Contributing Guide](development/contributing.md)** - How to contribute
- **[Testing](development/testing.md)** - Testing guidelines
- **[Release Process](development/release-process.md)** - Version management
- **[Architecture](development/architecture.md)** - Project structure

---

## 🎓 Learning Paths

### For Beginners
1. Start with [Installation](getting-started/installation.md)
2. Follow the [Quick Start](getting-started/quickstart.md)
3. Try [Basic Examples](examples/basic-examples.md)
4. Check the [FAQ](getting-started/faq.md) if stuck

### For Advanced Users
1. Explore [Advanced Features](advanced/)
2. Review [API Reference](api/)
3. Study [Advanced Examples](examples/advanced-examples.md)
4. Customize with [Configuration](advanced/configuration.md)

### For Contributors
1. Read [Contributing Guide](development/contributing.md)
2. Understand [Architecture](development/architecture.md)
3. Follow [Testing Guidelines](development/testing.md)
4. Submit PRs following [Release Process](development/release-process.md)

---

## 🔍 Quick Search

| I want to... | Go to... |
|--------------|----------|
| Install the package | [Installation](getting-started/installation.md) |
| Search for papers | [Search Features](features/search/) |
| Download PDFs | [Full-Text Retrieval](features/fulltext/) |
| Parse XML files | [XML Parsing](features/parsing/) |
| Extract metadata | [Metadata Extraction](features/parsing/metadata-extraction.md) |
| Extract tables | [Table Extraction](features/parsing/table-extraction.md) |
| Improve performance | [Performance Guide](advanced/performance.md) |
| Handle errors | [Error Handling](advanced/error-handling.md) |
| See code examples | [Examples](examples/) |
| Contribute code | [Contributing](development/contributing.md) |

---

## 📦 What's New

### Version 1.3.0 (Latest)

**New Features:**
- ✨ **Flexible XML Parsing Configuration** - Customize element extraction with `ElementPatterns`
- ✨ **Schema Coverage Validation** - Analyze XML element recognition
- ✨ **Enhanced Pattern Support** - Cross-references, media, and object IDs
- 🎯 **Improved Coverage** - XML recognition improved from 59.7% to 68.1%

See [CHANGELOG](../CHANGELOG.md) for full version history.

---

## 🆘 Getting Help

### Can't find what you're looking for?

1. **Search this documentation** - Use your browser's search (Ctrl+F / Cmd+F)
2. **Check the [FAQ](getting-started/faq.md)** - Common questions answered
3. **Browse [Examples](examples/)** - See working code
4. **Search [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)** - See if others had the same problem
5. **Ask a Question** - [Create a new issue](https://github.com/JonasHeinickeBio/pyEuropePMC/issues/new)

### Found a Bug?

Report it on [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues) with:
- Python version
- PyEuropePMC version
- Minimal code to reproduce
- Error message and stack trace

---

## 🔗 External Resources

- **[Europe PMC API Documentation](https://europepmc.org/RestfulWebService)** - Official API docs
- **[PyPI Package](https://pypi.org/project/pyeuropepmc/)** - Package on PyPI
- **[GitHub Repository](https://github.com/JonasHeinickeBio/pyEuropePMC)** - Source code
- **[Issue Tracker](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)** - Bug reports and feature requests

---

## 📄 License

PyEuropePMC is licensed under the [MIT License](../LICENSE).

---

<div align="center">

**[⬆ Back to Top](#pyeuropepmc-documentation)**

Made with ❤️ by the PyEuropePMC team

</div>
