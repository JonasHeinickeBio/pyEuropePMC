"""
Test data generators for benchmarking.

Provides scalable test data generation for benchmarking various operations.
"""

import random
import string
from typing import Any


class TestDataGenerator:
    """Generate scalable test data for benchmarking various operations."""

    # Sample real-world identifiers for realistic benchmarks
    SAMPLE_PMIDS = [
        "25883711",
        "25777971",
        "25666075",
        "25572492",
        "25471057",
        "25380133",
        "25286638",
        "25186639",
        "25086290",
        "24985647",
        "24884996",
        "24784614",
        "24684386",
        "24583864",
        "24483215",
        "24382717",
        "24282243",
        "24181796",
        "24081347",
        "23980812",
    ]

    SAMPLE_DOIS = [
        "10.1093/nar/gkv112",
        "10.1093/nar/gkv113",
        "10.1093/nar/gkv114",
        "10.1093/nar/gkv115",
        "10.1093/nar/gkv116",
        "10.1093/nar/gkv117",
        "10.1093/nar/gkv118",
        "10.1093/nar/gkv119",
        "10.1093/nar/gkv120",
        "10.1093/nar/gkv121",
    ]

    SAMPLE_PMCID = [
        "PMC4590001",
        "PMC4590002",
        "PMC4590003",
        "PMC4590004",
        "PMC4590005",
        "PMC4590006",
        "PMC4590007",
        "PMC4590008",
        "PMC4590009",
        "PMC4590010",
    ]

    SAMPLE_AFFILIATIONS = [
        "Department of Biochemistry, University of Cambridge, Cambridge, UK",
        "Institute of Molecular Biology, University of Mainz, Mainz, Germany",
        "Department of Computer Science, Stanford University, Stanford, CA",
        "National Institutes of Health, Bethesda, MD, USA",
        "Max Planck Institute for Biophysical Chemistry, Göttingen, Germany",
    ]

    SAMPLE_AUTHORS = [
        "Smith J",
        "Johnson M",
        "Williams R",
        "Brown T",
        "Davis L",
        "Miller P",
        "Wilson K",
        "Moore S",
        "Taylor D",
        "Anderson R",
    ]

    SAMPLE_JOURNALS = [
        "Nucleic Acids Research",
        "Nature",
        "Science",
        "Cell",
        "PNAS",
        "Nature Genetics",
        "Genome Biology",
        "EMBO Journal",
        "Molecular Cell",
        "Journal of Biological Chemistry",
    ]

    @classmethod
    def generate_random_string(cls, min_length: int = 10, max_length: int = 100) -> str:
        """Generate a random string."""
        length = random.randint(min_length, max_length)  # nosec B311
        return "".join(random.choices(string.ascii_letters + string.digits + " ", k=length))  # nosec B311

    @classmethod
    def generate_random_pmid(cls) -> str:
        """Generate a random (or sample) PMID."""
        return random.choice(cls.SAMPLE_PMIDS)  # nosec B311

    @classmethod
    def generate_random_doi(cls) -> str:
        """Generate a random (or sample) DOI."""
        return random.choice(cls.SAMPLE_DOIS)  # nosec B311

    @classmethod
    def generate_random_pmcid(cls) -> str:
        """Generate a random (or sample) PMCID."""
        return random.choice(cls.SAMPLE_PMCID)  # nosec B311

    @classmethod
    def generate_author_name(cls) -> str:
        """Generate a random author name."""
        return random.choice(cls.SAMPLE_AUTHORS)  # nosec B311

    @classmethod
    def generate_affiliation(cls) -> str:
        """Generate a random affiliation."""
        return random.choice(cls.SAMPLE_AFFILIATIONS)  # nosec B311

    @classmethod
    def generate_journal_name(cls) -> str:
        """Generate a random journal name."""
        return random.choice(cls.SAMPLE_JOURNALS)  # nosec B311

    @classmethod
    def generate_search_query(cls, complexity: str = "simple") -> str:
        """Generate a search query of specified complexity."""
        if complexity == "simple":
            return random.choice(  # nosec B311
                [
                    "cancer",
                    "cancer treatment",
                    "precision medicine",
                    "genomics",
                    "bioinformatics",
                ]
            )
        elif complexity == "moderate":
            author = cls.generate_author_name().split()[0]
            journal = cls.generate_journal_name().split()[0]
            return f"({author}[Author]) AND ({journal}[Journal])"
        else:  # complex
            author = cls.generate_author_name().split()[0]
            keyword = random.choice(["cancer", "treatment", "therapy", "drug", "target"])  # nosec B311
            year = random.randint(2020, 2025)  # nosec B311
            return (
                f"({author}[Author]) AND ({keyword}[Title/Abstract]) "
                f'AND ({year}[Pub Year]) AND "open access"[Filter]'
            )

    @classmethod
    def generate_test_identifiers(cls, count: int = 10) -> list[str]:
        """Generate a list of test identifiers (PMIDs)."""
        return [str(random.randint(10000000, 99999999)) for _ in range(count)]  # nosec B311

    @classmethod
    def generate_test_papers(cls, count: int = 10) -> list[dict[str, Any]]:
        """Generate test paper metadata for enrichment benchmarks."""
        papers = []
        for _i in range(count):
            paper = {
                "doi": cls.generate_random_doi(),
                "pmid": cls.generate_random_pmid(),
                "title": cls.generate_random_string(50, 150),
                "authors": [cls.generate_author_name() for _ in range(random.randint(1, 5))],  # nosec B311
                "journal": cls.generate_journal_name(),
                "pub_year": random.randint(2015, 2025),  # nosec B311
                "abstract": cls.generate_random_string(200, 500),
                "affiliation": cls.generate_affiliation(),
            }
            papers.append(paper)
        return papers

    @classmethod
    def generate_test_queries(cls, count: int = 10, complexity: str = "simple") -> list[str]:
        """Generate a list of test search queries."""
        return [cls.generate_search_query(complexity) for _ in range(count)]
