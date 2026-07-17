"""
CLI commands for enhanced agentic workflows.

This module provides command-line interfaces for:
- Smart citation analysis
- Automated paper screening
- Research question analysis
- Preprint analysis
- Literature review automation
- Knowledge graph building
- Clinical trial integration
"""

import os
import sys

from pyeuropepmc._optional_imports import OptionalDependencyError

try:
    import click
except ImportError:
    raise OptionalDependencyError("click", "agentic CLI", "pip install click") from None

from pyeuropepmc.agentic.agents import SmartCitationAnalysis
from pyeuropepmc.agentic.llm_client import create_llm_client

# Configuration from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
LLM_ENABLED = os.environ.get("LLM_ENABLED", "true").lower() == "true"
LLM_CACHE_ENABLED = os.environ.get("LLM_CACHE_ENABLED", "true").lower() == "true"


def _get_agent(use_llm: bool = False):
    """Get a SmartCitationAnalysis agent."""
    llm_client = None
    if use_llm:
        if not OPENAI_API_KEY:
            click.echo("Error: OPENAI_API_KEY environment variable not set", err=True)
            click.echo("Please set your OpenAI API key to use LLM features.", err=True)
            sys.exit(1)
        llm_client = create_llm_client(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            cache_enabled=LLM_CACHE_ENABLED,
        )
    return SmartCitationAnalysis(llm_client=llm_client)


@click.group()
def agentic():
    """Enhanced agentic workflows for literature research."""
    pass


@agentic.command()
@click.argument("doi")
@click.option("--use-llm/--no-use-llm", default=True, help="Use LLM for analysis")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
def cite_analyze(doi: str, use_llm: bool, output_format: str):
    """Analyze citations for a paper."""
    agent = _get_agent(use_llm=use_llm)

    result = agent.analyze_citation_context(doi=doi)

    if output_format == "json":
        click.echo(result.json(indent=2) if hasattr(result, "json") else result)
    else:
        click.echo(f"Citation Analysis for {doi}:")
        click.echo(f"Context: {result.get('context', 'N/A')}")
        click.echo(f"Classification: {result.get('classification', 'N/A')}")


@agentic.command()
@click.option("--query", "-q", required=True, help="Search query")
@click.option("--include", "-i", multiple=True, help="Inclusion criteria")
@click.option("--exclude", "-x", multiple=True, help="Exclusion criteria")
@click.option("--use-llm/--no-use-llm", default=True, help="Use LLM for analysis")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
def screen_papers(query: str, include: list, exclude: list, use_llm: bool, output_format: str):
    """Screen papers based on inclusion/exclusion criteria."""
    agent = _get_agent(use_llm=use_llm)

    result = agent.screen_papers(
        query=query,
        inclusion_criteria=list(include) if include else None,
        exclusion_criteria=list(exclude) if exclude else None,
    )

    if output_format == "json":
        click.echo(result.json(indent=2) if hasattr(result, "json") else result)
    else:
        click.echo(f"Screened papers for query: {query}")
        click.echo(f"Included: {len(result.get('included_papers', []))}")
        click.echo(f"Excluded: {len(result.get('excluded_papers', []))}")


@agentic.command()
@click.option("--question", "-q", required=True, help="Research question to analyze")
@click.option("--expand/--no-expand", default=False, help="Expand the research question")
@click.option("--use-llm/--no-use-llm", default=True, help="Use LLM for analysis")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
def analyze_question(question: str, expand: bool, use_llm: bool, output_format: str):
    """Analyze and expand a research question."""
    agent = _get_agent(use_llm=use_llm)

    result = agent.analyze_research_question(
        research_question=question,
        expand=expand,
    )

    if output_format == "json":
        click.echo(result.json(indent=2) if hasattr(result, "json") else result)
    else:
        click.echo(f"Research Question Analysis for: {question}")
        if expand and "expanded_questions" in result:
            click.echo("Expanded Questions:")
            for eq in result["expanded_questions"]:
                click.echo(f"  - {eq}")
        click.echo(f"Identified Gaps: {result.get('identified_gaps', [])}")


@agentic.command()
@click.argument("pmcid")
@click.option("--use-llm/--no-use-llm", default=True, help="Use LLM for analysis")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
def analyze_preprint(pmcid: str, use_llm: bool, output_format: str):
    """Analyze a preprint for credibility and bias."""
    agent = _get_agent(use_llm=use_llm)

    result = agent.analyze_preprint(pmcid=pmcid)

    if output_format == "json":
        click.echo(result.json(indent=2) if hasattr(result, "json") else result)
    else:
        click.echo(f"Preprint Analysis for {pmcid}:")
        click.echo(f"Credibility Score: {result.get('credibility_score', 'N/A')}")
        click.echo(f"Bias Indicators: {result.get('bias_indicators', [])}")


@agentic.command()
@click.option("--question", "-q", required=True, help="Literature review question")
@click.option("--prisma-output", "-o", help="Output path for PRISMA flow diagram")
@click.option("--use-llm/--no-use-llm", default=True, help="Use LLM for analysis")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
def literature_review(question: str, prisma_output: str | None, use_llm: bool, output_format: str):
    """Generate a comprehensive literature review."""
    agent = _get_agent(use_llm=use_llm)

    result = agent.generate_literature_review(
        research_question=question,
        prisma_output=prisma_output,
    )

    if output_format == "json":
        click.echo(result.json(indent=2) if hasattr(result, "json") else result)
    else:
        click.echo(f"Literature Review for: {question}")
        click.echo(f"Total Papers: {result.get('total_papers', 0)}")
        click.echo(f"PRISMA Flow: {result.get('prisma_flow', {})}")


@agentic.command()
@click.option("--papers", "-p", multiple=True, help="Paper IDs to analyze")
@click.option("--use-llm/--no-use-llm", default=True, help="Use LLM for analysis")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
def knowledge_graph(papers: list, use_llm: bool, output_format: str):
    """Build a knowledge graph from research literature."""
    agent = _get_agent(use_llm=use_llm)

    result = agent.build_knowledge_graph(
        paper_ids=list(papers) if papers else None,
    )

    if output_format == "json":
        click.echo(result.json(indent=2) if hasattr(result, "json") else result)
    else:
        click.echo("Knowledge Graph:")
        click.echo(f"Entities: {result.get('entities', [])}")
        click.echo(f"Relationships: {result.get('relationships', [])}")


@agentic.command()
@click.option("--query", "-q", help="Search query for trials")
@click.option("--paper-id", "-p", help="Paper ID to link with trials")
@click.option("--use-llm/--no-use-llm", default=True, help="Use LLM for analysis")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json")
def clinical_trials(query: str | None, paper_id: str | None, use_llm: bool, output_format: str):
    """Integrate clinical trial data with research findings."""
    agent = _get_agent(use_llm=use_llm)

    result = agent.integrate_clinical_trials(
        query=query,
        paper_id=paper_id,
    )

    if output_format == "json":
        click.echo(result.json(indent=2) if hasattr(result, "json") else result)
    else:
        click.echo("Clinical Trials Integration:")
        click.echo(f"Trials Found: {len(result.get('trials', []))}")
        click.echo(f"Study Design: {result.get('study_design', {})}")


# Add agentic group to main CLI
# This is done in pyproject.toml [project.scripts]
agentic_commands = [
    cite_analyze,
    screen_papers,
    analyze_question,
    analyze_preprint,
    literature_review,
    knowledge_graph,
    clinical_trials,
]
