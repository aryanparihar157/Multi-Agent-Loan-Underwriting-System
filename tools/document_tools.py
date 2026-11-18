"""
Document processing and validation tools.
Calls real Python functions with @kernel_function decoration for Semantic Kernel compatibility.
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List
from semantic_kernel.functions import kernel_function


class DocumentTools:
    """Document Extraction and Validation Plugin for Semantic Kernel."""

    MANDATORY_FIELDS = [
        "applicant_id",
        "applicant_name",
        "monthly_income",
        "requested_amount",
        "tenure_months",
    ]

    @kernel_function(
        name="validate_application_completeness",
        description="Validates that all mandatory fields are present and checks for missing income.",
    )
    def validate_application_completeness(
        self,
        application_data: Annotated[Dict[str, Any], "The raw loan application dictionary."],
    ) -> Dict[str, Any]:
        """
        Tool 1: Verifies mandatory fields.
        Per CA2 requirements: Halts and refers when income is missing rather than assuming it.
        """
        missing: List[str] = []
        for field in self.MANDATORY_FIELDS:
            val = application_data.get(field)
            if val is None or val == "":
                missing.append(field)

        # Check explicit income validity
        income_missing = "monthly_income" in missing or (
            application_data.get("monthly_income") is not None and application_data["monthly_income"] <= 0
        )

        return {
            "is_complete": len(missing) == 0 and not income_missing,
            "missing_fields": missing,
            "income_missing": income_missing,
            "status": "PASS" if (len(missing) == 0 and not income_missing) else "FAIL",
            "message": (
                "Application documents complete."
                if (len(missing) == 0 and not income_missing)
                else f"Mandatory fields missing: {', '.join(missing) if missing else 'Invalid income value'}"
            ),
        }

    @kernel_function(
        name="extract_financial_fields",
        description="Extracts normalized monthly income, existing EMIs, requested amount, and tenure.",
    )
    def extract_financial_fields(
        self,
        application_data: Annotated[Dict[str, Any], "The raw loan application dictionary."],
    ) -> Dict[str, Any]:
        """Tool 2: Extracts financial attributes into structured normalized floats."""
        raw_income = application_data.get("monthly_income")
        monthly_income = float(raw_income) if raw_income is not None else None

        raw_existing = application_data.get("existing_emis", 0.0)
        existing_emis = float(raw_existing) if raw_existing is not None else 0.0

        raw_amount = application_data.get("requested_amount")
        requested_amount = float(raw_amount) if raw_amount is not None else None

        raw_tenure = application_data.get("tenure_months")
        tenure_months = int(raw_tenure) if raw_tenure is not None else None

        return {
            "applicant_id": str(application_data.get("applicant_id", "")),
            "applicant_name": str(application_data.get("applicant_name", "")),
            "monthly_income": monthly_income,
            "existing_emis": existing_emis,
            "requested_amount": requested_amount,
            "tenure_months": tenure_months,
            "net_disposable_income": (monthly_income - existing_emis) if monthly_income is not None else None,
            "extraction_success": monthly_income is not None and requested_amount is not None and tenure_months is not None,
        }
