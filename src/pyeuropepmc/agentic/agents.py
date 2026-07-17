"""
Agent base classes and implementations for literature analysis.

This module provides:
- BaseAgent abstract base class
- SmartCitationAnalysis agent for comprehensive citation analysis
"""

from abc import ABC, abstractmethod
import logging
from typing import Any

from pyeuropepmc.agentic.llm_client import LLMClient, create_llm_client
from pyeuropepmc.features.search.base import BaseLiteratureClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for agentic workflows.

    Defines the interface for all agents:
    - Initialize with LLM client and literature client
    - Execute analysis with typed input/output
    - Provide progress tracking and logging

    Attributes
    ----------
    llm_client : LLMClient
        LLM client for generating responses
    literature_client : BaseLiteratureClient
        Literature client for fetching papers
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        literature_client: BaseLiteratureClient | None = None,
        llm_enabled: bool = True,
    ):
        """
        Initialize base agent.

        Parameters
        ----------
        llm_client : LLMClient, optional
            LLM client instance. If None, creates new one.
        literature_client : BaseLiteratureClient, optional
            Literature client instance. If None, creates new one.
        llm_enabled : bool, optional
            Whether LLM is enabled (default: True)
        """
        self.llm_client = llm_client or create_llm_client(enabled=llm_enabled)
        self.literature_client = literature_client
        self._progress_callbacks = []

    @abstractmethod
    def execute(self, **kwargs) -> dict[str, Any]:
        """
        Execute the agent's main analysis.

        Parameters
        ----------
        **kwargs : dict
            Agent-specific parameters

        Returns
        -------
        dict
            Analysis results
        """
        pass

    def register_progress_callback(self, callback):
        """
        Register a progress callback.

        Parameters
        ----------
        callback : callable
            Function signature: callback(progress: float, message: str)
        """
        self._progress_callbacks.append(callback)

    def _notify_progress(self, progress: float, message: str):
        """
        Notify progress callbacks.

        Parameters
        ----------
        progress : float
            Progress value (0.0 to 1.0)
        message : str
            Progress message
        """
        for callback in self._progress_callbacks:
            try:
                callback(progress, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")


class SmartCitationAnalysis(BaseAgent):
    """
    Agent for comprehensive citation analysis.

    Provides:
    - Citation summary generation
    - Citation pattern analysis
    - Citation comparison between papers
    - Methodology notes and limitations

    Attributes
    ----------
    llm_client : LLMClient
        LLM client for generating analyses
    literature_client : BaseLiteratureClient
        Literature client for fetching paper data
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        literature_client: BaseLiteratureClient | None = None,
        llm_enabled: bool = True,
    ):
        """
        Initialize smart citation analysis agent.

        Parameters
        ----------
        llm_client : LLMClient, optional
            LLM client instance. If None, creates new one.
        literature_client : BaseLiteratureClient, optional
            Literature client instance. If None, creates new one.
        llm_enabled : bool, optional
            Whether LLM is enabled (default: True)
        """
        super().__init__(llm_client, literature_client, llm_enabled)
        self._analysis_cache: dict[str, Any] = {}

    def analyze_citation_context(
        self,
        paper: dict[str, Any],
        context: str = "general",
        task: str = "Provide a comprehensive analysis of the citation context for this paper.",
    ) -> dict[str, Any] | None:
        """
        Analyze citation context for a paper.

        Parameters
        ----------
        paper : dict
            Paper data with pmid, title, authors, etc.
        context : str, optional
            Citation context description (default: "general")
        task : str, optional
            Analysis task description (default: general analysis)

        Returns
        -------
        dict or None
            Analysis results with summary, insights, methodology
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        # Check cache
        cache_key = f"citation_analysis:{paper.get('pmid', '')}:{context}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        # Notify progress
        self._notify_progress(0.2, "Generating citation analysis...")

        try:
            # Generate analysis
            prompt_context = {
                "paper": paper,
                "context": context,
                "task": task,
            }

            result = self.llm_client.generate_with_template(
                "citation_analysis.md", **prompt_context
            )

            if not result:
                return None

            # Parse and structure result
            analysis = {
                "paper_id": paper.get("pmid", "unknown"),
                "title": paper.get("title", "Unknown"),
                "summary": result,
                "insights": self._extract_insights(result),
                "methodology": self._extract_methodology(),
                "limitations": self._extract_limitations(),
                "timestamp": None,  # Could add timestamp if needed
            }

            # Cache result
            self._analysis_cache[cache_key] = analysis

            # Notify progress
            self._notify_progress(1.0, "Citation analysis complete")

            return analysis

        except Exception as e:
            logger.error(f"Citation analysis error: {e}")
            return None

    def compare_citations(
        self,
        paper1: dict[str, Any],
        paper2: dict[str, Any],
        task: str = "Compare these two papers and their citations.",
    ) -> dict[str, Any] | None:
        """
        Compare citations between two papers.

        Parameters
        ----------
        paper1 : dict
            First paper data
        paper2 : dict
            Second paper data
        task : str, optional
            Comparison task description

        Returns
        -------
        dict or None
            Comparison results with similarities, differences, implications
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        cache_key = f"citation_comparison:{paper1.get('pmid', '')}:{paper2.get('pmid', '')}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        self._notify_progress(0.3, "Comparing citations...")

        try:
            prompt_context = {
                "paper1": paper1,
                "paper2": paper2,
                "task": task,
            }

            result = self.llm_client.generate_with_template(
                "citation_comparison.md", **prompt_context
            )

            if not result:
                return None

            comparison = {
                "paper1_id": paper1.get("pmid", "unknown"),
                "paper2_id": paper2.get("pmid", "unknown"),
                "summary": result,
                "similarities": self._extract_similarities(result),
                "differences": self._extract_differences(result),
                "implications": self._extract_implications(result),
            }

            self._analysis_cache[cache_key] = comparison
            self._notify_progress(1.0, "Citation comparison complete")

            return comparison

        except Exception as e:
            logger.error(f"Citation comparison error: {e}")
            return None

    def summarize_citations(
        self,
        paper: dict[str, Any],
        citation_count: int,
    ) -> dict[str, Any] | None:
        """
        Summarize citation activity for a paper.

        Parameters
        ----------
        paper : dict
            Paper data
        citation_count : int
            Number of citations

        Returns
        -------
        dict or None
            Citation summary
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        cache_key = f"citation_summary:{paper.get('pmid', '')}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        self._notify_progress(0.3, "Summarizing citations...")

        try:
            prompt_context = {
                "paper": paper,
                "citation_count": citation_count,
            }

            result = self.llm_client.generate_with_template(
                "citation_summary.md", **prompt_context
            )

            if not result:
                return None

            summary = {
                "paper_id": paper.get("pmid", "unknown"),
                "citation_count": citation_count,
                "summary": result,
                "trend": self._extract_trend(result),
                "patterns": self._extract_patterns(result),
            }

            self._analysis_cache[cache_key] = summary
            self._notify_progress(1.0, "Citation summary complete")

            return summary

        except Exception as e:
            logger.error(f"Citation summary error: {e}")
            return None

    def execute(self, **kwargs) -> dict[str, Any]:
        """
        Execute the agent based on task type.

        Supported tasks:
        - "analyze": analyze_citation_context
        - "compare": compare_citations
        - "summarize": summarize_citations

        Parameters
        ----------
        **kwargs : dict
            Task-specific parameters

        Returns
        -------
        dict
            Task results
        """
        task_type = kwargs.get("task_type", "analyze")

        if task_type == "analyze":
            return self.analyze_citation_context(
                paper=kwargs.get("paper", {}),
                context=kwargs.get("context", "general"),
                task=kwargs.get("task", "Provide analysis."),
            )

        elif task_type == "compare":
            return self.compare_citations(
                paper1=kwargs.get("paper1", {}),
                paper2=kwargs.get("paper2", {}),
                task=kwargs.get("task", "Compare these papers."),
            )

        elif task_type == "summarize":
            return self.summarize_citations(
                paper=kwargs.get("paper", {}),
                citation_count=kwargs.get("citation_count", 0),
            )

        else:
            logger.warning(f"Unknown task type: {task_type}")
            return {"error": f"Unknown task type: {task_type}"}

    def _extract_insights(self, text: str) -> list[str]:
        """Extract key insights from analysis text."""
        insights = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("*") or line.startswith("-"):
                insights.append(line[1:].strip())
            elif len(line) > 10 and len(line) < 100:
                insights.append(line)
        return insights[:5]

    def _extract_methodology(self) -> str:
        """Extract methodology notes."""
        return "Analysis based on citation context and related works. Generated by SmartCitationAnalysis agent."

    def _extract_limitations(self) -> str:
        """Extract limitations."""
        return "Analysis may not capture all citation nuances. LLM-generated insights should be verified."

    def _extract_similarities(self, text: str) -> list[str]:
        """Extract similarities from comparison."""
        similarities = []
        for line in text.split("\n"):
            if "similar" in line.lower() or "same" in line.lower():
                similarities.append(line.strip())
        return similarities[:3]

    def _extract_differences(self, text: str) -> list[str]:
        """Extract differences from comparison."""
        differences = []
        for line in text.split("\n"):
            if "different" in line.lower() or "contrast" in line.lower():
                differences.append(line.strip())
        return differences[:3]

    def _extract_implications(self, text: str) -> str:
        """Extract implications from comparison."""
        for line in text.split("\n"):
            if "implication" in line.lower() or "combined" in line.lower():
                return line.strip()
        return "Combined insights suggest potential research directions."

    def _extract_trend(self, text: str) -> str:
        """Extract trend from summary."""
        if "increasing" in text.lower():
            return "increasing"
        elif "declining" in text.lower():
            return "declining"
        else:
            return "steady"

    def _extract_patterns(self, text: str) -> list[str]:
        """Extract citation patterns."""
        patterns = []
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > 5 and len(line) < 80:
                patterns.append(line)
        return patterns[:3]

    def screen_papers(
        self,
        papers: list[dict[str, Any]],
        inclusion_criteria: list[str],
        exclusion_criteria: list[str],
    ) -> dict[str, Any] | None:
        """
        Screen papers based on inclusion/exclusion criteria using LLM.

        Parameters
        ----------
        papers : list of dict
            List of paper data dictionaries
        inclusion_criteria : list of str
            List of inclusion criteria
        exclusion_criteria : list of str
            List of exclusion criteria

        Returns
        -------
        dict or None
            Screening results with classifications and reasoning
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        if not papers:
            logger.warning("No papers to screen")
            return None

        cache_key = f"paper_screening:{hash(tuple(c for c in inclusion_criteria))}:{hash(tuple(c for c in exclusion_criteria))}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        self._notify_progress(0.1, f"Screening {len(papers)} papers...")

        try:
            prompt_context = {
                "papers": papers,
                "inclusion_criteria": inclusion_criteria,
                "exclusion_criteria": exclusion_criteria,
            }

            result = self.llm_client.generate_with_template("paper_screening.md", **prompt_context)

            if not result:
                return None

            # Parse results
            screenings = []
            lines = result.split("\n")
            current_screening = None

            for i, line in enumerate(lines):
                if line.strip().startswith("### Paper"):
                    if current_screening:
                        screenings.append(current_screening)
                    current_screening = {
                        "paper_index": int(line.split()[-1]) - 1,
                        "classification": None,
                        "reasoning": "",
                        "evidence": "",
                    }
                elif current_screening:
                    if line.strip().startswith("1. Classification"):
                        current_screening["classification"] = line.split(":")[-1].strip()
                    elif line.strip().startswith("2. Reasoning"):
                        current_screening["reasoning"] = line.split(":", 1)[-1].strip()
                    elif line.strip().startswith("3. Evidence"):
                        current_screening["evidence"] = line.split(":", 1)[-1].strip()

            if current_screening:
                screenings.append(current_screening)

            results = {
                "total_papers": len(papers),
                "included": [s for s in screenings if s.get("classification") == "INCLUDE"],
                "excluded": [s for s in screenings if s.get("classification") == "EXCLUDE"],
                "undecided": [s for s in screenings if s.get("classification") == "UNDECIDED"],
                "screenings": screenings,
                "summary": result,
            }

            self._analysis_cache[cache_key] = results
            self._notify_progress(
                1.0,
                f"Screening complete: {len(results['included'])} included, {len(results['excluded'])} excluded",
            )

            return results

        except Exception as e:
            logger.error(f"Paper screening error: {e}")
            return None

    def analyze_research_question(
        self,
        research_question: str,
        time_frame: str = "all",
    ) -> dict[str, Any] | None:
        """
        Analyze and expand a research question.

        Parameters
        ----------
        research_question : str
            Research question to analyze
        time_frame : str, optional
            Time frame for literature search

        Returns
        -------
        dict or None
            Research question analysis with search terms, gaps, and strategy
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        cache_key = f"research_question:{hash(research_question)}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        self._notify_progress(0.2, "Analyzing research question...")

        try:
            prompt_context = {
                "research_question": research_question,
                "time_frame": time_frame,
            }

            result = self.llm_client.generate_with_template(
                "research_question_analysis.md", **prompt_context
            )

            if not result:
                return None

            analysis = {
                "research_question": research_question,
                "time_frame": time_frame,
                "analysis": result,
                "expanded_terms": self._extract_expanded_terms(result),
                "knowledge_gaps": self._extract_knowledge_gaps(result),
                "search_strategy": self._extract_search_strategy(result),
                "preliminary_findings": self._extract_preliminary_findings(result),
            }

            self._analysis_cache[cache_key] = analysis
            self._notify_progress(1.0, "Research question analysis complete")

            return analysis

        except Exception as e:
            logger.error(f"Research question analysis error: {e}")
            return None

    def analyze_preprint(
        self,
        paper: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Perform preprint-specific quality assessment.

        Parameters
        ----------
        paper : dict
            Paper data including preprint server info

        Returns
        -------
        dict or None
            Preprint analysis with methodology, transparency, and recommendations
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        cache_key = f"preprint_analysis:{paper.get('pmid', '')}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        self._notify_progress(0.3, "Analyzing preprint...")

        try:
            prompt_context = {
                "paper": paper,
            }

            result = self.llm_client.generate_with_template(
                "preprint_analysis.md", **prompt_context
            )

            if not result:
                return None

            analysis = {
                "paper_id": paper.get("pmid", "unknown"),
                "preprint_server": paper.get("preprint_server", "unknown"),
                "analysis": result,
                "methodology_assessment": self._extract_methodology_assessment(result),
                "transparency_indicators": self._extract_transparency_indicators(result),
                "preprint_considerations": self._extract_preprint_considerations(result),
                "recommendations": self._extract_preprint_recommendations(result),
            }

            self._analysis_cache[cache_key] = analysis
            self._notify_progress(1.0, "Preprint analysis complete")

            return analysis

        except Exception as e:
            logger.error(f"Preprint analysis error: {e}")
            return None

    def generate_literature_review(
        self,
        research_topic: str,
        papers: list[dict[str, Any]],
        time_frame: str = "all",
        key_concepts: list[str] | None = None,
        excluded_topics: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Generate a comprehensive literature review.

        Parameters
        ----------
        research_topic : str
            Topic for the literature review
        papers : list of dict
            List of paper data
        time_frame : str, optional
            Time frame for literature
        key_concepts : list of str, optional
            Key concepts to cover
        excluded_topics : list of str, optional
            Topics to exclude

        Returns
        -------
        dict or None
            Literature review with historical overview, current state, trends
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        if not papers:
            logger.warning("No papers for literature review")
            return None

        cache_key = f"literature_review:{hash(research_topic)}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        self._notify_progress(0.2, f"Generating literature review for {len(papers)} papers...")

        try:
            prompt_context = {
                "research_topic": research_topic,
                "time_frame": time_frame,
                "key_concepts": key_concepts or [],
                "excluded_topics": excluded_topics or [],
                "papers": papers,
            }

            result = self.llm_client.generate_with_template(
                "literature_review.md", **prompt_context
            )

            if not result:
                return None

            review = {
                "research_topic": research_topic,
                "time_frame": time_frame,
                "literature_review": result,
                "historical_overview": self._extract_historical_overview(result),
                "current_state": self._extract_current_state(result),
                "research_trends": self._extract_research_trends(result),
                "future_directions": self._extract_future_directions(result),
                "key_papers": self._extract_key_papers(papers),
            }

            self._analysis_cache[cache_key] = review
            self._notify_progress(1.0, "Literature review complete")

            return review

        except Exception as e:
            logger.error(f"Literature review error: {e}")
            return None

    def build_knowledge_graph(
        self,
        research_domain: str,
        entities: list[str] | None = None,
        relationships: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Build a knowledge graph from research domain.

        Parameters
        ----------
        research_domain : str
            Domain for the knowledge graph
        entities : list of str, optional
            Key entities to include
        relationships : list of str, optional
            Known relationships

        Returns
        -------
        dict or None
            Knowledge graph with nodes, edges, and analysis
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        cache_key = f"knowledge_graph:{hash(research_domain)}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        self._notify_progress(0.2, "Building knowledge graph...")

        try:
            prompt_context = {
                "research_domain": research_domain,
                "entities": entities or [],
                "relationships": relationships or [],
            }

            result = self.llm_client.generate_with_template("knowledge_graph.md", **prompt_context)

            if not result:
                return None

            graph = {
                "research_domain": research_domain,
                "knowledge_graph": result,
                "nodes": self._extract_nodes(result),
                "edges": self._extract_edges(result),
                "graph_analysis": self._extract_graph_analysis(result),
                "format_graphml": self._extract_graphml(result),
                "format_json": self._extract_graph_json(result),
            }

            self._analysis_cache[cache_key] = graph
            self._notify_progress(1.0, "Knowledge graph complete")

            return graph

        except Exception as e:
            logger.error(f"Knowledge graph error: {e}")
            return None

    def integrate_clinical_trials(
        self,
        condition: str,
        intervention: str,
    ) -> dict[str, Any] | None:
        """
        Integrate clinical trial data with research findings.

        Parameters
        ----------
        condition : str
            Medical condition
        intervention : str
            Intervention or treatment

        Returns
        -------
        dict or None
            Clinical trial integration with landscape, evidence, recommendations
        """
        if not self.llm_client.enabled:
            logger.warning("LLM not enabled")
            return None

        cache_key = f"clinical_trials:{hash(condition + intervention)}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        self._notify_progress(0.3, "Integrating clinical trials...")

        try:
            prompt_context = {
                "condition": condition,
                "intervention": intervention,
            }

            result = self.llm_client.generate_with_template("clinical_trials.md", **prompt_context)

            if not result:
                return None

            integration = {
                "condition": condition,
                "intervention": intervention,
                "integration": result,
                "clinical_trial_landscape": self._extract_trial_landscape(result),
                "evidence_integration": self._extract_evidence_integration(result),
                "practice_recommendations": self._extract_practice_recommendations(result),
                "trial_selection_criteria": self._extract_trial_selection_criteria(result),
            }

            self._analysis_cache[cache_key] = integration
            self._notify_progress(1.0, "Clinical trials integration complete")

            return integration

        except Exception as e:
            logger.error(f"Clinical trials integration error: {e}")
            return None

    def _extract_expanded_terms(self, text: str) -> list[str]:
        """Extract expanded search terms."""
        terms = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("-") and len(line) > 3:
                terms.append(line[1:].strip())
        return terms[:10]

    def _extract_knowledge_gaps(self, text: str) -> list[str]:
        """Extract knowledge gaps."""
        gaps = []
        for line in text.split("\n"):
            if "gap" in line.lower() or "need" in line.lower():
                gaps.append(line.strip())
        return gaps[:5]

    def _extract_search_strategy(self, text: str) -> str:
        """Extract search strategy."""
        for line in text.split("\n"):
            if "search" in line.lower() and (
                "query" in line.lower() or "strategy" in line.lower()
            ):
                return line.strip()
        return "Use comprehensive search query covering all key concepts."

    def _extract_preliminary_findings(self, text: str) -> list[str]:
        """Extract preliminary findings."""
        findings = []
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > 10 and len(line) < 100:
                findings.append(line)
        return findings[:5]

    def _extract_methodology_assessment(self, text: str) -> str:
        """Extract methodology assessment."""
        if "methodology" in text.lower():
            for line in text.split("\n"):
                if "methodology" in line.lower():
                    return line.strip()
        return "Methodology quality assessment based on preprint standards."

    def _extract_transparency_indicators(self, text: str) -> list[str]:
        """Extract transparency indicators."""
        indicators = []
        for line in text.split("\n"):
            if "transparency" in line.lower() or "data" in line.lower() or "code" in line.lower():
                indicators.append(line.strip())
        return indicators[:5]

    def _extract_preprint_considerations(self, text: str) -> list[str]:
        """Extract preprint considerations."""
        considerations = []
        for line in text.split("\n"):
            if "preprint" in line.lower() or "peer" in line.lower():
                considerations.append(line.strip())
        return considerations[:5]

    def _extract_preprint_recommendations(self, text: str) -> str:
        """Extract preprint recommendations."""
        for line in text.split("\n"):
            if "recommend" in line.lower() or "important" in line.lower():
                return line.strip()
        return "Readers should consider preprint status when interpreting results."

    def _extract_historical_overview(self, text: str) -> str:
        """Extract historical overview."""
        for line in text.split("\n"):
            if "historical" in line.lower() or "timeline" in line.lower():
                return line.strip()
        return "Historical development of the research topic."

    def _extract_current_state(self, text: str) -> str:
        """Extract current state of research."""
        for line in text.split("\n"):
            if "current" in line.lower() or "state" in line.lower():
                return line.strip()
        return "Current state of research in the field."

    def _extract_research_trends(self, text: str) -> list[str]:
        """Extract research trends."""
        trends = []
        for line in text.split("\n"):
            if "trend" in line.lower() or "emerging" in line.lower():
                trends.append(line.strip())
        return trends[:5]

    def _extract_future_directions(self, text: str) -> list[str]:
        """Extract future research directions."""
        directions = []
        for line in text.split("\n"):
            if "future" in line.lower() or "recommend" in line.lower():
                directions.append(line.strip())
        return directions[:5]

    def _extract_key_papers(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract key papers for reference."""
        return papers[:10]

    def _extract_nodes(self, text: str) -> list[dict[str, Any]]:
        """Extract nodes from knowledge graph."""
        nodes = []
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            if "**" in lines[i] and "id" in lines[i].lower():
                node = {"id": lines[i].strip()}
                i += 1
                while i < len(lines) and lines[i].strip().startswith("-"):
                    node[lines[i].strip().split(":")[0].strip("- ").strip()] = (
                        lines[i].strip().split(":", 1)[-1].strip()
                    )
                    i += 1
                nodes.append(node)
            else:
                i += 1
        return nodes[:20]

    def _extract_edges(self, text: str) -> list[dict[str, Any]]:
        """Extract edges from knowledge graph."""
        edges = []
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            if "**" in lines[i] and "edge" in lines[i].lower():
                edge = {"source": "", "target": "", "type": "", "evidence": ""}
                i += 1
                while i < len(lines) and lines[i].strip().startswith("-"):
                    parts = lines[i].strip().split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip("- ").strip()
                        if key in edge:
                            edge[key] = parts[1].strip()
                    i += 1
                edges.append(edge)
            else:
                i += 1
        return edges[:50]

    def _extract_graph_analysis(self, text: str) -> dict[str, Any]:
        """Extract graph analysis."""
        analysis = {"central_concepts": [], "knowledge_gaps": [], "connected_components": 0}
        for line in text.split("\n"):
            line = line.strip()
            if "central" in line.lower() or "important" in line.lower():
                analysis["central_concepts"].append(line)
            elif "gap" in line.lower():
                analysis["knowledge_gaps"].append(line)
        analysis["connected_components"] = len(analysis["central_concepts"]) // 2 + 1
        return analysis

    def _extract_graphml(self, text: str) -> str:
        """Extract GraphML format."""
        start = text.find("<graphml>")
        if start == -1:
            return ""
        end = text.find("</graphml>", start) + 10
        return text[start:end] if end > start + 10 else ""

    def _extract_graph_json(self, text: str) -> dict[str, Any]:
        """Extract JSON format."""
        import json

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        return {"nodes": [], "edges": []}

    def _extract_trial_landscape(self, text: str) -> dict[str, Any]:
        """Extract clinical trial landscape."""
        landscape = {
            "active_trials": 0,
            "completed_trials": 0,
            "geographic_distribution": [],
            "funding_sources": [],
        }
        for line in text.split("\n"):
            if "active" in line.lower() and "trial" in line.lower():
                landscape["active_trials"] += 1
            elif "completed" in line.lower() and "trial" in line.lower():
                landscape["completed_trials"] += 1
            elif "geographic" in line.lower():
                landscape["geographic_distribution"].append(line.strip())
        return landscape

    def _extract_evidence_integration(self, text: str) -> str:
        """Extract evidence integration."""
        for line in text.split("\n"):
            if "evidence" in line.lower() and "integration" in line.lower():
                return line.strip()
        return "Integrated evidence from clinical trials and research findings."

    def _extract_practice_recommendations(self, text: str) -> list[str]:
        """Extract practice recommendations."""
        recommendations = []
        for line in text.split("\n"):
            if "recommend" in line.lower() or "clinical" in line.lower():
                recommendations.append(line.strip())
        return recommendations[:5]

    def _extract_trial_selection_criteria(self, text: str) -> dict[str, Any]:
        """Extract trial selection criteria."""
        criteria = {
            "inclusion": [],
            "exclusion": [],
            "primary_outcomes": [],
            "statistical_significance": False,
            "clinical_relevance": "",
        }
        for line in text.split("\n"):
            if "inclusion" in line.lower():
                criteria["inclusion"].append(line.strip())
            elif "exclusion" in line.lower():
                criteria["exclusion"].append(line.strip())
        criteria["statistical_significance"] = any(
            "significant" in line.lower() for line in text.split("\n")
        )
        return criteria


__all__ = ["BaseAgent", "SmartCitationAnalysis"]
