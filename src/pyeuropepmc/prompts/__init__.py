"""
Jinja2 prompt templates for citation analysis.

Templates are organized by analysis type and can be rendered with context data.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template


class PromptTemplates:
    """Jinja2 prompt templates for LLM citation analysis."""

    def __init__(self, templates_dir: Path | None = None):
        """
        Initialize prompt templates.

        Parameters
        ----------
        templates_dir : Path, optional
            Directory containing template files. If None, uses built-in templates.
        """
        if templates_dir is None:
            # Use built-in templates from this module's directory
            self.templates_dir = Path(__file__).parent / "prompts"
        else:
            self.templates_dir = templates_dir

        # Create templates directory if it doesn't exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

        # Register custom filters
        self.env.filters["truncate"] = self._truncate
        self.env.filters["bold"] = self._bold
        self.env.filters["italic"] = self._italic

    def _truncate(self, text: str, max_length: int = 200) -> str:
        """Truncate text to max_length with ellipsis."""
        text = text.strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _bold(self, text: str) -> str:
        """Format text as bold markdown."""
        return f"**{text.strip()}**"

    def _italic(self, text: str) -> str:
        """Format text as italic markdown."""
        return f"*{text.strip()}*"

    def get_template(self, name: str) -> Template:
        """
        Get a template by name.

        Parameters
        ----------
        name : str
            Template filename (e.g., "citation_analysis.md")

        Returns
        -------
        Template
            Jinja2 Template object
        """
        return self.env.get_template(name)

    def render(self, name: str, **context) -> str:
        """
        Render a template with context.

        Parameters
        ----------
        name : str
            Template filename
        **context : dict
            Context variables for template rendering

        Returns
        -------
        str
            Rendered template content
        """
        template = self.get_template(name)
        return template.render(**context)


# Global templates instance
_templates = None


def get_templates() -> PromptTemplates:
    """Get or create the global templates instance."""
    global _templates
    if _templates is None:
        _templates = PromptTemplates()
    return _templates


# Default template contents (embedded for offline use)
DEFAULT_TEMPLATES = {
    "citation_analysis.md": """\
# Citation Analysis Request

## Paper Details
- **Title**: {{ paper.title }}
- **Authors**: {% for author in paper.authors %}{{ author.name }}{% if not loop.last %}, {% endif %}{% endfor %}
- **PMID**: {{ paper.pmid }}
- **DOI**: {{ paper.doi }}
- **Year**: {{ paper.publication_year }}
- **Journal**: {{ paper.journal }}

## Citation Context
{{ context }}

## Analysis Task
{{ task }}

## Expected Output Format
- Summary of citations in 2-3 sentences
- Key insights about citation patterns
- Methodology notes
- Limitations or caveats

Please provide a comprehensive analysis of the citation context for this paper.
""",
    "citation_comparison.md": """\
# Citation Comparison Request

## Paper 1
- **Title**: {{ paper1.title }}
- **PMID**: {{ paper1.pmid }}
- **Year**: {{ paper1.publication_year }}

## Paper 2
- **Title**: {{ paper2.title }}
- **PMID**: {{ paper2.pmid }}
- **Year**: {{ paper2.publication_year }}

## Comparison Task
{{ task }}

## Expected Output Format
- Similarities in research focus
- Differences in approach or findings
- Complementary or conflicting results
- Combined implications

Please compare these two papers and their citations.
""",
    "citation_summary.md": """\
# Citation Summary Request

## Paper Details
- **Title**: {{ paper.title }}
- **PMID**: {{ paper.pmid }}
- **Year**: {{ paper.publication_year }}

## Number of Citations
{{ citation_count }}

## Expected Output Format
- Brief summary of citation activity
- Trend indicators (increasing, steady, declining)
- Notable citation patterns

Please provide a concise summary of the citation activity for this paper.
""",
}


def create_default_templates(templates_dir: Path | None = None):
    """
    Create default template files if they don't exist.

    Parameters
    ----------
    templates_dir : Path, optional
        Directory to create templates in. If None, uses default.
    """
    if templates_dir is None:
        templates_dir = Path(__file__).parent / "prompts"

    templates_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in DEFAULT_TEMPLATES.items():
        template_path = templates_dir / filename
        if not template_path.exists():
            template_path.write_text(content, encoding="utf-8")


# Create default templates on module load
create_default_templates()

__all__ = ["PromptTemplates", "get_templates", "DEFAULT_TEMPLATES", "create_default_templates"]
