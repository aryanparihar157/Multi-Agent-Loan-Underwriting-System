"""
Affordability Assessment Tools.
Implements underwriting stated income rules (e.g. EMI under 40% of net income) and DTI calculation.
"""
from __future__ import annotations

from typing import Annotated, Any, Dict
from semantic_kernel.functions import kernel_function


class AffordabilityTools:
    """Affordability Plugin for Semantic Kernel."""

    DEFAULT_MAX_EMI_RATIO = 0.40  # 40% stated income rule
    DEFAULT_MAX_TOTAL_DTI = 0.55  # 55% total Debt-To-Income cap

    @kernel_function(
        name="check_affordability_rule",
        description="Checks if the proposed EMI satisfies the stated income rule (EMI <= 40% of net income).",
    )
    def check_affordability_rule(
        self,
        monthly_income: Annotated[float, "Applicant verified monthly income."],
        existing_emis: Annotated[float, "Existing monthly EMI commitments."],
        proposed_emi: Annotated[float, "Newly computed monthly EMI for requested loan."],
        max_ratio: Annotated[float, "Maximum allowed EMI to net income ratio, default 0.40."] = 0.40,
    ) -> Dict[str, Any]:
        """
        Tool 1: Verifies EMI fits within stated income threshold (<= 40% rule).
        """
        if monthly_income <= 0:
            return {
                "eligible": False,
                "reason": "Monthly income is non-positive or undefined.",
                "emi_to_income_ratio": 1.0,
                "max_allowed_emi": 0.0,
            }

        emi_to_income_ratio = proposed_emi / monthly_income
        max_allowed_emi = round(monthly_income * max_ratio, 2)
        total_monthly_outflow = existing_emis + proposed_emi
        total_dti_ratio = total_monthly_outflow / monthly_income

        passes_emi_cap = emi_to_income_ratio <= max_ratio
        passes_total_dti = total_dti_ratio <= self.DEFAULT_MAX_TOTAL_DTI

        eligible = passes_emi_cap and passes_total_dti

        if not passes_emi_cap:
            reason = (
                f"Proposed EMI (${proposed_emi:,.2f}) exceeds {int(max_ratio * 100)}% "
                f"of monthly income (${monthly_income:,.2f}). Actual ratio: {emi_to_income_ratio:.1%}, "
                f"maximum allowed EMI is ${max_allowed_emi:,.2f}."
            )
        elif not passes_total_dti:
            reason = (
                f"Combined debt obligations (${total_monthly_outflow:,.2f}) exceed maximum overall "
                f"DTI limit of {int(self.DEFAULT_MAX_TOTAL_DTI * 100)}%. Total DTI: {total_dti_ratio:.1%}."
            )
        else:
            reason = (
                f"Affordable. Proposed EMI (${proposed_emi:,.2f}) represents {emi_to_income_ratio:.1%} "
                f"of monthly income (comfortably within {int(max_ratio * 100)}% ceiling)."
            )

        return {
            "eligible": eligible,
            "monthly_income": monthly_income,
            "existing_emis": existing_emis,
            "proposed_emi": proposed_emi,
            "emi_to_income_ratio": round(emi_to_income_ratio, 4),
            "emi_percentage": f"{emi_to_income_ratio:.1%}",
            "total_dti_ratio": round(total_dti_ratio, 4),
            "total_dti_percentage": f"{total_dti_ratio:.1%}",
            "max_allowed_emi": max_allowed_emi,
            "threshold_rule": f"EMI <= {int(max_ratio * 100)}% of income",
            "reason": reason,
        }

    @kernel_function(
        name="calculate_debt_to_income_ratio",
        description="Calculates comprehensive Debt-to-Income (DTI) and financial leverage classification.",
    )
    def calculate_debt_to_income_ratio(
        self,
        monthly_income: Annotated[float, "Verified monthly income."],
        total_monthly_debt: Annotated[float, "Total monthly debt including proposed EMI."],
    ) -> Dict[str, Any]:
        """Tool 2: Computes DTI ratio and financial risk bracket."""
        if monthly_income <= 0:
            return {"dti_ratio": 1.0, "risk_bracket": "CRITICAL", "headroom": 0.0}

        ratio = total_monthly_debt / monthly_income
        headroom = max(0.0, (monthly_income * self.DEFAULT_MAX_TOTAL_DTI) - total_monthly_debt)

        if ratio <= 0.30:
            bracket = "EXCELLENT"
        elif ratio <= 0.40:
            bracket = "HEALTHY"
        elif ratio <= 0.50:
            bracket = "MODERATE"
        else:
            bracket = "HIGH_LEVERAGE"

        return {
            "monthly_income": monthly_income,
            "total_monthly_debt": total_monthly_debt,
            "dti_ratio": round(ratio, 4),
            "dti_percentage": f"{ratio:.1%}",
            "risk_bracket": bracket,
            "monthly_headroom": round(headroom, 2),
        }
