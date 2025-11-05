"""
Advanced Query Builder Example

This example demonstrates how to use the QueryBuilder class to construct
complex search queries for Europe PMC with a fluent API.
"""

from pyeuropepmc import QueryBuilder, SearchClient


def example_basic_queries():
    """Demonstrate basic query construction."""
    print("=== Basic Query Examples ===\n")

    # Simple keyword search
    qb = QueryBuilder(validate=False)
    query = qb.keyword("cancer").build()
    print(f"1. Simple keyword: {query}")

    # Keyword with field specification
    qb = QueryBuilder(validate=False)
    query = qb.keyword("CRISPR", field="title").build()
    print(f"2. Keyword in title: {query}")

    # Multi-word keyword (automatically quoted)
    qb = QueryBuilder(validate=False)
    query = qb.keyword("gene editing", field="abstract").build()
    print(f"3. Multi-word keyword: {query}\n")


def example_field_specific_searches():
    """Demonstrate field-specific search helpers."""
    print("=== Field-Specific Search Examples ===\n")

    # Author search
    qb = QueryBuilder(validate=False)
    query = qb.author("Smith J").build()
    print(f"1. Author search: {query}")

    # Journal search
    qb = QueryBuilder(validate=False)
    query = qb.journal("Nature").build()
    print(f"2. Journal search: {query}")

    # MeSH term search
    qb = QueryBuilder(validate=False)
    query = qb.mesh_term("Neoplasms").build()
    print(f"3. MeSH term search: {query}\n")


def example_date_filters():
    """Demonstrate date range filtering."""
    print("=== Date Range Filter Examples ===\n")

    # Year range
    qb = QueryBuilder(validate=False)
    query = qb.date_range(start_year=2020, end_year=2023).build()
    print(f"1. Year range: {query}")

    # Open-ended start year
    qb = QueryBuilder(validate=False)
    query = qb.date_range(start_year=2020).build()
    print(f"2. From 2020 onwards: {query}")

    # Specific date range
    qb = QueryBuilder(validate=False)
    query = qb.date_range(start_date="2020-01-01", end_date="2023-12-31").build()
    print(f"3. Specific dates: {query}\n")


def example_boolean_operators():
    """Demonstrate logical operators (AND, OR, NOT)."""
    print("=== Boolean Operator Examples ===\n")

    # AND operator
    qb = QueryBuilder(validate=False)
    query = qb.keyword("cancer").and_().keyword("treatment").build()
    print(f"1. AND operator: {query}")

    # OR operator
    qb = QueryBuilder(validate=False)
    query = qb.keyword("cancer").or_().keyword("tumor").build()
    print(f"2. OR operator: {query}")

    # NOT operator
    qb = QueryBuilder(validate=False)
    query = qb.keyword("cancer").and_().not_().keyword("review").build()
    print(f"3. NOT operator: {query}")

    # Complex boolean query
    qb = QueryBuilder(validate=False)
    query = (
        qb.keyword("cancer")
        .or_()
        .keyword("tumor")
        .and_()
        .keyword("treatment")
        .build()
    )
    print(f"4. Complex boolean: {query}\n")


def example_advanced_filters():
    """Demonstrate advanced filtering options."""
    print("=== Advanced Filter Examples ===\n")

    # Citation count filter
    qb = QueryBuilder(validate=False)
    query = qb.citation_count(min_count=10).build()
    print(f"1. Minimum citations: {query}")

    # Open access filter
    qb = QueryBuilder(validate=False)
    query = qb.open_access(True).build()
    print(f"2. Open access only: {query}")

    # Has PDF filter
    qb = QueryBuilder(validate=False)
    query = qb.has_pdf(True).build()
    print(f"3. Has PDF: {query}")

    # Has full text filter
    qb = QueryBuilder(validate=False)
    query = qb.has_full_text(True).build()
    print(f"4. Has full text: {query}\n")


def example_identifier_searches():
    """Demonstrate searching by identifiers."""
    print("=== Identifier Search Examples ===\n")

    # PMC ID search
    qb = QueryBuilder(validate=False)
    query = qb.pmcid("PMC1234567").build()
    print(f"1. PMC ID: {query}")

    # PubMed ID search
    qb = QueryBuilder(validate=False)
    query = qb.pmid("12345678").build()
    print(f"2. PubMed ID: {query}")

    # DOI search
    qb = QueryBuilder(validate=False)
    query = qb.doi("10.1234/example.2023.001").build()
    print(f"3. DOI: {query}\n")


