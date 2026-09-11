"""Unit tests for pyeuropepmc.prompts (Jinja2 template rendering)."""

from __future__ import annotations

from pyeuropepmc.prompts import (
    DEFAULT_TEMPLATES,
    PromptTemplates,
    create_default_templates,
    get_templates,
)


class _Author:
    def __init__(self, name):
        self.name = name


class _Paper:
    def __init__(self):
        self.title = "A Great Paper"
        self.authors = [_Author("Smith J"), _Author("Doe A")]
        self.pmid = "12345"
        self.doi = "10.1234/x"
        self.publication_year = 2024
        self.journal = "Journal of Tests"


class TestPromptTemplates:
    def test_init_creates_templates_dir(self, tmp_path):
        templates_dir = tmp_path / "templates"
        pt = PromptTemplates(templates_dir=templates_dir)
        assert templates_dir.exists()
        assert pt.templates_dir == templates_dir

    def test_init_default_dir(self):
        pt = PromptTemplates()
        assert pt.templates_dir.exists()

    def test_render_citation_analysis(self, tmp_path):
        templates_dir = tmp_path / "t"
        create_default_templates(templates_dir)
        pt = PromptTemplates(templates_dir=templates_dir)
        text = pt.render(
            "citation_analysis.md",
            paper=_Paper(),
            context="some context",
            task="analyze it",
        )
        assert "A Great Paper" in text
        assert "Smith J, Doe A" in text
        assert "analyze it" in text

    def test_render_citation_comparison(self, tmp_path):
        templates_dir = tmp_path / "t"
        create_default_templates(templates_dir)
        pt = PromptTemplates(templates_dir=templates_dir)
        text = pt.render(
            "citation_comparison.md", paper1=_Paper(), paper2=_Paper(), task="compare"
        )
        assert "Paper 1" in text and "Paper 2" in text

    def test_render_citation_summary(self, tmp_path):
        templates_dir = tmp_path / "t"
        create_default_templates(templates_dir)
        pt = PromptTemplates(templates_dir=templates_dir)
        text = pt.render("citation_summary.md", paper=_Paper(), citation_count=42)
        assert "42" in text

    def test_get_template_returns_template_object(self, tmp_path):
        templates_dir = tmp_path / "t"
        create_default_templates(templates_dir)
        pt = PromptTemplates(templates_dir=templates_dir)
        template = pt.get_template("citation_summary.md")
        assert template is not None

    def test_custom_filters_registered(self, tmp_path):
        templates_dir = tmp_path / "t"
        create_default_templates(templates_dir)
        pt = PromptTemplates(templates_dir=templates_dir)
        assert pt._truncate("short text") == "short text"
        assert pt._truncate("x" * 300, max_length=10) == "xxxxxxx..."
        assert pt._bold(" text ") == "**text**"
        assert pt._italic(" text ") == "*text*"


def test_get_templates_singleton():
    t1 = get_templates()
    t2 = get_templates()
    assert t1 is t2


def test_create_default_templates_is_idempotent(tmp_path):
    templates_dir = tmp_path / "custom"
    create_default_templates(templates_dir)
    assert (templates_dir / "citation_analysis.md").exists()
    # second call should not error even though files already exist
    create_default_templates(templates_dir)
    assert set(DEFAULT_TEMPLATES) == {p.name for p in templates_dir.iterdir()}


def test_create_default_templates_default_dir():
    # exercises the `templates_dir is None` branch; writes into the package's
    # own prompts/ dir (same side effect the module triggers on import).
    create_default_templates(None)
