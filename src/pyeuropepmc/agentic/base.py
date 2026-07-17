"""
Base classes for agentic workflows.

This module provides the base classes for all agents:
- BaseAgent: Abstract base class for agentic workflows
"""

from abc import ABC, abstractmethod
import logging
from typing import Any

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for agentic workflows.

    Defines the interface for all agents:
    - Execute analysis with typed input/output
    - Provide progress tracking and logging
    - Support caching and state management

    Attributes
    ----------
    llm_client : Any
        LLM client for generating responses
    literature_client : Any
        Literature client for fetching papers
    """

    def __init__(self, **kwargs):
        """
        Initialize base agent.

        Parameters
        ----------
        **kwargs : dict
            Agent-specific initialization parameters
        """
        self.llm_client = kwargs.get("llm_client")
        self.literature_client = kwargs.get("literature_client")
        self._progress_callbacks = []
        self._state: dict[str, Any] = {}

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

    def set_state(self, key: str, value: Any):
        """
        Set agent state value.

        Parameters
        ----------
        key : str
            State key
        value : Any
            State value
        """
        self._state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get agent state value.

        Parameters
        ----------
        key : str
            State key
        default : Any, optional
            Default value if key not found

        Returns
        -------
        Any
            State value or default
        """
        return self._state.get(key, default)

    def clear_state(self):
        """Clear all agent state."""
        self._state = {}


__all__ = ["BaseAgent"]
