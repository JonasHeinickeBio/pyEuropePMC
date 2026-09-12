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

Everything here is imported lazily (PEP 562).  The LLM-backed pieces need
``pip install pyeuropepmc[agentic]`` (langchain, langchain-openai, openai,
langgraph); importing this package without those installed is fine as long as
you only touch the non-LLM helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyeuropepmc._lazy import lazy_module

_LAZY = {
    "SmartCitationAnalysis": "pyeuropepmc.agentic.agents:SmartCitationAnalysis",
    "BaseAgent": "pyeuropepmc.agentic.base:BaseAgent",
    "LLMClient": "pyeuropepmc.agentic.llm_client:LLMClient",
    "create_llm_client": "pyeuropepmc.agentic.llm_client:create_llm_client",
    "AgentConfig": "pyeuropepmc.agentic.orchestrator:AgentConfig",
    "AgentOrchestrator": "pyeuropepmc.agentic.orchestrator:AgentOrchestrator",
    "AgentRole": "pyeuropepmc.agentic.orchestrator:AgentRole",
    "Task": "pyeuropepmc.agentic.orchestrator:Task",
    "PipelineStage": "pyeuropepmc.agentic.pipeline:PipelineStage",
    "PipelineState": "pyeuropepmc.agentic.pipeline:PipelineState",
    "PipelineStep": "pyeuropepmc.agentic.pipeline:PipelineStep",
    "ResearchPipeline": "pyeuropepmc.agentic.pipeline:ResearchPipeline",
    "BaseTool": "pyeuropepmc.agentic.registry:BaseTool",
    "ToolInfo": "pyeuropepmc.agentic.registry:ToolInfo",
    "ToolRegistry": "pyeuropepmc.agentic.registry:ToolRegistry",
    "ToolType": "pyeuropepmc.agentic.registry:ToolType",
    "register": "pyeuropepmc.agentic.registry:register",
    "registry": "pyeuropepmc.agentic.registry:registry",
    "TaskNode": "pyeuropepmc.agentic.task_planner:TaskNode",
    "TaskPlanner": "pyeuropepmc.agentic.task_planner:TaskPlanner",
    "TaskStatus": "pyeuropepmc.agentic.task_planner:TaskStatus",
}

_lazy_getattr, __dir__, __all__ = lazy_module(__name__, _LAZY)


def __getattr__(name: str) -> Any:
    """Resolve a public attribute lazily (see :mod:`pyeuropepmc._lazy`)."""
    return _lazy_getattr(name)


if TYPE_CHECKING:
    from pyeuropepmc.agentic.agents import SmartCitationAnalysis as SmartCitationAnalysis
    from pyeuropepmc.agentic.base import BaseAgent as BaseAgent
    from pyeuropepmc.agentic.llm_client import (
        LLMClient as LLMClient,
        create_llm_client as create_llm_client,
    )
    from pyeuropepmc.agentic.orchestrator import (
        AgentConfig as AgentConfig,
        AgentOrchestrator as AgentOrchestrator,
        AgentRole as AgentRole,
        Task as Task,
    )
    from pyeuropepmc.agentic.pipeline import (
        PipelineStage as PipelineStage,
        PipelineState as PipelineState,
        PipelineStep as PipelineStep,
        ResearchPipeline as ResearchPipeline,
    )
    from pyeuropepmc.agentic.registry import (
        BaseTool as BaseTool,
        ToolInfo as ToolInfo,
        ToolRegistry as ToolRegistry,
        ToolType as ToolType,
        register as register,
        registry as registry,
    )
    from pyeuropepmc.agentic.task_planner import (
        TaskNode as TaskNode,
        TaskPlanner as TaskPlanner,
        TaskStatus as TaskStatus,
    )
