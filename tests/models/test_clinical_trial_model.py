"""Unit tests for ClinicalTrial.from_literature_result / to_literature_result."""

from __future__ import annotations

from pyeuropepmc.models.clinical_trial import ClinicalTrial, TrialPhase, TrialStatus
from pyeuropepmc.models.literature import LiteratureResult


def _result(meta: dict | None) -> LiteratureResult:
    return LiteratureResult(
        source="clinicaltrials", source_id="NCT01234567", title="A trial", extra_metadata=meta
    )


class TestFromLiteratureResult:
    def test_reads_client_overall_status(self):
        trial = ClinicalTrial.from_literature_result(
            _result({"nct_id": "NCT01234567", "overall_status": "RECRUITING", "phase": "PHASE2"})
        )
        assert trial.status == TrialStatus.RECRUITING
        assert trial.phase == TrialPhase.PHASE2

    def test_round_trip_keeps_status(self):
        original = ClinicalTrial(
            nct_id="NCT07654321",
            title="Round trip",
            status=TrialStatus.TERMINATED,
            phase=TrialPhase.PHASE3,
            conditions=["ME/CFS"],
        )
        trial = ClinicalTrial.from_literature_result(original.to_literature_result())
        assert (trial.status, trial.phase, trial.conditions) == (
            TrialStatus.TERMINATED,
            TrialPhase.PHASE3,
            ["ME/CFS"],
        )

    def test_status_key_wins_over_overall_status(self):
        trial = ClinicalTrial.from_literature_result(
            _result({"status": "COMPLETED", "overall_status": "RECRUITING"})
        )
        assert trial.status == "COMPLETED"

    def test_missing_or_empty_values_fall_back_to_defaults(self):
        """The client stores "" for a trial without phases and None for absent lists."""
        trial = ClinicalTrial.from_literature_result(
            _result({"overall_status": "", "phase": "", "conditions": None})
        )
        assert trial.status == TrialStatus.UNKNOWN
        assert trial.phase == TrialPhase.NA
        assert trial.conditions == []

    def test_no_extra_metadata(self):
        trial = ClinicalTrial.from_literature_result(_result(None))
        assert trial.nct_id == "NCT01234567"
        assert trial.status == TrialStatus.UNKNOWN
