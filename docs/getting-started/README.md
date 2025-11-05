# Getting Started with PyEuropePMC

Welcome! This section will help you get up and running with PyEuropePMC quickly.

## 📋 Prerequisites

Before you begin, ensure you have:

- **Python 3.10 or higher** installed
- **pip** or **poetry** for package management
- Basic familiarity with Python programming
- (Optional) A text editor or IDE

## 🚀 Quick Navigation

| Document | Description | Time |
|----------|-------------|------|
| **[Installation](installation.md)** | Install PyEuropePMC and dependencies | 2 min |
| **[Quick Start](quickstart.md)** | Your first search and extraction | 5 min |
| **[FAQ](faq.md)** | Common questions and troubleshooting | 10 min |

## 📖 Recommended Learning Path

### Step 1: Installation (2 minutes)
Start with the [Installation Guide](installation.md) to get PyEuropePMC installed on your system.

```bash
pip install pyeuropepmc
```

### Step 2: Quick Start (5 minutes)
Follow the [Quick Start Guide](quickstart.md) to run your first search:

```python
from pyeuropepmc import SearchClient

with SearchClient() as client:
    results = client.search("CRISPR", pageSize=10)
    print(f"Found {results['hitCount']} papers")
```

### Step 3: Explore Features
Once you've completed the quick start, explore specific features:

- **[Search](../features/search/)** - Advanced search capabilities
- **[Full-Text](../features/fulltext/)** - Download PDFs and XML
- **[Parsing](../features/parsing/)** - Extract structured data from XML

## 🎯 What You'll Learn

After completing this section, you'll be able to:

- ✅ Install and configure PyEuropePMC
- ✅ Perform basic searches
- ✅ Download full-text content
- ✅ Parse XML documents
- ✅ Extract metadata and tables
- ✅ Handle common errors

## 💡 Next Steps

Once you're comfortable with the basics:

1. **Dive deeper** into [Features](../features/) to see what's possible
2. **Study the [API Reference](../api/)** for complete documentation
3. **Explore [Examples](../examples/)** for real-world use cases
4. **Learn [Advanced](../advanced/)** techniques for power users

## 🆘 Need Help?

- Check the [FAQ](faq.md) for common questions
- See [Examples](../examples/) for working code
- Visit [GitHub Issues](https://github.com/JonasHeinickeBio/pyEuropePMC/issues) for support

---

**Ready to begin?** Start with [Installation →](installation.md)
