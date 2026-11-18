"""
Counter-Offer Tools (Group-of-3 Add-on Requirement).
If requested loan amount fails affordability, deterministically computes:
1. The largest loan amount that passes the 40% income cap under current tenure.
2. The longest viable tenure (up to 84 months) that makes the requested loan amount affordable.
"""
from __future__ import annotations

import math
from typing import Annotated, Any, Dict
from semantic_kernel.functions import kernel_function


class CounterOfferTools:
    """Counter-Offer Plugin for Semantic Kernel."""

    @kernel_function(
        name="calculate_max_eligible_loan_amount",
        description="Calculates the maximum loan principal allowed such that EMI is exactly within 40% of net income.",
    )
    def calculate_max_eligible_loan_amount(
        self,
        monthly_income: Annotated[float, "Verified monthly net income."],
        existing_emis: Annotated[float, "Existing monthly EMI commitments."],
        annual_rate_percent: Annotated[float, "Annual interest rate in percentage."],
        tenure_months: Annotated[int, "Desired loan tenure in months."],
        max_ratio: Annotated[float, "Max allowed EMI ratio, default 0.40."] = 0.40,
    ) -> Dict[str, Any]:
        """
        Tool 1: Inverts the reducing-balance EMI formula to solve for maximum Principal:
        P = [EMI * ((1+r)^n - 1)] / [r * (1+r)^n]
        where target EMI = monthly_income * max_ratio.
        """
        if monthly_income <= 0 or tenure_months <= 0:
            return {"max_loan_amount": 0.0, "target_emi": 0.0, "is_viable": False}

        target_emi = round(monthly_income * max_ratio, 2)
        monthly_rate = (annual_rate_percent / 100.0) / 12.0

        if monthly_rate == 0.0:
            max_principal = target_emi * tenure_months
        else:
            factor = math.pow(1.0 + monthly_rate, tenure_months)
            max_principal = (target_emi * (factor - 1.0)) / (monthly_rate * factor)

        max_principal = round(max_principal, 2)

        return {
            "monthly_income": monthly_income,
            "target_emi": target_emi,
            "annual_rate_percent": annual_rate_percent,
            "tenure_months": tenure_months,
            "max_eligible_loan_amount": max_principal,
            "is_viable": max_principal > 0.0,
            "summary": (
                f"Under tenure of {tenure_months} months, maximum affordable loan amount "
                f"is ${max_principal:,.2f} with an EMI of ${target_emi:,.2f} (40% income cap)."
            ),
        }

    @kernel_function(
        name="propose_extended_tenure_option",
        description="Calculates the longest tenure (up to 84 months) that reduces the EMI under 40% income cap.",
    )
    def propose_extended_tenure_option(
        self,
        requested_amount: Annotated[float, "Requested principal loan amount."],
        monthly_income: Annotated[float, "Verified monthly net income."],
        existing_emis: Annotated[float, "Existing monthly commitments."],
        annual_rate_percent: Annotated[float, "Annual interest rate in percentage."],
        current_tenure: Annotated[int, "Current tenure in months."],
        max_tenure_ceiling: Annotated[int, "Maximum allowed extension ceiling, default 84 months."] = 84,
        max_ratio: Annotated[float, "Max allowed EMI ratio, default 0.40."] = 0.40,
    ) -> Dict[str, Any]:
        """
        Tool 2: Iterates through tenures up to max ceiling to find smallest tenure that passes affordability.
        """
        target_max_emi = monthly_income * max_ratio
        monthly_rate = (annual_rate_percent / 100.0) / 12.0

        found_tenure = None
        resulting_emi = None

        for test_tenure in range(current_tenure + 6, max_tenure_ceiling + 1, 6):
            factor = math.pow(1.0 + monthly_rate, test_tenure)
            emi = (requested_amount * monthly_rate * factor) / (factor - 1.0)
            if emi <= target_max_emi:
                found_tenure = test_tenure
                resulting_emi = round(emi, 2)
                break

        if found_tenure is not None:
            return {
                "viable_tenure_found": True,
                "requested_amount": requested_amount,
                "original_tenure": current_tenure,
                "extended_tenure_months": found_tenure,
                "new_monthly_emi": resulting_emi,
                "target_max_emi": round(target_max_emi, 2),
                "summary": (
                    f"Extending tenure from {current_tenure} to {found_tenure} months lowers monthly EMI "
                    f"to ${resulting_emi:,.2f}, fitting within the 40% income cap (${target_max_emi:,.2f})."
                ),
            }

        return {
            "viable_tenure_found": False,
            "requested_amount": requested_amount,
            "original_tenure": current_tenure,
            "max_tested_tenure": max_tenure_ceiling,
            "target_max_emi": round(target_max_emi, 2),
            "summary": (
                f"Even extending tenure to {max_tenure_ceiling} months is insufficient to bring the requested "
                f"amount (${requested_amount:,.2f}) under the 40% income cap."
            ),
        }
