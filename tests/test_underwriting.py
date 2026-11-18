"""
Test Suite for Multi-Agent Loan Underwriting System.
Covers the three mandatory test scenarios defined in the CSE476 CA2 specification,
plus a credit risk decline scenario.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from models.schemas import DecisionEnum, LoanApplication
from agents.underwriting_manager import UnderwritingManager


@pytest.fixture
def manager(tmp_path):
    log_file = tmp_path / "test_run_log.md"
    bureau_path = Path(__file__).resolve().parent.parent / "data" / "bureau_records.json"
    return UnderwritingManager(
        annual_interest_rate=10.5,
        bureau_data_path=str(bureau_path),
        run_log_path=str(log_file),
    )


def test_scenario_1_sanction_flow(manager):
    """
    Scenario 1: Full Pass / Loan Sanction.
    - Verified Income: $125,000 / month
    - Requested Amount: $500,000 for 36 months
    - Computed EMI: ~$16,252 (13.0% of income, comfortably <= 40%)
    - Bureau: CIBIL 785, 0 defaults
    Expected Outcome: SANCTION with valid computed EMI and 1-paragraph justification.
    """
    app = LoanApplication(
        applicant_id="APP-101",
        applicant_name="Alice Sharma",
        monthly_income=125000.0,
        existing_emis=8000.0,
        requested_amount=500000.0,
        tenure_months=36,
        purpose="Home renovation",
    )

    record = manager.evaluate_application(app)

    # 1. Assert Decision
    assert record.decision == DecisionEnum.SANCTION

    # 2. Assert Deterministic EMI Computation
    assert record.computed_monthly_emi is not None
    assert 16000.0 < record.computed_monthly_emi < 17000.0

    # 3. Assert Affordability Check
    assert record.affordability_passed is True
    assert record.emi_to_income_ratio is not None
    assert record.emi_to_income_ratio <= 0.40

    # 4. Assert Credit Verification
    assert record.credit_check_passed is True
    assert record.bureau_profile.cibil_score == 785

    # 5. Assert 1-paragraph justification is present and reasoned
    assert record.one_paragraph_justification is not None
    assert "SANCTIONED" in record.one_paragraph_justification
    assert "Alice Sharma" in record.one_paragraph_justification


def test_scenario_2_decline_affordability_and_counter_offer(manager):
    """
    Scenario 2: Decline on Affordability Rule (EMI > 40% of income).
    - Verified Income: $35,000 / month (Max allowed EMI = $14,000)
    - Requested Amount: $1,200,000 for 24 months
    - Computed EMI: ~$55,671 (> 150% of income)
    - Bureau: CIBIL 740, 0 defaults
    Expected Outcome:
    - Decision: DECLINE
    - Counter-Offer Worker: Proposes largest viable loan amount and longest tenure.
    """
    app = LoanApplication(
        applicant_id="APP-104",
        applicant_name="Bob Mehta",
        monthly_income=35000.0,
        existing_emis=10000.0,
        requested_amount=1200000.0,
        tenure_months=24,
        purpose="Commercial vehicle purchase",
    )

    record = manager.evaluate_application(app)

    # 1. Assert Decision is DECLINE
    assert record.decision == DecisionEnum.DECLINE
    assert record.affordability_passed is False
    assert record.emi_to_income_ratio > 0.40

    # 2. Assert Counter-Offer Worker Add-On was activated
    assert record.counter_offer is not None
    assert record.counter_offer.eligible_for_counter_offer is True
    assert record.counter_offer.max_eligible_loan_amount is not None
    assert record.counter_offer.max_eligible_loan_amount > 0
    # Max EMI under 40% of $35,000 is $14,000
    assert record.counter_offer.max_amount_emi == 14000.0

    # 3. Assert Justification explains reason and alternatives
    assert "DECLINED" in record.one_paragraph_justification
    assert "Counter-Offer Worker" in record.one_paragraph_justification


def test_scenario_3_refer_missing_income(manager):
    """
    Scenario 3: Halt and Refer on Missing Income.
    - Verified Income: None (missing document)
    - Requested: $300,000 for 24 months
    Expected Outcome:
    - Pipeline halts immediately at Document stage.
    - Decision: REFER (never assumes or hallucinates income).
    - Downstream agents (EMI, Credit, Affordability) are not invoked.
    """
    app = LoanApplication(
        applicant_id="APP-103",
        applicant_name="Charlie Verma",
        monthly_income=None,  # MISSING INCOME
        existing_emis=3000.0,
        requested_amount=300000.0,
        tenure_months=24,
        purpose="Emergency medical expense",
    )

    record = manager.evaluate_application(app)

    # 1. Assert Decision is REFER
    assert record.decision == DecisionEnum.REFER
    assert record.is_valid is False
    assert "monthly_income" in record.validation_errors or "Missing income" in record.decision_reason

    # 2. Confirm pipeline halted: downstream computed values must NOT exist
    assert record.computed_monthly_emi is None
    assert record.affordability_verdict is None

    # 3. Assert Justification specifically states income verification requirement
    assert "REFERRED" in record.one_paragraph_justification
    assert "rather than making an assumption or hallucinating" in record.one_paragraph_justification.lower()


def test_scenario_4_decline_credit_risk(manager):
    """
    Scenario 4: Decline on Credit Risk / Bureau Red Flags.
    - Verified Income: $95,000 / month (High income)
    - Requested: $200,000 for 24 months (Easily affordable)
    - Bureau: CIBIL 590, 2 past defaults
    Expected Outcome: DECLINE due to credit risk despite strong affordability.
    """
    app = LoanApplication(
        applicant_id="APP-102",
        applicant_name="David Khan",
        monthly_income=95000.0,
        existing_emis=5000.0,
        requested_amount=200000.0,
        tenure_months=24,
        purpose="Debt consolidation",
    )

    record = manager.evaluate_application(app)

    assert record.decision == DecisionEnum.DECLINE
    assert record.credit_check_passed is False
    assert record.bureau_profile.cibil_score == 590
    assert record.bureau_profile.past_defaults == 2
    assert "credit check failed" in record.decision_reason.lower()
