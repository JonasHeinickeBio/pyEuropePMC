# PyEuropePMC

**PyEuropePMC** is a Python toolkit for automated search, extraction, entity annotation, and knowledge graph (KG) integration of scientific literature from [Europe PMC](https://europepmc.org/).

---

## 🚧 Project Status

**PyEuropePMC is under active development.**  
APIs, features, and documentation may change.  
Contributions, feedback, and suggestions are welcome!

---

## ✨ Features

- **Simple Python API** for querying Europe PMC
- **Flexible output formats:** JSON, XML, DC
- **Entity annotation** for genes, diseases, chemicals, and more
- **Knowledge graph integration** with ready-to-use functions
- **Modular and extensible** design for custom pipelines

---

## 📝 Overview

PyEuropePMC enables you to:

- **Search** Europe PMC for scientific papers programmatically
- **Extract** metadata and full-text content
- **Annotate** entities (e.g., genes, diseases, chemicals) in articles
- **Integrate** extracted data into knowledge graphs or other downstream applications

---

## 🚀 Quick Start

### 1. Installation

```bash
pip install pyeuropepmc
```

Or, to install from source:

```bash
git clone https://github.com/yourusername/pyeuropepmc.git
cd pyeuropepmc
pip install .
```

### 2. Basic Usage

```python
import pyeuropepmc

client = pyeuropepmc.Client()
results = client.search_and_parse("long covid", format="json")
for paper in results:
    print(paper["title"])
```

---

## 📚 Documentation

- [API Reference](docs/API.md) *(coming soon)*
- [Examples](examples/) *(coming soon)*

---

## 🤝 Contributing

Contributions are welcome!  
Please open issues or pull requests for bugs, features, or suggestions.

---

## 📄 License

Distributed under the MIT License.  
See [LICENSE](LICENSE) for details.

---

## 🌐 Links

- [Europe PMC](https://europepmc.org/)
- [PyEuropePMC on PyPI](https://pypi.org/project/pyeuropepmc/)
- [GitHub Repository](https://github.com/yourusername/pyeuropepmc)
