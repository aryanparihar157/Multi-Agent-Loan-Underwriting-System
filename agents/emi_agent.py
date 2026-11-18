"""
EMI Computation Agent Module.
Specialist agent executing deterministic loan math and amortization schedules.
"""
from __future__ import annotations

from typing import Any, Dict
from semantic_kernel import Kernel
from tools.emi_tools import EMITools
from models.schemas import SharedUnderwritingRecord


class EMIComputationAgent:
    """Specialist agent for deterministic loan math (not model-hallucinated math)."""

    INSTRUCTIONS = (
        "You are the EMI Computation Specialist Agent. You use strictly deterministic "
        "mathematical reducing-balance formulas to compute the applicant's exact monthly EMI, "
        "total interest, and amortization schedule for the requested tenure."
    )

    def __init__(self, kernel: Kernel | None = None):
        self.kernel = kernel or Kernel()
        self.tools = EMITools()
        if "emi_tools" not in self.kernel.plugins:
            self.kernel.add_plugin(self.tools, plugin_name="emi_tools")

    def process(self, shared_record: SharedUnderwritingRecord) -> SharedUnderwritingRecord:
        """
        Executes deterministic reducing-balance calculation and updates the shared record.
        """
        principal = shared_record.extracted_requested_amount or 0.0
        tenure = shared_record.extracted_tenure_months or 0
        rate = shared_record.annual_interest_rate

        # Tool 1: Compute reducing-balance monthly EMI
        emi_result = self.tools.compute_reducing_balance_emi(
            principal=principal,
            annual_rate_percent=rate,
            tenure_months=tenure,
        )

        shared_record.computed_monthly_emi = emi_result["monthly_emi"]
        shared_record.total_payable_amount = emi_result["total_payable"]
        shared_record.total_interest = emi_result["total_interest"]

        shared_record.add_trace(
            agent_name="EMIComputationAgent",
            action="compute_reducing_balance_emi",
            tool_used="EMITools.compute_reducing_balance_emi",
            status="SUCCESS",
            details=emi_result,
        )

        # Tool 2: Generate amortization breakdown summary
        amort_result = self.tools.generate_amortization_schedule(
            principal=principal,
            annual_rate_percent=rate,
            tenure_months=tenure,
        )
        shared_record.amortization_summary = amort_result["summary"]

        shared_record.add_trace(
            agent_name="EMIComputationAgent",
            action="generate_amortization_schedule",
            tool_used="EMITools.generate_amortization_schedule",
            status="SUCCESS",
            details=amort_result["summary"],
        )

        return shared_record
