"""
EMI Computation deterministic tools.
Implements reducing-balance EMI formula as a deterministic tool (not the model).
"""
from __future__ import annotations

import math
from typing import Annotated, Any, Dict, List
from semantic_kernel.functions import kernel_function


class EMITools:
    """EMI Computation Plugin for Semantic Kernel."""

    @kernel_function(
        name="compute_reducing_balance_emi",
        description="Deterministically calculates monthly reducing-balance EMI given principal, annual rate, and tenure.",
    )
    def compute_reducing_balance_emi(
        self,
        principal: Annotated[float, "Principal loan amount requested."],
        annual_rate_percent: Annotated[float, "Annual interest rate as percentage (e.g., 10.5)."],
        tenure_months: Annotated[int, "Loan tenure in months."],
    ) -> Dict[str, Any]:
        """
        Tool 1: Deterministic Reducing-Balance EMI calculation.
        Formula: E = [P * r * (1+r)^n] / [(1+r)^n - 1]
        where r = annual_rate / 12 / 100
        """
        if principal <= 0 or tenure_months <= 0:
            return {
                "monthly_emi": 0.0,
                "total_payable": 0.0,
                "total_interest": 0.0,
                "error": "Principal and tenure must be positive numbers.",
            }

        monthly_rate = (annual_rate_percent / 100.0) / 12.0
        
        if monthly_rate == 0.0:
            emi = principal / tenure_months
        else:
            factor = math.pow(1.0 + monthly_rate, tenure_months)
            emi = (principal * monthly_rate * factor) / (factor - 1.0)

        monthly_emi = round(emi, 2)
        total_payable = round(monthly_emi * tenure_months, 2)
        total_interest = round(total_payable - principal, 2)

        return {
            "principal": principal,
            "annual_rate_percent": annual_rate_percent,
            "tenure_months": tenure_months,
            "monthly_emi": monthly_emi,
            "total_payable": total_payable,
            "total_interest": total_interest,
            "calculation_method": "deterministic_reducing_balance",
        }

    @kernel_function(
        name="generate_amortization_schedule",
        description="Generates an amortization schedule breakdown showing principal and interest split over tenure.",
    )
    def generate_amortization_schedule(
        self,
        principal: Annotated[float, "Principal loan amount."],
        annual_rate_percent: Annotated[float, "Annual interest rate in percentage."],
        tenure_months: Annotated[int, "Loan tenure in months."],
    ) -> Dict[str, Any]:
        """Tool 2: Generates month-by-month amortization schedule with principal and interest breakdown."""
        calc = self.compute_reducing_balance_emi(principal, annual_rate_percent, tenure_months)
        monthly_emi = calc["monthly_emi"]
        monthly_rate = (annual_rate_percent / 100.0) / 12.0

        schedule: List[Dict[str, Any]] = []
        balance = principal

        for month in range(1, tenure_months + 1):
            interest = round(balance * monthly_rate, 2)
            principal_paid = round(monthly_emi - interest, 2)
            balance = max(0.0, round(balance - principal_paid, 2))

            schedule.append({
                "month": month,
                "emi": monthly_emi,
                "principal_paid": principal_paid,
                "interest_paid": interest,
                "ending_balance": balance,
            })
            if balance <= 0:
                break

        return {
            "summary": {
                "principal": principal,
                "tenure_months": tenure_months,
                "monthly_emi": monthly_emi,
                "first_month_interest": schedule[0]["interest_paid"] if schedule else 0.0,
                "last_month_balance": schedule[-1]["ending_balance"] if schedule else 0.0,
            },
            "schedule": schedule,
        }
