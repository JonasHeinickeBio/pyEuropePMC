# Citation Networks & Work Cooccurrences - Documentation Index

This directory contains comprehensive advisory documentation for implementing citation network analysis and work cooccurrence features in PyEuropePMC.

## 📚 Documentation Files

### 1. [Full Implementation Advisory](citation-networks-implementation-advisory.md)
**Length**: ~20 pages | **Audience**: Developers, Maintainers

Comprehensive analysis covering:
- Current state analysis of PyEuropePMC codebase
- Detailed feature scope breakdown (citation networks vs work cooccurrences)
- Three implementation options compared (same repo, new repo, fork)
- **Recommendation**: Extend current repository with new `networks` module
- Complete module structure with example code
- 4-phase implementation plan (7-11 weeks total)
- Key considerations: rate limiting, memory management, reproducibility
- Success metrics and next steps

**Start here if**: You need to make the decision about implementation approach or need full context.

---

### 2. [Quick Reference Guide](citation-networks-quick-reference.md)
**Length**: ~7 pages | **Audience**: Quick decision-makers

TL;DR version containing:
- Decision matrix (same repo vs new repo vs fork)
- What's already built vs what's missing
- Proposed API examples
- Implementation timeline (Phases 1-4)
- Critical considerations (rate limiting, memory, reproducibility)
- When to reconsider separate repository

**Start here if**: You need the key decisions and recommendations without deep dive.

---

### 3. [Architecture Diagrams](citation-networks-architecture.md)
**Length**: ~17 pages | **Audience**: Visual learners, Architects

Visual documentation including:
- Current PyEuropePMC architecture (ASCII diagrams)
- Proposed architecture with networks module
- Citation network building flow
- Cooccurrence analysis flow
- Data flow & dependencies
- Memory & performance estimates
- Recommended file structure

**Start here if**: You understand the concepts better through diagrams and visual flow.

---

## 🎯 Quick Navigation

### I want to...

**...understand the recommendation**
→ Read: [Quick Reference Guide](citation-networks-quick-reference.md) - Section "TL;DR"

**...see what the API would look like**
→ Read: [Quick Reference Guide](citation-networks-quick-reference.md) - Section "Quick Example (Proposed API)"

**...understand the implementation phases**
→ Read: [Quick Reference Guide](citation-networks-quick-reference.md) - Section "Implementation Timeline"

**...see the architectural changes**
→ Read: [Architecture Diagrams](citation-networks-architecture.md) - Section "Proposed Architecture"

**...understand why not a separate repo**
→ Read: [Full Advisory](citation-networks-implementation-advisory.md) - Section "Implementation Options"

**...see the complete module structure**
→ Read: [Full Advisory](citation-networks-implementation-advisory.md) - Section "Proposed Module Structure"

**...understand complexity and scope**
→ Read: [Full Advisory](citation-networks-implementation-advisory.md) - Section "Feature Scope Analysis"

---

## 📊 Executive Summary

### The Question
Should citation networks and work cooccurrences be implemented:
1. In the current PyEuropePMC repository?
2. As a separate `pyeuropepmc-networks` package?
3. As a fork of PyEuropePMC?

### The Answer
**Implement in the current repository** as a new `networks` submodule.

### Key Reasoning

| Factor | Why Same Repo |
|--------|---------------|
| **Infrastructure** | Reuse existing ArticleClient, caching, rate limiting |
| **Maintenance** | Single CI/CD pipeline, one test suite |
| **User Experience** | Single package installation, unified documentation |
| **Codebase Size** | Network module ~2,000 LOC vs 10,000 LOC core - manageable |
| **Dependencies** | Make them optional via extras: `pip install pyeuropepmc[networks]` |

### What's Already Built

PyEuropePMC already provides the foundational APIs:
- `ArticleClient.get_citations()` - Get papers citing a given paper
- `ArticleClient.get_references()` - Get papers referenced by a given paper
- `SearchClient.search()` - Query for papers with various filters
- Robust caching, rate limiting, error handling

### What Needs to Be Built

New `networks` module providing:
1. **CitationNetworkBuilder**: Multi-hop citation traversal, network construction
2. **CooccurrenceAnalyzer**: MeSH terms, keywords, author collaboration analysis
3. **NetworkMetrics**: Centrality, clustering, hub identification
4. **Exporters**: GraphML, GML, JSON export for visualization tools

