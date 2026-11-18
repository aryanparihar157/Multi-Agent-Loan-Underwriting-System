"""
Credit-History Agent Module.
Specialist agent querying in-memory prior record store and assessing credit risk parameters.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from semantic_kernel import Kernel
from tools.credit_tools import CreditTools
from models.schemas import SharedUnderwritingRecord, BureauRecord


class CreditHistoryAgent:
    """Specialist agent querying in-memory credit history store and identifying red flags."""

    INSTRUCTIONS = (
        "You are the Credit-History Specialist Agent. You check the applicant's record in "
        "the in-memory bureau database for prior write-offs, defaults, and current CIBIL score. "
        "You identify any underwriting red flags."
    )

    def __init__(self, kernel: Kernel | None = None, data_file: Optional[str] = None):
        self.kernel = kernel or Kernel()
        self.tools = CreditTools(data_file=data_file)
        if "credit_tools" not in self.kernel.plugins:
            self.kernel.add_plugin(self.tools, plugin_name="credit_tools")

    def process(self, shared_record: SharedUnderwritingRecord) -> SharedUnderwritingRecord:
        """
        Queries in-memory bureau records and assesses credit risk into the shared record.
        """
        app_id = shared_record.application.applicant_id

        # Tool 1: In-memory bureau lookup
        bureau_data = self.tools.query_bureau_records(applicant_id=app_id)
        shared_record.bureau_profile = BureauRecord(
            applicant_id=bureau_data["applicant_id"],
            cibil_score=bureau_data["cibil_score"],
            past_defaults=bureau_data["past_defaults"],
            active_loans=bureau_data["active_loans"],
            late_payment_count_last_2yrs=bureau_data["late_payments_last_2yrs"],
            credit_remarks=bureau_data["credit_remarks"],
        )

        shared_record.add_trace(
            agent_name="CreditHistoryAgent",
            action="query_bureau_records",
            tool_used="CreditTools.query_bureau_records",
            status="SUCCESS",
            details=bureau_data,
        )

        # Tool 2: Credit risk & red flag assessment
        risk_result = self.tools.assess_credit_risk(
            cibil_score=bureau_data["cibil_score"],
            past_defaults=bureau_data["past_defaults"],
            late_payments=bureau_data["late_payments_last_2yrs"],
        )

        shared_record.credit_check_passed = risk_result["credit_check_passed"]
        shared_record.credit_risk_level = risk_result["risk_tier"]
        shared_record.credit_justification = risk_result["justification"]

        shared_record.add_trace(
            agent_name="CreditHistoryAgent",
            action="assess_credit_risk",
            tool_used="CreditTools.assess_credit_risk",
            status="PASS" if risk_result["credit_check_passed"] else "FAIL",
            details=risk_result,
        )

        return shared_record

    def add_defaulter_record(self, record_data: Dict[str, Any]) -> None:
        """Adds or updates an applicant record in the credit tools bureau store."""
        self.tools.add_or_update_record(record_data)

    def remove_defaulter_record(self, applicant_id: str) -> bool:
        """Removes an applicant record from the credit tools bureau store."""
        return self.tools.remove_record(applicant_id)
