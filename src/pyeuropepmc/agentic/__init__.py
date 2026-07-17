"""
Agentic workflows module for pyEuropePMC.

This module provides:
- LLM client integration with LangChain (OpenAI)
- Jinja2 prompt templates for citation analysis
- Smart Citation Analysis agent
- MCP Server LLM tools

Key Components:
- `LLMClient`: LangChain wrapper with caching support
- `SmartCitationAnalysis`: Core citation analysis agent
- Prompt templates for various analysis scenarios
"""

from pyeuropepmc.agentic.agents import SmartCitationAnalysis
from pyeuropepmc.agentic.base import BaseAgent
from pyeuropepmc.agentic.llm_client import LLMClient
from pyeuropepmc.agentic.orchestrator import (
    AgentConfig,
    AgentOrchestrator,
    AgentRole,
    Task,
)
from pyeuropepmc.agentic.pipeline import (
    PipelineStage,
    PipelineState,
    PipelineStep,
    ResearchPipeline,
)
from pyeuropepmc.agentic.registry import (
    BaseTool,
    ToolInfo,
    ToolRegistry,
    ToolType,
    register,
    registry,
)
from pyeuropepmc.agentic.task_planner import (
    TaskNode,
    TaskPlanner,
    TaskStatus,
)

__all__ = [
    "LLMClient",
    "SmartCitationAnalysis",
    "BaseAgent",
    "AgentOrchestrator",
    "AgentRole",
    "AgentConfig",
    "Task",
    "ToolRegistry",
    "ToolType",
    "ToolInfo",
    "BaseTool",
    "register",
    "registry",
    "TaskPlanner",
    "TaskNode",
    "TaskStatus",
    "ResearchPipeline",
    "PipelineStage",
    "PipelineStep",
    "PipelineState",
]