### Implementation Timeline

- **Phase 1** (2-3 weeks): Core citation networks
- **Phase 2** (1-2 weeks): Network metrics
- **Phase 3** (2-3 weeks): Cooccurrence analysis
- **Phase 4** (2-3 weeks): Advanced features
- **Total**: 7-11 weeks

### Critical Success Factors

1. **Caching is essential**: Network traversal = hundreds of API calls
2. **Set resource limits**: max_depth, max_nodes to prevent runaway usage
3. **Comprehensive examples**: Complex features need good documentation
4. **Optional dependencies**: Keep core package lightweight
5. **Performance monitoring**: Document memory usage and API call estimates

---

## 🔄 When to Reconsider

**Consider a separate repository if:**
- Network module grows beyond 5,000 lines of code
- Dependency conflicts emerge (e.g., NetworkX version incompatibilities)
- You want to support non-Europe PMC data sources
- User base clearly segments (API users vs network analysts)
- Development cycles need to be fully independent

**Current assessment**: None of these apply yet. Start in the same repo.

---

## 🚀 Next Steps

1. **Review Documentation** (1 day)
   - Read Quick Reference for overview
   - Review Full Advisory for details
   - Study Architecture Diagrams for structure

2. **Prototype** (1-2 days)
   - Build basic CitationNetworkBuilder with 10-paper test
   - Validate API rate limiting and caching approach

3. **Design** (2-3 days)
   - Write detailed API specification
   - Define test coverage requirements
   - Plan example notebooks

4. **Implement Phase 1** (2-3 weeks)
   - Core citation network functionality
   - Tests with 90%+ coverage
   - Basic example notebook

5. **Gather Feedback** (ongoing)
   - Share with early users
   - Adjust based on real-world usage
   - Iterate on API design

---

## 📖 Related Documentation

### Existing PyEuropePMC Docs
- [Development Guide](README.md) - General development practices
- [API Reference](../api/) - Current API documentation
- [Examples](../../examples/) - Usage examples
- [Article Client Examples](../../examples/03-article-client/) - Current citation/reference retrieval

### External Resources
- [Europe PMC API Documentation](https://europepmc.org/RestfulWebService)
- [NetworkX Documentation](https://networkx.org/)
- [Bibliometrics Standards](https://www.bibliometrix.org/)

---

## ❓ Frequently Asked Questions

### Why not use an existing bibliometrics package?

Existing packages (pybliometrics, scholarly) either:
- Use proprietary data (Scopus, Web of Science)
- Have reliability issues (Google Scholar rate limiting)
- Don't integrate with Europe PMC's open access focus

PyEuropePMC + networks module = best of both worlds.

### Will this make the package too complex?

No, with proper modularization:
- Core users don't need to install network dependencies
- Clear separation between basic API wrapper and advanced analysis
- Network features are opt-in via `pip install pyeuropepmc[networks]`

### What about performance with large networks?

Documentation will clearly state:
- Expected API calls for different network sizes
- Memory requirements (e.g., 1000 nodes ≈ 50-200 MB)
- Build times with/without caching
- Recommended limits (default max_nodes=1000)

### Can I use this for systematic reviews?

Yes! PyEuropePMC already supports systematic review tracking via:
- QueryBuilder with query logging
- PRISMA-compliant search audit trails
- Citation networks can help with forward/backward citation searching

### What if Europe PMC API changes?

PyEuropePMC already handles this well:
- Robust error handling throughout
- Clear error messages for API changes
- Active maintenance and updates
- Networks module will inherit this resilience

---

## 📞 Contact & Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/JonasHeinickeBio/pyEuropePMC/issues)
- **GitHub Discussions**: [Ask questions or share ideas](https://github.com/JonasHeinickeBio/pyEuropePMC/discussions)
- **Email**: jonas.heinicke@helmholtz-hzi.de

---

## 📝 Document Status

- **Created**: 2025-11-11
- **Status**: ✅ Advisory Phase - Decision support documents
- **Next Review**: After prototype implementation
- **Maintainer**: PyEuropePMC Development Team

---

**Remember**: This is advisory documentation to help make informed decisions about implementing citation networks. The actual implementation will follow the standard PyEuropePMC development workflow with proper testing, documentation, and review processes.
