# PyEuropePMC Examples

Welcome to the PyEuropePMC examples directory! This folder contains organized examples demonstrating all features of the pyEuropePMC library.

## 📁 Directory Structure

### [01-getting-started](./01-getting-started/) - Quick Start Examples
**1 notebook** - Perfect for new users
- Basic usage patterns
- Simple searches and data retrieval
- Core concepts introduction

### [02-search-client](./02-search-client/) - Search & Query Features
**3 examples** - Master literature search
- Basic and advanced search queries
- Logging and debugging features
- Search with caching

### [03-article-client](./03-article-client/) - Article Metadata & Citations
**1 notebook** - Deep dive into articles
- Fast metadata retrieval
- Citation and reference analysis
- Supplementary data access

### [04-fulltext-parser](./04-fulltext-parser/) - Full Text XML Parsing
**4 notebooks + 2 scripts** - Parse and extract from full text
- Basic full text extraction
- Parser configuration and customization
- Modular parsing workflows
- Advanced features (tables, references, metadata)

### [05-ftp-downloader](./05-ftp-downloader/) - Bulk Downloads
**2 notebooks + 1 script** - Download articles at scale
- Basic FTP download workflows
- Clean and organized downloads
- Bulk XML processing

### [06-caching](./06-caching/) - Performance Optimization
**2 scripts** - Speed up your workflows
- Basic caching strategies
- Multi-client caching patterns

### [07-advanced](./07-advanced/) - Advanced Features
**3 examples** - Power user techniques
- Advanced parsing patterns
- Progress callbacks for long operations
- Schema coverage analysis

## 🚀 Getting Started

### For New Users
Start here: [`01-getting-started/01-basic-usage.ipynb`](./01-getting-started/01-basic-usage.ipynb)

### By Use Case

**I want to search for papers:**
→ [`02-search-client/01-search-basics.ipynb`](./02-search-client/01-search-basics.ipynb)

**I want to download full text articles:**
→ [`05-ftp-downloader/01-basic-download.ipynb`](./05-ftp-downloader/01-basic-download.ipynb)

**I want to parse XML and extract data:**
→ [`04-fulltext-parser/01-basic-fulltext.ipynb`](./04-fulltext-parser/01-basic-fulltext.ipynb)

**I want to analyze citations:**
→ [`03-article-client/01-article-basics.ipynb`](./03-article-client/01-article-basics.ipynb)

**I want to optimize performance:**
→ [`06-caching/01-basic-caching.py`](./06-caching/01-basic-caching.py)

## 📊 Example Types

- **📓 Jupyter Notebooks (.ipynb)** - Interactive tutorials with explanations
- **🐍 Python Scripts (.py)** - Standalone runnable examples

## 🎯 Quick Reference

| Feature | Difficulty | Examples | Best For |
|---------|-----------|----------|----------|
| Getting Started | ⭐ Beginner | 1 | First-time users |
| Search Client | ⭐⭐ Intermediate | 3 | Literature search |
| Article Client | ⭐⭐ Intermediate | 1 | Citation analysis |
| Fulltext Parser | ⭐⭐⭐ Advanced | 6 | Data extraction |
| FTP Downloader | ⭐⭐ Intermediate | 3 | Bulk downloads |
| Caching | ⭐⭐ Intermediate | 2 | Performance |
| Advanced | ⭐⭐⭐ Advanced | 3 | Power users |

## 💡 Usage Tips

1. **Start with Jupyter Notebooks** - They include explanations and can be run cell-by-cell
2. **Check README files** - Each subfolder has a detailed README with examples overview
3. **Run in order** - Numbered files (01-, 02-, etc.) build on each other
4. **Modify and experiment** - These examples are templates - adapt them to your needs!

## 📦 Requirements

All examples require:
```bash
pip install pyeuropepmc
```

Some advanced examples may need additional packages (noted in the example files).

## 🔗 Additional Resources

- **Documentation**: [docs/](../docs/)
- **API Reference**: [docs/api/](../docs/api/)
- **Test Files**: [tests/](../tests/)
- **GitHub**: https://github.com/JonasHeinickeBio/pyEuropePMC

## 🆘 Getting Help

If you're stuck:
1. Check the example's docstring/markdown cells for explanations
2. Review the [documentation](../docs/)
3. Look at the [test files](../tests/) for more usage patterns
4. Open an issue on GitHub

## 📝 Contributing Examples

Have a useful example? Contributions welcome!
1. Follow the existing structure
2. Include clear comments and documentation
3. Test your example before submitting
4. Place in the appropriate feature folder

---

**Total Examples**: 19 files (13 notebooks + 6 scripts) organized into 7 feature categories

*Last Updated: October 2025*
