"""Integration tests for the live ClinicalTrials.gov API.

Usage:
    pytest tests/integration/ --run-integration -v
"""

import pytest

from pyeuropepmc.features.search import ClinicalTrialsClient
from pyeuropepmc.models import ClinicalTrial


@pytest.mark.integration
class TestClinicalTrialsLiveAPI:
    """Hit the real ClinicalTrials.gov API."""

    @pytest.fixture(scope="class")
    def client(self) -> ClinicalTrialsClient:
        return ClinicalTrialsClient()

    def test_search_keyword(self, client: ClinicalTrialsClient) -> None:
        """Search for a common condition."""
        results = client.search("COVID-19", limit=10)
        assert len(results) > 0
        for r in results:
            assert r.title
            assert r.source == "clinicaltrials"

    def test_search_by_condition(self, client: ClinicalTrialsClient) -> None:
        """Search by medical condition."""
        results = client.search_by_condition("chronic fatigue syndrome", limit=10)
        assert len(results) > 0
        for r in results:
            assert r.title

    def test_search_by_intervention(self, client: ClinicalTrialsClient) -> None:
        """Search by intervention/treatment."""
        results = client.search_by_intervention("cognitive behavioral therapy", limit=10)
        assert len(results) > 0

    def test_get_paper_by_nct_id(self, client: ClinicalTrialsClient) -> None:
        """Fetch a study by its NCT number."""
        nct = "NCT04280705"  # ACTT-1 trial evaluating remdesivir for COVID-19
        study = client.get_paper(nct)
        assert study is not None
        assert study.title
        # Official title is the generic ACTT-1 protocol; remdesivir appears as intervention
        meta = study.extra_metadata
        assert meta.get("nct_id") == nct
        assert meta.get("overall_status") is not None
        interventions = " ".join(str(i) for i in (meta.get("interventions") or [])).lower()
        assert "remdesivir" in interventions or "covid" in study.title.lower()

    def test_get_paper_not_found(self, client: ClinicalTrialsClient) -> None:
        """Non-existent NCT number returns None."""
        study = client.get_paper("NCT00000000")
        assert study is None

    def test_search_limit(self, client: ClinicalTrialsClient) -> None:
        """Verify limit parameter is respected."""
        for limit in [1, 5]:
            results = client.search("asthma", limit=limit)
            assert len(results) <= limit

    def test_extra_metadata(self, client: ClinicalTrialsClient) -> None:
        """Extra metadata includes phase, sponsor, enrollment, status."""
        results = client.search("vaccine", limit=3)
        for r in results:
            meta = r.extra_metadata
            # At least some of these should be present
            has_meta = bool(meta.get("nct_id") or meta.get("phase") or meta.get("overall_status"))
            assert has_meta, f"No extra_metadata for {r.title}"

    def test_clinical_trial_model(self, client: ClinicalTrialsClient) -> None:
        """Convert a result to ClinicalTrial model."""
        results = client.search("diabetes", limit=1)
        if results:
            r = results[0]
            ct = ClinicalTrial.from_literature_result(r)
            assert isinstance(ct, ClinicalTrial)
            assert ct.title
            if ct.conditions:
                assert len(ct.conditions) > 0
