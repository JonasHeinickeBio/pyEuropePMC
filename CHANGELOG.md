# Changelog

All notable changes to PyEuropePMC are documented here.

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
