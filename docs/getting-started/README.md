# Getting Started with PyEuropePMC

<div align="center">

**🚀 Welcome to PyEuropePMC!** Get up and running in minutes.

[📦 Installation](installation.md) • [⚡ Quick Start](quickstart.md) • [❓ FAQ](faq.md) • [⬅️ Back to Docs](../README.md)

</div>

---

## 📋 Prerequisites

Before you begin, ensure you have:

- **Python 3.10 or higher** installed
- **pip** or **poetry** for package management
- Basic familiarity with Python programming
- (Optional) A text editor or IDE

## 🚀 Quick Navigation

| Document | Description | Time | Difficulty |
|----------|-------------|------|------------|
| **[📦 Installation](installation.md)** | Install PyEuropePMC and dependencies | 2 min | ⭐ Beginner |
| **[⚡ Quick Start](quickstart.md)** | Your first search and extraction | 5 min | ⭐ Beginner |
| **[❓ FAQ](faq.md)** | Common questions and troubleshooting | 10 min | ⭐ Beginner |

## 📖 Recommended Learning Path

<div class="learning-path">

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

- **[🔍 Search](../features/search/)** - Advanced search capabilities
- **[📄 Full-Text](../features/fulltext/)** - Download PDFs and XML
- **[🔬 Parsing](../features/parsing/)** - Extract structured data from XML

</div>

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

## 📚 Related Sections

| Section | Why Visit? |
|---------|------------|
| **[Features](../features/)** | Learn what PyEuropePMC can do |
| **[API Reference](../api/)** | Complete method documentation |
| **[Examples](../examples/)** | Working code samples |
| **[Advanced](../advanced/)** | Power user features |

---

<div align="center">

**Ready to begin?** [📦 Start with Installation →](installation.md)

**[⬆ Back to Top](#getting-started-with-pyeuropepmc)** • [⬅️ Back to Main Docs](../README.md)

</div>
