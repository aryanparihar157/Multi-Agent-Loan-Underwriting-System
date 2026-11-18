"""Generates architecture diagram for CSE476 CA2 Project 2."""
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def generate_diagram():
    fig, ax = plt.subplots(figsize=(15, 10), dpi=300)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 10)
    ax.axis("off")

    # Title
    ax.text(7.5, 9.6, "CSE476 CA2: Multi-Agent Loan Underwriting System", 
            ha="center", va="center", fontsize=18, fontweight="bold", color="#1E293B")
    ax.text(7.5, 9.2, "Architecture: Manager-Worker Delegation | Framework: Semantic Kernel", 
            ha="center", va="center", fontsize=12, fontstyle="italic", color="#475569")

    # 1. Left Box: Loan Application Input
    input_box = patches.FancyBboxPatch((0.5, 5.5), 2.8, 2.5, boxstyle="round,pad=0.2",
                                       fc="#EFF6FF", ec="#3B82F6", lw=2)
    ax.add_patch(input_box)
    ax.text(1.9, 7.6, "Application Input", ha="center", va="center", fontsize=12, fontweight="bold", color="#1D4ED8")
    ax.text(1.9, 6.7, "• Applicant ID\n• Monthly Income\n• Existing EMIs\n• Requested Loan\n• Tenure (Months)", 
            ha="center", va="center", fontsize=9.5, color="#1E293B")

    # 2. Central Manager Agent
    mgr_box = patches.FancyBboxPatch((4.2, 5.2), 3.4, 3.0, boxstyle="round,pad=0.2",
                                     fc="#FDF2F8", ec="#DB2777", lw=2.5)
    ax.add_patch(mgr_box)
    ax.text(5.9, 7.8, "Underwriting Manager", ha="center", va="center", fontsize=13, fontweight="bold", color="#9D174D")
    ax.text(5.9, 7.3, "(Coordinator Agent)", ha="center", va="center", fontsize=10, fontstyle="italic", color="#BE185D")
    ax.text(5.9, 6.2, "• Manages Delegation Flow\n• Owns In-Memory Blackboard\n• Enforces Policy Gates\n• Halts on Missing Income\n• Synthesizes Justification", 
            ha="center", va="center", fontsize=9.5, color="#374151")

    # Arrow Input -> Manager
    ax.annotate("", xy=(4.2, 6.7), xytext=(3.3, 6.7),
                arrowprops=dict(arrowstyle="->", lw=2, color="#3B82F6"))

    # 3. In-Memory Blackboard (Shared State)
    bb_box = patches.FancyBboxPatch((4.2, 3.2), 3.4, 1.3, boxstyle="round,pad=0.15",
                                    fc="#F8FAFC", ec="#64748B", lw=1.5, ls="--")
    ax.add_patch(bb_box)
    ax.text(5.9, 4.1, "Shared In-Memory State", ha="center", va="center", fontsize=10.5, fontweight="bold", color="#334155")
    ax.text(5.9, 3.6, "SharedUnderwritingRecord\n(Audit Trail, EMIs, Scores, Ratios)", 
            ha="center", va="center", fontsize=8.5, color="#64748B")
    ax.annotate("", xy=(5.9, 5.2), xytext=(5.9, 4.5),
                arrowprops=dict(arrowstyle="<->", lw=1.5, color="#64748B"))

    # 4. Specialist Worker Agents Column (Right Side)
    specialists = [
        ("Document Agent", "#FEF3C7", "#D97706", "#B45309", 
         "Tools:\n• validate_application_completeness()\n• extract_financial_fields()", 7.8),
        ("EMI Computation Agent", "#ECFDF5", "#059669", "#047857", 
         "Tools (Deterministic):\n• compute_reducing_balance_emi()\n• generate_amortization_schedule()", 6.0),
        ("Credit-History Agent", "#F5F3FF", "#7C3AED", "#6D28D9", 
         "Tools (In-Memory Bureau):\n• query_bureau_records()\n• assess_credit_risk()", 4.2),
        ("Affordability Agent", "#FFF1F2", "#E11D48", "#BE123C", 
         "Tools (40% Rule & DTI):\n• check_affordability_rule()\n• calculate_debt_to_income_ratio()", 2.4),
        ("Counter-Offer Worker", "#F0FDF4", "#16A34A", "#15803D", 
         "Tools (Group-of-3 Add-On):\n• calculate_max_eligible_loan_amount()\n• propose_extended_tenure_option()", 0.6),
    ]

    for name, bg, border, title_c, tools_text, y in specialists:
        s_box = patches.FancyBboxPatch((8.8, y), 3.6, 1.4, boxstyle="round,pad=0.15",
                                       fc=bg, ec=border, lw=1.8)
        ax.add_patch(s_box)
        ax.text(10.6, y + 1.1, name, ha="center", va="center", fontsize=10.5, fontweight="bold", color=title_c)
        ax.text(10.6, y + 0.5, tools_text, ha="center", va="center", fontsize=8, color="#1F2937")

        # Connection line from Manager to Specialist
        ax.annotate("", xy=(8.8, y + 0.7), xytext=(7.6, 6.7),
                    arrowprops=dict(arrowstyle="->", lw=1.3, color=border, connectionstyle="arc3,rad=-0.1"))

    # 5. Output / Decision Badges (Bottom Left)
    out_y = 1.0
    dec_box = patches.FancyBboxPatch((0.5, 0.4), 6.8, 2.2, boxstyle="round,pad=0.2",
                                     fc="#FAFAFA", ec="#94A3B8", lw=1.5)
    ax.add_patch(dec_box)
    ax.text(3.9, 2.2, "Underwriting System Outputs & Decision Gates", ha="center", va="center", 
            fontsize=11, fontweight="bold", color="#1E293B")

    # Sanction Badge
    s_patch = patches.FancyBboxPatch((0.8, 0.7), 1.8, 1.1, boxstyle="round,pad=0.1", fc="#DCFCE7", ec="#16A34A", lw=1.5)
    ax.add_patch(s_patch)
    ax.text(1.7, 1.5, "SANCTION", ha="center", va="center", fontsize=10, fontweight="bold", color="#15803D")
    ax.text(1.7, 1.0, "All rules passed\nEMI <= 40% income", ha="center", va="center", fontsize=7.5, color="#166534")

    # Decline Badge
    d_patch = patches.FancyBboxPatch((2.9, 0.7), 2.0, 1.1, boxstyle="round,pad=0.1", fc="#FEE2E2", ec="#DC2626", lw=1.5)
    ax.add_patch(d_patch)
    ax.text(3.9, 1.5, "DECLINE", ha="center", va="center", fontsize=10, fontweight="bold", color="#B91C1C")
    ax.text(3.9, 1.0, "EMI > 40% or Red Flags\n+ Counter-Offer Details", ha="center", va="center", fontsize=7.5, color="#991B1B")

    # Refer Badge
    r_patch = patches.FancyBboxPatch((5.2, 0.7), 1.8, 1.1, boxstyle="round,pad=0.1", fc="#FEF9C3", ec="#CA8A04", lw=1.5)
    ax.add_patch(r_patch)
    ax.text(6.1, 1.5, "REFER", ha="center", va="center", fontsize=10, fontweight="bold", color="#A16207")
    ax.text(6.1, 1.0, "Missing Income / Docs\nHalts Immediately", ha="center", va="center", fontsize=7.5, color="#854D0E")

    # Arrow Manager -> Decision Box
    ax.annotate("", xy=(3.9, 2.6), xytext=(5.0, 5.2),
                arrowprops=dict(arrowstyle="->", lw=2, color="#475569"))

    plt.tight_layout()
    plt.savefig("f:/Agenetic-AI/docs/architecture_diagram.png", dpi=300, bbox_inches="tight")
    print("Architecture diagram generated at: f:/Agenetic-AI/docs/architecture_diagram.png")

if __name__ == "__main__":
    generate_diagram()
