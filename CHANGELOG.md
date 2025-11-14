# Changelog

All notable changes to PyEuropePMC are documented here.


## [1.11.0] - 2025-11-14

### ✨ Features

- **Advanced Analytics and Visualization**: Comprehensive analytics suite with publication metrics, citation analysis, and interactive dashboards
  - Author statistics and geographic analysis
  - Journal distribution and publication type analysis
  - Quality metrics and duplicate detection
  - Interactive visualization plots for trends and distributions

- **HTTP Caching System**: Robust caching with requests-cache and conditional GET support
  - Configurable cache backends (memory, disk, Redis)
  - Cache invalidation and TTL management
  - Conditional requests to minimize API calls

- **Content-Addressed Artifact Storage**: SHA-256 based storage with deduplication
  - Efficient storage of large documents and metadata
  - Automatic deduplication to save disk space
  - Metadata tracking and artifact management

- **Full Text XML Parser**: Advanced parsing for Europe PMC full-text XML documents
  - Metadata extraction and table parsing
  - Multiple output formats (JSON, Markdown, plain text)
  - Configurable parsing schemas and element patterns

- **Advanced Filtering Utilities**: Enhanced post-query result filtering
  - `filter_pmc_papers`: AND logic for precise filtering
  - `filter_pmc_papers_or`: OR logic for broad exploratory searches
  - Support for MeSH terms, keywords, and abstract matching

- **Full-Text Content Retrieval**: Comprehensive client for retrieving full-text articles
  - Support for multiple formats (XML, PDF, plain text)
  - Progress tracking and error handling
  - Batch processing capabilities

### 🔧 Maintenance

- **Major Codebase Restructuring**: Complete architectural overhaul for better maintainability
  - Modular design with clear separation of concerns
  - Enhanced error handling and type safety
  - Comprehensive test coverage improvements

- **CI/CD Pipeline Enhancements**: Automated testing and quality assurance
  - Pre-commit hooks for code quality
  - Automated dependency updates
  - Coverage reporting and benchmarking


## [1.10.1] - 2025-11-10

### Fixed

- **CodeScene Integration**: Added missing `run_delta_analysis` function to CodeScene analysis script

## [1.10.0] - 2025-11-10

### ✨ Features

- **Enhanced CodeScene Integration**: Secure environment management for code health analysis
  - Improved CodeScene CLI integration with proper environment setup
  - Enhanced code quality monitoring and analysis capabilities

## [1.9.1] - 2025-11-10

### 🔧 Maintenance

- **Dependency Updates**: Updated multiple development and runtime dependencies
  - Updated `requests` to 2.32.5 for security improvements
  - Updated `notebook` to 7.4.7 for compatibility
  - Updated `attrs` to 25.4.0 and `jupyterlab-widgets` to 3.0.16
  - Updated CI actions: `actions/checkout` to v5, `actions/upload-artifact` to v5, `actions/labeler` to v6, `codecov/codecov-action` to v5, `actions/ai-inference` to v2

## [1.9.0] - 2025-11-10

### ✨ Features

- **CodeScene CLI Integration**: Automated code health analysis and quality monitoring
  - Integrated CodeScene CLI for comprehensive code analysis
  - Enhanced CI workflows with code health tracking

### 🔧 Maintenance

- **Query Builder Refactoring**: Improved error handling and removed unnecessary flags
  - Enhanced QueryBuilder with better validation and error handling
  - Removed SEARCH_QUERY_AVAILABLE flag for cleaner implementation
  - Added comprehensive unit tests for QueryBuilder functionality

- **CI Workflow Improvements**: Enhanced testing and issue tracking automation
  - Updated CI workflows for better test coverage and issue management
  - Improved automated dependency management

### Fixed

- Code review fixes: documentation improvements, unused import removal, and exception handling enhancements

## [1.8.1] - 2025-11-06

### Added

- **Advanced Query Builder**: Complete fluent API for building complex Europe PMC search queries
  - Type-safe field specifications with 150+ searchable fields
  - Fluent method chaining for complex boolean logic (AND/OR/NOT)
  - Optional query validation using CoLRev search-query package
  - Load/save queries in standard JSON format
  - Cross-platform query translation (PubMed, Web of Science, etc.)
  - Query evaluation with recall/precision metrics

