"""
Counter-Offer Worker Agent Module (Group-of-3 Add-on Requirement).
Activated when requested amount fails affordability to propose:
- The largest loan amount that passes affordability under current tenure.
- The longest tenure (up to 84 months) that makes the requested amount viable.
"""
from __future__ import annotations

from typing import Any, Dict
from semantic_kernel import Kernel
from tools.counter_offer_tools import CounterOfferTools
from models.schemas import SharedUnderwritingRecord, CounterOfferDetails


class CounterOfferAgent:
    """Specialist worker for synthesizing alternative loan offers when standard criteria fail."""

    INSTRUCTIONS = (
        "You are the Counter-Offer Specialist Worker. When an applicant fails affordability "
        "because the requested EMI exceeds the 40% income cap, you determine viable alternatives: "
        "either the maximum loan principal allowed at the current tenure, or the extended tenure "
        "required to service the requested loan amount."
    )

    def __init__(self, kernel: Kernel | None = None):
        self.kernel = kernel or Kernel()
        self.tools = CounterOfferTools()
        if "counter_offer_tools" not in self.kernel.plugins:
            self.kernel.add_plugin(self.tools, plugin_name="counter_offer_tools")

    def process(self, shared_record: SharedUnderwritingRecord) -> SharedUnderwritingRecord:
        """
        Computes counter-offer alternatives and writes them to the shared record.
        """
        income = shared_record.extracted_monthly_income or 0.0
        existing = shared_record.extracted_existing_emis or 0.0
        rate = shared_record.annual_interest_rate
        tenure = shared_record.extracted_tenure_months or 36
        requested_amt = shared_record.extracted_requested_amount or 0.0

        # Tool 1: Compute maximum eligible loan amount at current tenure
        max_amt_result = self.tools.calculate_max_eligible_loan_amount(
            monthly_income=income,
            existing_emis=existing,
            annual_rate_percent=rate,
            tenure_months=tenure,
            max_ratio=0.40,
        )

        shared_record.add_trace(
            agent_name="CounterOfferAgent",
            action="calculate_max_eligible_loan_amount",
            tool_used="CounterOfferTools.calculate_max_eligible_loan_amount",
            status="SUCCESS",
            details=max_amt_result,
        )

        # Tool 2: Compute extended tenure option for full requested amount
        tenure_result = self.tools.propose_extended_tenure_option(
            requested_amount=requested_amt,
            monthly_income=income,
            existing_emis=existing,
            annual_rate_percent=rate,
            current_tenure=tenure,
            max_tenure_ceiling=84,
            max_ratio=0.40,
        )

        shared_record.add_trace(
            agent_name="CounterOfferAgent",
            action="propose_extended_tenure_option",
            tool_used="CounterOfferTools.propose_extended_tenure_option",
            status="SUCCESS",
            details=tenure_result,
        )

        # Build CounterOfferDetails
        note_parts = [max_amt_result["summary"]]
        if tenure_result["viable_tenure_found"]:
            note_parts.append(tenure_result["summary"])
        else:
            note_parts.append(
                f"Requested amount cannot be serviced within maximum allowable extension of 84 months."
            )

        shared_record.counter_offer = CounterOfferDetails(
            eligible_for_counter_offer=True,
            max_eligible_loan_amount=max_amt_result["max_eligible_loan_amount"],
            max_amount_emi=max_amt_result["target_emi"],
            extended_tenure_months=tenure_result.get("extended_tenure_months"),
            extended_tenure_emi=tenure_result.get("new_monthly_emi"),
            recommendation_note=" | ".join(note_parts),
        )

        return shared_record
