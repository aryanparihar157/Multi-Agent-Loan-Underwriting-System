"""
Affordability Agent Module.
Specialist agent applying stated income rules (EMI <= 40% income) and DTI checks.
"""
from __future__ import annotations

from typing import Any, Dict
from semantic_kernel import Kernel
from tools.affordability_tools import AffordabilityTools
from models.schemas import SharedUnderwritingRecord


class AffordabilityAgent:
    """Specialist agent enforcing stated income rules and debt-to-income limits."""

    INSTRUCTIONS = (
        "You are the Affordability Specialist Agent. You apply the bank's stated income rule: "
        "the newly proposed monthly EMI must not exceed 40% of the applicant's verified net monthly "
        "income, and total debt obligations must be within manageable debt-to-income limits."
    )

    def __init__(self, kernel: Kernel | None = None):
        self.kernel = kernel or Kernel()
        self.tools = AffordabilityTools()
        if "affordability_tools" not in self.kernel.plugins:
            self.kernel.add_plugin(self.tools, plugin_name="affordability_tools")

    def process(self, shared_record: SharedUnderwritingRecord) -> SharedUnderwritingRecord:
        """
        Evaluates affordability rules and updates shared record with the verdict.
        """
        monthly_income = shared_record.extracted_monthly_income or 0.0
        existing_emis = shared_record.extracted_existing_emis or 0.0
        proposed_emi = shared_record.computed_monthly_emi or 0.0

        # Tool 1: Stated income rule (40% rule)
        afford_result = self.tools.check_affordability_rule(
            monthly_income=monthly_income,
            existing_emis=existing_emis,
            proposed_emi=proposed_emi,
            max_ratio=0.40,
        )

        shared_record.affordability_passed = afford_result["eligible"]
        shared_record.emi_to_income_ratio = afford_result["emi_to_income_ratio"]
        shared_record.max_allowed_emi = afford_result["max_allowed_emi"]
        shared_record.affordability_verdict = afford_result["reason"]

        shared_record.add_trace(
            agent_name="AffordabilityAgent",
            action="check_affordability_rule",
            tool_used="AffordabilityTools.check_affordability_rule",
            status="PASS" if afford_result["eligible"] else "FAIL",
            details=afford_result,
        )

        # Tool 2: Total Debt-to-Income (DTI) analysis
        total_monthly_debt = existing_emis + proposed_emi
        dti_result = self.tools.calculate_debt_to_income_ratio(
            monthly_income=monthly_income,
            total_monthly_debt=total_monthly_debt,
        )

        shared_record.total_dti_ratio = dti_result["dti_ratio"]

        shared_record.add_trace(
            agent_name="AffordabilityAgent",
            action="calculate_debt_to_income_ratio",
            tool_used="AffordabilityTools.calculate_debt_to_income_ratio",
            status="SUCCESS",
            details=dti_result,
        )

        return shared_record
