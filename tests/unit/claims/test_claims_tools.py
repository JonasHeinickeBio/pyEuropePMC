"""Tests for agentic claims tools."""

from unittest.mock import patch

import pytest

from pyeuropepmc.agentic.claims_tools import (
    claims_registry,
    claim_extract,
    claim_summary,
    claim_verify,
    claim_review,
    claim_accept,
    claim_write,
    register_all_claims_tools,
)


class TestClaimsTools:
    def test_registry_has_tools(self):
        tools = claims_registry.list_all()
        tool_names = [t.name for t in tools]
        assert "claim_extract" in tool_names
        assert "claim_verify" in tool_names
        assert "claim_review" in tool_names
        assert "claim_accept" in tool_names
        assert "claim_write" in tool_names
        assert "claim_summary" in tool_names
        assert "claim_get_evidence" in tool_names
        assert "claim_run_workflow" in tool_names

    def test_claim_extract_no_llm(self):
        result = claim_extract(text="First claim. Second claim here.")
        assert result["success"] is True
        assert result["count"] >= 1

    def test_claim_summary_no_claims(self):
        from pyeuropepmc.agentic.claims_tools import _workflow_state
        _workflow_state.clear()
        result = claim_summary()
        assert result["status"] == "no_claims"

    def test_claim_verify_no_claims(self):
        from pyeuropepmc.agentic.claims_tools import _workflow_state
        _workflow_state.clear()
        result = claim_verify()
        assert result["success"] is False
        assert "No claims" in result["error"]

    def test_claim_accept(self):
        # Run extract first to set up state
        claim_extract(text="Test claim here.")
        result = claim_accept(claim_id="test-123", accepted=True)
        assert result["success"] is True
        assert result["accepted"] is True

    def test_claim_write_no_state(self):
        from pyeuropepmc.agentic.claims_tools import _workflow_state
        _workflow_state.clear()
        result = claim_write()
        assert result["success"] is False
        assert "No claims" in result["error"]

    def test_register_all_claims_tools(self):
        from pyeuropepmc.agentic.registry import ToolRegistry
        target = ToolRegistry(name="target")
        register_all_claims_tools(target)
        tools = target.list_all()
        tool_names = [t.name for t in tools]
        assert "claim_extract" in tool_names
        assert "claim_accept" in tool_names