- **Systematic Review Tracking**: PRISMA/Cochrane-compliant search logging
  - `log_to_search()` method for tracking queries in systematic reviews
  - Integration with search logging utilities for audit trails
  - Raw results saving for reproducibility
  - PRISMA flow diagram data generation
  - Complete systematic review workflow support

- **Field Coverage Validation**: API field synchronization tools
  - `validate_field_coverage()` function to check API vs code field coverage
  - `get_available_fields()` for fetching current API fields
  - Automated field metadata validation

### Improved

- Enhanced type safety with comprehensive Literal types for all search fields
- Better error handling with specific error codes and context
- Improved documentation with extensive examples and API reference
- Graceful fallback when optional dependencies are missing

## [1.8.0] - 2025-10-15

### Added

- AI-powered Feature Suggester GitHub Action for automated feature suggestions

## [1.7.0] - 2025-09-20

### Added

- **Full Text XML Parser**: Comprehensive XML parsing with metadata extraction
  - Support for table and figure extraction from full-text XML
  - Multiple output format conversions
  - Enhanced metadata parsing capabilities

## [1.6.0] - 2025-08-25

### Added

- **Advanced Filtering Utilities**: Powerful post-query result filtering
  - `filter_pmc_papers()`: AND logic filtering with MeSH, keywords, and abstract matching
  - `filter_pmc_papers_or()`: OR logic filtering for broader result sets
  - Case-insensitive and partial matching support

## [1.5.0] - 2025-08-10

### Added

- **Optional Disk Cache Integration**: Performance optimization with safe fallbacks
  - Disk-based caching using diskcache library
  - Backward compatibility when diskcache is not installed
  - Type-safe implementation with proper error handling

## [1.4.0] - 2025-07-28

### Added

- **Comprehensive Test Suite**: Expanded testing coverage
  - Additional unit tests for all functionality
  - Improved test organization and coverage reporting

### Improved

- Enhanced documentation with detailed usage examples
- Better code organization and maintainability

## [1.3.0] - 2025-07-22

### Added

- **Full-Text Content Retrieval**: Complete full-text access implementation
  - `FullTextClient` for downloading PDF, XML, and HTML content
  - Multiple fallback endpoints for robust retrieval
  - Intelligent content availability checking
  - Atomic download operations with proper error handling

## [1.2.0] - 2025-07-16

### Added

- **Full-Text Content Retrieval**: Complete implementation of full-text content access
  - `FullTextClient` class for downloading PDF, XML, and HTML content
  - Support for multiple fallback endpoints for robust content retrieval
  - Intelligent content availability checking
  - Atomic download operations with proper error handling

- **Bulk FTP Downloads**: Efficient bulk PDF downloads from Europe PMC FTP servers
  - `FTPDownloader` class for querying and downloading from FTP archives
  - Smart directory searching algorithm for optimal PMC ID location
  - Bulk download and extraction capabilities
  - ZIP file handling with automatic PDF extraction

- **Enhanced Test Coverage**: Comprehensive test suite with 200+ tests
  - Unit tests for all new functionality
  - Functional tests with realistic server responses
  - Edge case coverage and error handling validation

### Improved

- Enhanced error handling with specific error codes for full-text operations
- Updated documentation with full-text API reference
- Improved type annotations throughout the codebase
- Better rate limiting and respectful API usage

## [1.1.0] - 2025-06-25

### Added

- **Enhanced BaseAPIClient**: Improved session management and context support
- **Advanced Search Parameter Validation**: Better input validation and error handling
- **Unit Tests**: Comprehensive test coverage for search functionality
- **Copilot Instructions**: Coding standards and development guidelines

### Improved

- Enhanced EuropePMCParser error handling
- Better CI/CD pipeline with coverage reporting
- Improved documentation and usage examples

## [1.0.2] - 2025-06-15

### Fixed

- Minor bug fixes and improvements
- CI/CD pipeline refinements

## [1.0.1] - 2025-06-12

### Fixed

- Python setup and dependency configuration fixes
- Semantic release configuration updates

## [1.0.0] - 2025-06-10

### Initial Release

- Initial release with core search functionality
- Support for JSON, XML, and Dublin Core formats
- Comprehensive test suite (200+ tests)
- Complete documentation and examples
- Production-ready error handling and rate limiting

### Core Features

- Europe PMC search API integration
- Smart pagination for large result sets
- Context managers for resource management
- Type hints throughout codebase
- Built-in retry logic and connection handling

For detailed release information, see [docs/development/release-analysis.md](docs/development/release-analysis.md)
