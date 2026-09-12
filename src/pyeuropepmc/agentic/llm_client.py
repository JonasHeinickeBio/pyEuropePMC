"""
Enhanced LLM client with LangChain integration and caching support.

This module provides:
- OpenAI LLM client wrapped with LangChain
- Response caching using existing CacheBackend
- Configurable model, temperature, and other parameters
- Automatic retries and error handling
- LLM opt-in with graceful fallback
"""

import logging
import os
from pathlib import Path
from typing import Any

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None
    HumanMessage = None
    SystemMessage = None
    PromptTemplate = None

from pyeuropepmc.cache.cache import CacheBackend, CacheConfig, CacheDataType

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LangChain-based LLM client with caching support.

    Provides:
    - OpenAI model integration via LangChain
    - Response caching for repeated queries
    - Configurable model parameters (temperature, max_tokens, etc.)
    - Automatic retry on failures
    - Type-safe response handling
    - LLM opt-in with use_llm flag

    Attributes
    ----------
    model : str
        Model name (default: "gpt-4o-mini")
    temperature : float
        Temperature for generation (default: 0.7)
    max_tokens : int
        Maximum output tokens (default: 16384)
    cache : CacheBackend
        Cache backend for storing LLM responses
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        cache_dir: Path | None = None,
        enabled: bool = True,
        cache_ttl: int = 86400,
    ):
        """
        Initialize LLM client.

        Parameters
        ----------
        api_key : str, optional
            OpenAI API key. If None, uses OPENAI_API_KEY environment variable.
        model : str, optional
            Model name. If None, uses OPENAI_MODEL env var or defaults to "gpt-4o-mini".
        base_url : str, optional
            Custom API base URL. If None, uses OPENAI_BASE_URL env var.
            Useful for OpenAI-compatible endpoints (e.g. Blablador, Ollama).
        temperature : float, optional
            Temperature for generation (default: 0.7)
        max_tokens : int, optional
            Maximum output tokens (default: 16384)
        cache_dir : Path, optional
            Directory for cache storage. If None, uses system temp.
        enabled : bool, optional
            Whether LLM client is enabled (default: True)
        cache_ttl : int, optional
            Cache TTL in seconds (default: 86400 = 24 hours)
        """
        if not LANGCHAIN_AVAILABLE:
            logger.warning(
                "LangChain not available. Install with: pip install langchain langchain-openai"
            )
            self.enabled = False
            return

        self.enabled = enabled
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.cache_ttl = cache_ttl

        # Initialize cache
        cache_config = CacheConfig(
            enabled=enabled,
            cache_dir=cache_dir,
            ttl=cache_ttl,
            size_limit_mb=100,  # 100MB cache
        )
        self.cache = CacheBackend(cache_config)

        # Build ChatOpenAI kwargs
        llm_kwargs = dict(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self.api_key,
            timeout=60,
            max_retries=3,
        )
        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        # Initialize LLM
        try:
            self.llm = ChatOpenAI(**llm_kwargs)
            endpoint = self.base_url or "https://api.openai.com/v1"
            logger.info(f"LLM client initialized: {self.model} @ {endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.enabled = False
            self.llm = None

    def _generate_cache_key(self, prompt: str, model: str | None = None, **kwargs) -> str:
        """
        Generate cache key from prompt and parameters.

        Parameters
        ----------
        prompt : str
            Prompt text
        model : str, optional
            Model name (for model-specific caching)
        **kwargs : dict
            Additional parameters

        Returns
        -------
        str
            Cache key hash
        """
        import hashlib

        params = {"prompt": prompt, "model": model or self.model, **kwargs}
        params_json = str(sorted(params.items()))
        return hashlib.sha256(params_json.encode()).hexdigest()[:16]

    def generate(
        self, prompt: str, model: str | None = None, use_llm: bool = True, **kwargs
    ) -> str | None:
        """
        Generate text from LLM with caching.

        Parameters
        ----------
        prompt : str
            Input prompt
        model : str, optional
            Model name to use (overrides default)
        use_llm : bool, optional
            Whether to use LLM (default: True). If False, returns None.
        **kwargs : dict
            Additional parameters for template rendering

        Returns
        -------
        str or None
            Generated text or None if disabled/error/LLM opt-out
        """
        if not use_llm:
            logger.debug("LLM opt-out: returning None")
            return None

        if not self.enabled or not self.llm:
            logger.warning("LLM client not enabled")
            return None

        # Generate cache key
        cache_key = f"llm:generate:{self._generate_cache_key(prompt, model, **kwargs)}"

        # Try cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"LLM cache hit: {cache_key}")
            return cached

        try:
            # Create messages
            messages = [HumanMessage(content=prompt)]

            # Generate response
            response = self.llm.invoke(messages)
            content = response.content if response else None

            if content:
                # Cache result
                self.cache.set(cache_key, content, data_type=CacheDataType.SEARCH)
                logger.debug(f"LLM cache set: {cache_key}")

            return content

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return None

    def generate_with_template(
        self, template_name: str, use_llm: bool = True, **context
    ) -> str | None:
        """
        Generate text using a Jinja2 template.

        Parameters
        ----------
        template_name : str
            Name of template file (e.g., "citation_analysis.md")
        use_llm : bool, optional
            Whether to use LLM (default: True)
        **context : dict
            Context variables for template rendering

        Returns
        -------
        str or None
            Generated text or None if error/LLM opt-out
        """
        if not use_llm:
            logger.debug("LLM opt-out: returning None")
            return None

        if not self.enabled:
            logger.warning("LLM client not enabled")
            return None

        try:
            from pyeuropepmc.prompts import get_templates

            # Render template
            templates = get_templates()
            prompt = templates.render(template_name, **context)

            # Generate response
            return self.generate(prompt, **context)

        except Exception as e:
            logger.error(f"Template generation error: {e}")
            return None

    def clear_cache(self) -> bool:
        """
        Clear LLM response cache.

        Returns
        -------
        bool
            True if successful
        """
        if self.enabled:
            return self.cache.clear()
        return False

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns
        -------
        dict
            Cache statistics
        """
        if self.enabled:
            return self.cache.get_stats()
        return {}

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def close(self):
        """Close the LLM client and release resources."""
        if self.enabled and self.llm:
            self.llm = None
            logger.info("LLM client closed")


# Convenience function
def create_llm_client(
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    cache_dir: Path | None = None,
    enabled: bool = True,
    cache_ttl: int = 86400,
) -> LLMClient:
    """
    Create an LLM client with default configuration.

    Parameters
    ----------
    api_key : str, optional
        OpenAI API key
    model : str, optional
        Model name. If None, uses OPENAI_MODEL env var or "gpt-4o-mini".
    base_url : str, optional
        Custom API base URL. If None, uses OPENAI_BASE_URL env var.
    temperature : float, optional
        Temperature for generation
    max_tokens : int, optional
        Maximum output tokens
    cache_dir : Path, optional
        Cache directory
    enabled : bool, optional
        Whether LLM is enabled
    cache_ttl : int, optional
        Cache TTL in seconds

    Returns
    -------
    LLMClient
        Initialized LLM client
    """
    return LLMClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        cache_dir=cache_dir,
        enabled=enabled,
        cache_ttl=cache_ttl,
    )


__all__ = ["LLMClient", "create_llm_client", "LANGCHAIN_AVAILABLE"]