def example_complex_queries():
    """Demonstrate complex real-world query scenarios."""
    print("=== Complex Real-World Query Examples ===\n")

    # Example 1: Recent cancer research papers with high citations
    qb = QueryBuilder(validate=False)
    query = (
        qb.keyword("cancer", field="title")
        .and_()
        .date_range(start_year=2020)
        .and_()
        .open_access(True)
        .and_()
        .citation_count(min_count=10)
        .build()
    )
    print(f"1. Recent high-impact cancer research:\n   {query}\n")

    # Example 2: CRISPR papers by specific author in Nature
    qb = QueryBuilder(validate=False)
    query = (
        qb.author("Smith J")
        .and_()
        .journal("Nature")
        .and_()
        .keyword("CRISPR", field="title")
        .build()
    )
    print(f"2. CRISPR papers by Smith J in Nature:\n   {query}\n")

    # Example 3: Multiple MeSH terms with filters
    qb = QueryBuilder(validate=False)
    query = (
        qb.mesh_term("Neoplasms")
        .and_()
        .mesh_term("Drug Therapy")
        .and_()
        .date_range(start_year=2018, end_year=2023)
        .and_()
        .has_full_text(True)
        .build()
    )
    print(f"3. Cancer drug therapy with full text (2018-2023):\n   {query}\n")

    # Example 4: Searching by multiple authors (OR logic)
    qb = QueryBuilder(validate=False)
    query = (
        qb.author("Smith J")
        .or_()
        .author("Doe Jane")
        .and_()
        .keyword("genetics")
        .and_()
        .date_range(start_year=2020)
        .build()
    )
    print(f"4. Genetics papers by Smith J or Doe Jane since 2020:\n   {query}\n")


def example_with_grouping():
    """Demonstrate query grouping for complex logic."""
    print("=== Query Grouping Example ===\n")

    # Create a sub-query for disease terms
    disease_terms = QueryBuilder(validate=False).keyword("cancer").or_().keyword("tumor")

    # Use the sub-query in a larger query
    qb = QueryBuilder(validate=False)
    query = (
        qb.group(disease_terms)
        .and_()
        .author("Smith J")
        .and_()
        .date_range(start_year=2020)
        .build()
    )
    print(f"Grouped query:\n   {query}\n")


def example_with_search_client():
    """Demonstrate using QueryBuilder with SearchClient."""
    print("=== Integration with SearchClient ===\n")

    # Build a query
    qb = QueryBuilder(validate=False)
    query = (
        qb.keyword("CRISPR", field="title")
        .and_()
        .date_range(start_year=2020, end_year=2023)
        .and_()
        .open_access(True)
        .build()
    )

    print(f"Query: {query}\n")

    # Note: Uncomment the following to actually execute the search
    # (requires network connection and may take time)
    """
    with SearchClient() as client:
        results = client.search(query, pageSize=10)
        hit_count = results.get("hitCount", 0)
        print(f"Found {hit_count} results")
        
        # Print first few results
        if "resultList" in results and "result" in results["resultList"]:
            for i, paper in enumerate(results["resultList"]["result"][:3], 1):
                print(f"{i}. {paper.get('title', 'N/A')}")
                print(f"   Authors: {paper.get('authorString', 'N/A')}")
                print(f"   Year: {paper.get('pubYear', 'N/A')}\n")
    """


def example_raw_query():
    """Demonstrate using raw query strings."""
    print("=== Raw Query Example ===\n")

    # Use raw query for complex syntax not directly supported
    qb = QueryBuilder(validate=False)
    query = qb.raw("(cancer OR tumor) AND treatment NOT review").build()
    print(f"Raw query: {query}\n")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("PyEuropePMC QueryBuilder Examples")
    print("=" * 70 + "\n")

    example_basic_queries()
    example_field_specific_searches()
    example_date_filters()
    example_boolean_operators()
    example_advanced_filters()
    example_identifier_searches()
    example_complex_queries()
    example_with_grouping()
    example_raw_query()
    example_with_search_client()

    print("=" * 70)
    print("For more information, see the QueryBuilder documentation")
    print("=" * 70)


if __name__ == "__main__":
    main()
