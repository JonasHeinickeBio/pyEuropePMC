# Getting Started with PyEuropePMC

**Level**: ⭐ Beginner
**Examples**: 1 notebook
**Time**: 10-15 minutes

## Overview

This folder contains the essential starting point for using PyEuropePMC. Perfect for first-time users who want to understand the basics quickly.

## 📓 Examples

### 01-basic-usage.ipynb
**Your first PyEuropePMC tutorial**

Learn the fundamentals:
- Setting up the SearchClient
- Performing simple searches
- Understanding result formats
- Accessing article metadata
- Error handling basics

**What you'll build**: A simple script that searches Europe PMC and displays results

**Key concepts**:
- Europe PMC query syntax
- Result pagination
- JSON vs XML formats
- Rate limiting

## 🚀 Quick Start

```python
from pyeuropepmc.search import SearchClient

# Create a client
with SearchClient() as client:
    # Search for papers
    results = client.search("CRISPR gene editing", page_size=5)

    # Display results
    for paper in results['resultList']['result']:
        print(f"{paper['title']} ({paper['pubYear']})")
```

## 🎯 Learning Path

1. **Start here**: `01-basic-usage.ipynb`
2. **Next**: [02-search-client](../02-search-client/) for advanced search features
3. **Then**: [03-article-client](../03-article-client/) for article analysis

## 💡 Tips for Beginners

- Run cells one at a time to see what each does
- Modify the search queries to try your own topics
- Check the output formats to understand the data structure
- Don't worry about rate limits - the defaults are safe

## 📚 What's Next?

After mastering the basics:
- **Search deeper**: [Advanced search patterns](../02-search-client/01-search-basics.ipynb)
- **Download articles**: [FTP downloader](../05-ftp-downloader/01-basic-download.ipynb)
- **Parse full text**: [Fulltext parser](../04-fulltext-parser/01-basic-fulltext.ipynb)

## 🆘 Common Questions

**Q: Do I need an API key?**
A: No! Europe PMC is free and open access.

**Q: How many results can I retrieve?**
A: The API has rate limits, but you can retrieve unlimited results with pagination.

**Q: What formats are supported?**
A: JSON (default), XML, and Dublin Core (DC).

## 🔗 Resources

- [Europe PMC API Documentation](https://europepmc.org/RestfulWebService)
- [Query Syntax Guide](https://europepmc.org/Help#mostofsearch)
- [Main Documentation](../../docs/)
