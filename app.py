"""
Local Web Application & Interactive UI for Multi-Agent Loan Underwriting.
Starts a local FastAPI server and automatically opens the user's web browser.
Powered by Semantic Kernel & Local Agent (Qwen 3 via Ollama).
Includes persistent memory, historical tracking, and active defaulters registry
with manual addition and management.
"""
from __future__ import annotations

import os
import sys
import json
import socket
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel

# Ensure project root is on path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agents.underwriting_manager import UnderwritingManager
from models.schemas import LoanApplication, DecisionEnum

app = FastAPI(title="CSE476 Agentic Loan Underwriting System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Manager with Local Qwen Agent configuration
bureau_path = project_root / "data" / "bureau_records.json"
run_log_path = project_root / "run_log.md"

manager = UnderwritingManager(
    annual_interest_rate=10.5,
    bureau_data_path=str(bureau_path) if bureau_path.exists() else None,
    run_log_path=str(run_log_path),
    use_llm=True,
    llm_provider="local",
    local_model_name="qwen3:8b",
    local_endpoint="http://localhost:11434/v1",
)


class UnderwriteRequest(BaseModel):
    applicant_id: str
    applicant_name: str
    monthly_income: Optional[float] = None
    existing_emis: float = 0.0
    requested_amount: Optional[float] = None
    tenure_months: Optional[int] = None
    purpose: Optional[str] = "Personal Loan"
    interest_rate: float = 10.5
    engine: str = "local_qwen"  # "local_qwen" or "deterministic"


class DefaulterCreateRequest(BaseModel):
    applicant_id: str
    applicant_name: Optional[str] = "Registered Defaulter"
    cibil_score: int = 540
    past_defaults: int = 1
    active_loans: int = 0
    late_payments_last_2yrs: int = 0
    credit_remarks: Optional[str] = "Manually reported default in bureau watchlist"


@app.get("/api/scenarios")
async def get_scenarios():
    sample_file = project_root / "data" / "sample_applications.json"
    if sample_file.exists():
        with open(sample_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@app.get("/api/bureau")
async def get_bureau():
    if bureau_path.exists():
        with open(bureau_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@app.get("/api/statistics")
async def get_statistics():
    """Returns aggregated memory statistics (sanctioned, declined, referred, totals)."""
    return manager.get_statistics()


@app.get("/api/history")
async def get_history(limit: int = 100):
    """Returns historical evaluations recorded in memory."""
    return manager.get_history(limit=limit)


@app.get("/api/defaulters")
async def get_defaulters():
    """Returns the registry of defaulting and flagged applicants."""
    return manager.get_defaulters_registry()


@app.post("/api/defaulters")
async def add_defaulter_endpoint(req: DefaulterCreateRequest):
    """Adds a new defaulter to the persistent bureau watchlist."""
    if not req.applicant_id.strip():
        raise HTTPException(status_code=400, detail="Applicant ID is mandatory.")
    
    saved_rec = manager.add_defaulter(req.model_dump())
    return {"status": "SUCCESS", "message": f"Defaulter {req.applicant_id} added successfully.", "record": saved_rec}


@app.delete("/api/defaulters/{applicant_id}")
async def remove_defaulter_endpoint(applicant_id: str):
    """Removes a defaulter from the persistent bureau watchlist."""
    removed = manager.remove_defaulter(applicant_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Defaulter record not found.")
    return {"status": "SUCCESS", "message": f"Defaulter {applicant_id} removed from watchlist."}


@app.post("/api/memory/clear")
async def clear_memory():
    """Clears evaluation history memory."""
    manager.memory_store.clear()
    return {"status": "SUCCESS", "message": "Evaluation memory cleared."}


@app.get("/api/logs")
async def get_logs():
    if run_log_path.exists():
        with open(run_log_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "No run logs available yet."}


@app.post("/api/underwrite")
async def run_underwrite(req: UnderwriteRequest):
    # Configure LLM mode on manager
    manager.annual_interest_rate = req.interest_rate
    manager.use_llm = req.engine == "local_qwen"

    raw_dict = req.model_dump()
    record = manager.evaluate_application(raw_dict)

    # Return serialized output
    return record.model_dump()


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agentic Loan Underwriting System | CSE476 Project</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #0b0f19; color: #f1f5f9; }
    .glass-panel { background: rgba(17, 24, 39, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glow-cyan { box-shadow: 0 0 25px -5px rgba(6, 182, 212, 0.3); }
    .glow-emerald { box-shadow: 0 0 25px -5px rgba(16, 185, 129, 0.35); }
    .glow-rose { box-shadow: 0 0 25px -5px rgba(244, 63, 94, 0.35); }
    .glow-amber { box-shadow: 0 0 25px -5px rgba(245, 158, 11, 0.35); }
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0b0f19; }
    ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
  </style>
</head>
<body class="min-h-screen flex flex-col relative">

  <!-- Top Navbar -->
  <header class="border-b border-slate-800 bg-slate-900/60 sticky top-0 z-50 backdrop-blur-md">
    <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap justify-between items-center gap-4">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
          <i class="fa-solid fa-network-wired text-lg"></i>
        </div>
        <div>
          <h1 class="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            Multi-Agent Loan Underwriting
            <span class="text-xs px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800 font-medium">CSE476 CA2</span>
          </h1>
          <p class="text-xs text-slate-400">Lovely Professional University • Instructor: Rohit Bharti</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button onclick="openDefaulterModal()" class="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-red-600/30 transition cursor-pointer">
          <i class="fa-solid fa-user-plus"></i> Add Defaulter
        </button>
        <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700 text-xs">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span class="text-slate-300">Local Agent:</span>
          <span class="font-semibold text-cyan-400">Qwen 3 (8B) via Ollama</span>
        </div>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-4 py-6 flex-1 w-full flex flex-col gap-6">

    <!-- Top Portfolio Memory & Metrics KPI Bar -->
    <section class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <div class="glass-panel p-3.5 rounded-xl border border-slate-800">
        <p class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Evaluated</p>
        <h3 id="statTotal" class="text-xl font-bold text-white mt-1">0</h3>
        <p class="text-[10px] text-slate-500 mt-0.5">Recorded in Memory</p>
      </div>
      <div class="glass-panel p-3.5 rounded-xl border border-emerald-900/50 bg-emerald-950/10">
        <p class="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">Sanctioned</p>
        <div class="flex items-baseline gap-2 mt-1">
          <h3 id="statSanctioned" class="text-xl font-bold text-emerald-400">0</h3>
          <span id="statSanctionRate" class="text-xs text-emerald-500 font-semibold">(0%)</span>
        </div>
        <p class="text-[10px] text-slate-500 mt-0.5">Approved Loans</p>
      </div>
      <div class="glass-panel p-3.5 rounded-xl border border-rose-900/50 bg-rose-950/10">
        <p class="text-[11px] font-semibold text-rose-400 uppercase tracking-wider">Declined</p>
        <h3 id="statDeclined" class="text-xl font-bold text-rose-400 mt-1">0</h3>
        <p class="text-[10px] text-slate-500 mt-0.5">Affordability/Risk</p>
      </div>
      <div class="glass-panel p-3.5 rounded-xl border border-amber-900/50 bg-amber-950/10">
        <p class="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">Referred</p>
        <h3 id="statReferred" class="text-xl font-bold text-amber-400 mt-1">0</h3>
        <p class="text-[10px] text-slate-500 mt-0.5">Halted for Review</p>
      </div>
      <div class="glass-panel p-3.5 rounded-xl border border-cyan-900/50 bg-cyan-950/10">
        <p class="text-[11px] font-semibold text-cyan-400 uppercase tracking-wider">Sanctioned Volume</p>
        <h3 id="statVolume" class="text-xl font-bold text-cyan-300 mt-1">$0</h3>
        <p class="text-[10px] text-slate-500 mt-0.5">Total Capital Approved</p>
      </div>
      <div class="glass-panel p-3.5 rounded-xl border border-red-900/60 bg-red-950/20 cursor-pointer hover:border-red-600 transition" onclick="switchMemoryTab('defaulters')">
        <div class="flex justify-between items-center">
          <p class="text-[11px] font-semibold text-red-400 uppercase tracking-wider">Defaulters</p>
          <i class="fa-solid fa-arrow-up-right-from-square text-[10px] text-red-400"></i>
        </div>
        <h3 id="statDefaulters" class="text-xl font-bold text-red-400 mt-1">0</h3>
        <p class="text-[10px] text-red-300/80 mt-0.5">Bureau Watchlist (Click to view)</p>
      </div>
    </section>

    <!-- Preset Scenarios Quick Select -->
    <section class="glass-panel rounded-2xl p-4">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-bolt text-amber-400"></i> Benchmark Scenarios (Assignment Rubric)
        </h2>
        <span class="text-xs text-slate-500">Click any card to auto-load application</span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
        <!-- Scenario 1 -->
        <button onclick="loadScenario('scenario_1_sanction')" 
          class="text-left p-3 rounded-xl border border-emerald-900/60 bg-emerald-950/20 hover:bg-emerald-900/30 transition group cursor-pointer">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
              <i class="fa-solid fa-circle-check"></i> Scenario 1
            </span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-300 font-mono">SANCTION</span>
          </div>
          <p class="text-sm font-semibold text-slate-200 group-hover:text-emerald-300 transition">Alice Sharma</p>
          <p class="text-xs text-slate-400 mt-0.5">High Income ($125k) • CIBIL 785 • 13% DTI</p>
        </button>

        <!-- Scenario 2 -->
        <button onclick="loadScenario('scenario_2_decline_affordability')" 
          class="text-left p-3 rounded-xl border border-rose-900/60 bg-rose-950/20 hover:bg-rose-900/30 transition group cursor-pointer">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-bold text-rose-400 flex items-center gap-1.5">
              <i class="fa-solid fa-triangle-exclamation"></i> Scenario 2
            </span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-rose-900/50 text-rose-300 font-mono">COUNTER-OFFER</span>
          </div>
          <p class="text-sm font-semibold text-slate-200 group-hover:text-rose-300 transition">Bob Mehta</p>
          <p class="text-xs text-slate-400 mt-0.5">EMI > 40% Cap • Viable Alternatives</p>
        </button>

        <!-- Scenario 3 -->
        <button onclick="loadScenario('scenario_3_refer_missing_income')" 
          class="text-left p-3 rounded-xl border border-amber-900/60 bg-amber-950/20 hover:bg-amber-900/30 transition group cursor-pointer">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-bold text-amber-400 flex items-center gap-1.5">
              <i class="fa-solid fa-hand"></i> Scenario 3
            </span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/50 text-amber-300 font-mono">REFER (HALT)</span>
          </div>
          <p class="text-sm font-semibold text-slate-200 group-hover:text-amber-300 transition">Charlie Verma</p>
          <p class="text-xs text-slate-400 mt-0.5">Missing Income • Zero Hallucination</p>
        </button>

        <!-- Scenario 4 -->
        <button onclick="loadScenario('scenario_4_decline_credit_risk')" 
          class="text-left p-3 rounded-xl border border-red-950 bg-red-950/30 hover:bg-red-900/40 transition group cursor-pointer">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-bold text-red-400 flex items-center gap-1.5">
              <i class="fa-solid fa-shield-xmark"></i> Scenario 4
            </span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-red-900/50 text-red-300 font-mono">DECLINE</span>
          </div>
          <p class="text-sm font-semibold text-slate-200 group-hover:text-red-300 transition">David Khan</p>
          <p class="text-xs text-slate-400 mt-0.5">CIBIL 590 • 2 Recorded Defaults</p>
        </button>
      </div>
    </section>

    <!-- Main Workspace (2 Columns) -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

      <!-- LEFT: Application Input Form (5 cols) -->
      <div class="lg:col-span-5 flex flex-col gap-4">
        <div class="glass-panel rounded-2xl p-5 border border-slate-800">
          <div class="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
            <h3 class="font-bold text-white flex items-center gap-2">
              <i class="fa-regular fa-file-lines text-cyan-400"></i> Loan Application Form
            </h3>
            <span class="text-xs text-slate-400 font-mono" id="formStateLabel">Input Ready</span>
          </div>

          <form id="loanForm" class="space-y-4" onsubmit="event.preventDefault(); submitUnderwriting();">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-semibold text-slate-400 mb-1">Applicant ID</label>
                <input type="text" id="app_id" required value="APP-101" 
                  class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-cyan-500 focus:outline-none font-mono">
              </div>
              <div>
                <label class="block text-xs font-semibold text-slate-400 mb-1">Applicant Name</label>
                <input type="text" id="app_name" required value="Alice Sharma" 
                  class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-cyan-500 focus:outline-none">
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <div class="flex justify-between items-center mb-1">
                  <label class="text-xs font-semibold text-slate-400">Monthly Net Income ($)</label>
                  <button type="button" onclick="toggleMissingIncome()" class="text-[10px] text-amber-400 hover:underline">
                    Set Missing
                  </button>
                </div>
                <input type="number" step="100" id="monthly_income" value="125000" 
                  class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-cyan-500 focus:outline-none">
              </div>
              <div>
                <label class="block text-xs font-semibold text-slate-400 mb-1">Existing Monthly EMIs ($)</label>
                <input type="number" step="100" id="existing_emis" value="8000" 
                  class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-cyan-500 focus:outline-none">
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-semibold text-slate-400 mb-1">Requested Loan ($)</label>
                <input type="number" step="1000" id="requested_amount" required value="500000" 
                  class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-cyan-500 focus:outline-none font-semibold text-cyan-300">
              </div>
              <div>
                <label class="block text-xs font-semibold text-slate-400 mb-1">Tenure (Months)</label>
                <input type="number" id="tenure_months" required value="36" 
                  class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-cyan-500 focus:outline-none">
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-semibold text-slate-400 mb-1">Interest Rate (% p.a.)</label>
                <input type="number" step="0.1" id="interest_rate" required value="10.5" 
                  class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-cyan-500 focus:outline-none">
              </div>
              <div>
                <label class="block text-xs font-semibold text-slate-400 mb-1">Loan Purpose</label>
                <input type="text" id="purpose" value="Home renovation" 
                  class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-cyan-500 focus:outline-none">
              </div>
            </div>

            <div class="pt-2 border-t border-slate-800">
              <label class="block text-xs font-semibold text-slate-400 mb-2">Synthesis Engine</label>
              <div class="grid grid-cols-2 gap-2">
                <label class="flex items-center gap-2 p-2.5 rounded-lg bg-slate-900 border border-cyan-800/80 cursor-pointer text-xs">
                  <input type="radio" name="engine" value="local_qwen" checked class="text-cyan-500 focus:ring-0">
                  <div>
                    <p class="font-semibold text-white">Local Qwen Agent</p>
                    <p class="text-[10px] text-slate-400">qwen3:8b via Ollama</p>
                  </div>
                </label>
                <label class="flex items-center gap-2 p-2.5 rounded-lg bg-slate-900 border border-slate-800 cursor-pointer text-xs">
                  <input type="radio" name="engine" value="deterministic" class="text-cyan-500 focus:ring-0">
                  <div>
                    <p class="font-semibold text-white">Rule Engine</p>
                    <p class="text-[10px] text-slate-400">Deterministic Template</p>
                  </div>
                </label>
              </div>
            </div>

            <button type="submit" id="submitBtn"
              class="w-full mt-2 py-3 px-4 rounded-xl font-bold text-sm bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white shadow-lg shadow-cyan-600/25 transition flex items-center justify-center gap-2 cursor-pointer">
              <i class="fa-solid fa-play"></i> Run Multi-Agent Underwriting
            </button>
          </form>
        </div>

        <!-- Defaulters Watchlist Quick Box -->
        <div class="glass-panel rounded-2xl p-4 text-xs border border-red-900/40 bg-red-950/10">
          <div class="flex items-center justify-between mb-2 pb-1 border-b border-red-900/30">
            <h4 class="font-bold text-red-300 flex items-center gap-1.5">
              <i class="fa-solid fa-shield-halved text-red-400"></i> Active Defaulters Watchlist
            </h4>
            <button onclick="openDefaulterModal()" class="text-[10px] text-red-400 hover:text-red-200 underline font-semibold flex items-center gap-1">
              <i class="fa-solid fa-plus"></i> Add New
            </button>
          </div>
          <div class="space-y-2 max-h-48 overflow-y-auto pr-1" id="defaulterQuickList">
            Loading watchlist...
          </div>
        </div>
      </div>

      <!-- RIGHT: Multi-Agent Execution & Decision View (7 cols) -->
      <div class="lg:col-span-7 flex flex-col gap-4">

        <!-- Verdict Display Card -->
        <div id="verdictCard" class="glass-panel rounded-2xl p-6 border border-slate-800 transition-all duration-300">
          <div class="flex items-center justify-between pb-4 border-b border-slate-800">
            <div>
              <p class="text-xs uppercase tracking-wider text-slate-400 font-semibold">Underwriting Decision</p>
              <h2 id="decisionBadge" class="text-2xl font-black tracking-tight text-slate-500 flex items-center gap-2 mt-1">
                <i class="fa-solid fa-circle-notch animate-spin text-lg"></i> Awaiting Application
              </h2>
            </div>
            <div class="text-right">
              <span class="text-xs text-slate-400">Timestamp</span>
              <p id="decisionTimestamp" class="text-xs font-mono text-slate-300 mt-0.5">--</p>
            </div>
          </div>

          <!-- Key Underwriting Metrics Grid -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 my-4">
            <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <p class="text-[11px] text-slate-400">Computed EMI</p>
              <p id="resEmi" class="text-base font-bold text-white mt-1">--</p>
              <p class="text-[10px] text-slate-500">Reducing-balance</p>
            </div>
            <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <p class="text-[11px] text-slate-400">Affordability (DTI)</p>
              <p id="resDti" class="text-base font-bold text-white mt-1">--</p>
              <p class="text-[10px] text-slate-500">Cap: 40.0% Income</p>
            </div>
            <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <p class="text-[11px] text-slate-400">Bureau Score</p>
              <p id="resCibil" class="text-base font-bold text-white mt-1">--</p>
              <p id="resRiskTier" class="text-[10px] text-slate-500">Bureau Lookup</p>
            </div>
            <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <p class="text-[11px] text-slate-400">Total Payable</p>
              <p id="resPayable" class="text-base font-bold text-white mt-1">--</p>
              <p id="resInterest" class="text-[10px] text-slate-500">Principal + Interest</p>
            </div>
          </div>

          <!-- Counter-Offer Card (Group of 3 Add-On) -->
          <div id="counterOfferSection" class="hidden my-3 p-4 rounded-xl border border-rose-900/60 bg-rose-950/20">
            <h4 class="text-xs font-bold text-rose-300 uppercase tracking-wider flex items-center gap-2 mb-2">
              <i class="fa-solid fa-handshake-angle"></i> Group-of-3 Add-On: Counter-Offer Proposal
            </h4>
            <div class="grid grid-cols-2 gap-3 text-xs mb-2">
              <div>
                <span class="text-slate-400">Max Affordable Amount (Current Tenure):</span>
                <p id="coMaxAmount" class="font-bold text-emerald-400 text-sm">--</p>
              </div>
              <div>
                <span class="text-slate-400">Extended Tenure Alternative:</span>
                <p id="coExtTenure" class="font-bold text-cyan-400 text-sm">--</p>
              </div>
            </div>
            <p id="coNote" class="text-xs text-slate-300 italic border-t border-rose-900/40 pt-2"></p>
          </div>

          <!-- One-Paragraph Executive Justification -->
          <div class="mt-4">
            <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between mb-2">
              <span><i class="fa-solid fa-quote-left text-cyan-400 mr-1.5"></i> One-Paragraph Underwriting Justification</span>
              <span id="synthesizerBadge" class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">Qwen 3 Synthesizer</span>
            </h4>
            <div class="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 text-slate-200 text-sm leading-relaxed" id="justificationText">
              Submit an application or click any scenario above to see the multi-agent decision and justification trace.
            </div>
          </div>
        </div>

        <!-- Step-by-Step Multi-Agent Execution Trace -->
        <div class="glass-panel rounded-2xl p-5 border border-slate-800">
          <div class="flex items-center justify-between mb-3">
            <h3 class="font-bold text-white text-sm flex items-center gap-2">
              <i class="fa-solid fa-shoe-prints text-cyan-400"></i> Specialist Multi-Agent Execution Trace
            </h3>
            <span class="text-xs text-slate-400" id="traceCount">0 steps logged</span>
          </div>

          <div id="traceContainer" class="space-y-2.5 max-h-56 overflow-y-auto pr-1">
            <p class="text-xs text-slate-500 italic">No agent execution steps executed yet.</p>
          </div>
        </div>

      </div>

    </div>

    <!-- BOTTOM: Persistent Memory & Historical Evaluations Tabbed Table -->
    <section class="glass-panel rounded-2xl p-6 border border-slate-800">
      <div class="flex flex-wrap items-center justify-between gap-4 mb-4 pb-3 border-b border-slate-800">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-purple-500/20 text-purple-400 flex items-center justify-center">
            <i class="fa-solid fa-clock-rotate-left"></i>
          </div>
          <div>
            <h3 class="font-bold text-white text-base">Underwriting Memory & Historical Registry</h3>
            <p class="text-xs text-slate-400">Persistent log of all evaluated loan decisions, approval volumes, and defaulter tracking</p>
          </div>
        </div>

        <!-- Tab Switcher and Actions -->
        <div class="flex items-center gap-2">
          <button onclick="switchMemoryTab('history')" id="tabBtnHistory" 
            class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600 text-white cursor-pointer transition">
            <i class="fa-solid fa-list-check mr-1"></i> Loan History (<span id="historyTabCount">0</span>)
          </button>
          <button onclick="switchMemoryTab('defaulters')" id="tabBtnDefaulters" 
            class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white cursor-pointer transition">
            <i class="fa-solid fa-user-xmark mr-1"></i> Defaulters Watchlist (<span id="defaulterTabCount">0</span>)
          </button>
          <button onclick="openDefaulterModal()" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-500 text-white cursor-pointer transition flex items-center gap-1 ml-1">
            <i class="fa-solid fa-plus"></i> Add Defaulter
          </button>
          <button onclick="refreshMemory()" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs cursor-pointer ml-1" title="Refresh">
            <i class="fa-solid fa-rotate-right"></i>
          </button>
        </div>
      </div>

      <!-- Tab 1: Evaluation History Table -->
      <div id="viewHistory" class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-900/80 text-slate-400 uppercase font-mono text-[10px] border-b border-slate-800">
            <tr>
              <th class="py-2.5 px-3">Log ID</th>
              <th class="py-2.5 px-3">Timestamp</th>
              <th class="py-2.5 px-3">Applicant</th>
              <th class="py-2.5 px-3">Income</th>
              <th class="py-2.5 px-3">Loan Req.</th>
              <th class="py-2.5 px-3">Computed EMI</th>
              <th class="py-2.5 px-3">CIBIL</th>
              <th class="py-2.5 px-3">Decision</th>
              <th class="py-2.5 px-3">Reason / Details</th>
            </tr>
          </thead>
          <tbody id="historyTableBody" class="divide-y divide-slate-800/60 font-mono">
            <tr><td colspan="9" class="py-4 text-center text-slate-500">Loading history records...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- Tab 2: Defaulters Detailed Table -->
      <div id="viewDefaulters" class="hidden overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-red-950/40 text-red-300 uppercase font-mono text-[10px] border-b border-red-900/50">
            <tr>
              <th class="py-2.5 px-3">Applicant ID</th>
              <th class="py-2.5 px-3">Name</th>
              <th class="py-2.5 px-3">Bureau Score</th>
              <th class="py-2.5 px-3">Past Defaults</th>
              <th class="py-2.5 px-3">Active Loans</th>
              <th class="py-2.5 px-3">Late Payments (2Y)</th>
              <th class="py-2.5 px-3">Credit Remarks</th>
              <th class="py-2.5 px-3">Watchlist Status</th>
              <th class="py-2.5 px-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody id="defaultersTableBody" class="divide-y divide-red-900/20 font-mono">
            <tr><td colspan="9" class="py-4 text-center text-slate-500">Loading defaulter records...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

  </main>

  <!-- MODAL: Add Defaulter Manually -->
  <div id="defaulterModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="glass-panel w-full max-w-lg rounded-2xl border border-red-900/70 shadow-2xl p-6 relative">
      <div class="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
        <h3 class="font-bold text-white text-base flex items-center gap-2">
          <span class="w-7 h-7 rounded-lg bg-red-600/20 text-red-400 flex items-center justify-center text-xs">
            <i class="fa-solid fa-user-slash"></i>
          </span>
          Add Defaulter to Bureau Watchlist
        </h3>
        <button onclick="closeDefaulterModal()" class="text-slate-400 hover:text-white p-1">
          <i class="fa-solid fa-xmark text-lg"></i>
        </button>
      </div>

      <form id="defaulterForm" class="space-y-3.5 text-xs" onsubmit="event.preventDefault(); submitDefaulter();">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Applicant ID *</label>
            <input type="text" id="def_app_id" required placeholder="e.g. APP-106" 
              class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-red-500 focus:outline-none font-mono uppercase">
          </div>
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Applicant Full Name *</label>
            <input type="text" id="def_app_name" required placeholder="e.g. Vikram Singh" 
              class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-red-500 focus:outline-none">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block font-semibold text-slate-400 mb-1">CIBIL Bureau Score (300 - 900) *</label>
            <input type="number" id="def_cibil" required min="300" max="900" value="520" 
              class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-red-500 focus:outline-none font-bold text-amber-400">
          </div>
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Past Defaults / Write-Offs Count *</label>
            <input type="number" id="def_past_defaults" required min="1" max="20" value="2" 
              class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-red-500 focus:outline-none font-bold text-red-400">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Active Loans Count</label>
            <input type="number" id="def_active_loans" min="0" value="1" 
              class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-red-500 focus:outline-none">
          </div>
          <div>
            <label class="block font-semibold text-slate-400 mb-1">Late Payments in Last 2 Years</label>
            <input type="number" id="def_late_payments" min="0" value="3" 
              class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm focus:border-red-500 focus:outline-none">
          </div>
        </div>

        <div>
          <label class="block font-semibold text-slate-400 mb-1">Credit Bureau Remarks / Grounds *</label>
          <textarea id="def_remarks" required rows="2" placeholder="e.g. Legal recovery notice issued, settled with loss, NPA account in 2025" 
            class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs focus:border-red-500 focus:outline-none text-slate-200">Wilful default on personal loan; accounts overdue 90+ DPD</textarea>
        </div>

        <div class="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-800">
          <button type="button" onclick="closeDefaulterModal()" 
            class="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold cursor-pointer">
            Cancel
          </button>
          <button type="submit" id="saveDefBtn"
            class="px-5 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold shadow-lg shadow-red-600/30 cursor-pointer flex items-center gap-1.5">
            <i class="fa-solid fa-shield-halved"></i> Save to Defaulter Watchlist
          </button>
        </div>
      </form>
    </div>
  </div>

  <script>
    let scenariosData = {};
    let activeMemoryTab = 'history';

    async function init() {
      try {
        const scResp = await fetch('/api/scenarios');
        scenariosData = await scResp.json();

        await refreshMemory();
      } catch (e) {
        console.error('Init error:', e);
      }
    }

    async function refreshMemory() {
      try {
        // 1. Fetch Stats
        const statsResp = await fetch('/api/statistics');
        const stats = await statsResp.json();

        document.getElementById('statTotal').innerText = stats.total_evaluated;
        document.getElementById('statSanctioned').innerText = stats.sanctioned_count;
        document.getElementById('statSanctionRate').innerText = `(${stats.sanction_rate_percent}%)`;
        document.getElementById('statDeclined').innerText = stats.declined_count;
        document.getElementById('statReferred').innerText = stats.referred_count;
        document.getElementById('statVolume').innerText = `$${(stats.total_sanctioned_amount || 0).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}`;
        document.getElementById('statDefaulters').innerText = stats.evaluated_defaulters_count;

        // 2. Fetch History
        const histResp = await fetch('/api/history');
        const history = await histResp.json();
        document.getElementById('historyTabCount').innerText = history.length;
        renderHistoryTable(history);

        // 3. Fetch Defaulters
        const defResp = await fetch('/api/defaulters');
        const defaulters = await defResp.json();
        document.getElementById('defaulterTabCount').innerText = defaulters.length;
        renderDefaultersTable(defaulters);
        renderDefaulterQuickList(defaulters);

      } catch (err) {
        console.error('Failed to refresh memory:', err);
      }
    }

    function renderHistoryTable(history) {
      const tbody = document.getElementById('historyTableBody');
      if (!history || history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="py-6 text-center text-slate-500 italic">No loan applications recorded in memory yet. Run a scenario above!</td></tr>';
        return;
      }

      let html = '';
      history.forEach(item => {
        const dec = item.decision;
        const badgeCol = dec === 'SANCTION' 
          ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-800' 
          : (dec === 'DECLINE' ? 'bg-rose-900/60 text-rose-300 border border-rose-800' : 'bg-amber-900/60 text-amber-300 border border-amber-800');

        html += `
          <tr class="hover:bg-slate-900/60 transition">
            <td class="py-2.5 px-3 text-cyan-400 font-bold">${item.id}</td>
            <td class="py-2.5 px-3 text-slate-400 text-[11px]">${item.timestamp}</td>
            <td class="py-2.5 px-3 font-semibold text-slate-200">${item.applicant_name} <span class="text-slate-500 text-[10px]">(${item.applicant_id})</span></td>
            <td class="py-2.5 px-3 text-slate-300">${item.monthly_income ? '$' + item.monthly_income.toLocaleString() : '<span class=\"text-amber-400\">MISSING</span>'}</td>
            <td class="py-2.5 px-3 text-cyan-300 font-bold">${item.requested_amount ? '$' + item.requested_amount.toLocaleString() : 'N/A'}</td>
            <td class="py-2.5 px-3 text-slate-300">${item.computed_monthly_emi ? '$' + item.computed_monthly_emi.toLocaleString(undefined, {minimumFractionDigits: 2}) : 'N/A'}</td>
            <td class="py-2.5 px-3 text-slate-300 font-bold">${item.cibil_score || 'N/A'}</td>
            <td class="py-2.5 px-3">
              <span class="px-2 py-0.5 rounded text-[10px] font-bold ${badgeCol}">${dec}</span>
            </td>
            <td class="py-2.5 px-3 text-slate-400 text-[11px] max-w-xs truncate" title="${item.decision_reason}">
              ${item.decision_reason}
              ${item.counter_offer_proposed ? ' <span class=\"text-cyan-400 font-semibold\">[Counter-Offer]</span>' : ''}
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    }

    function renderDefaultersTable(defaulters) {
      const tbody = document.getElementById('defaultersTableBody');
      if (!defaulters || defaulters.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="py-6 text-center text-slate-500 italic">No defaulters currently registered in memory. Click \"+ Add Defaulter\" to register one!</td></tr>';
        return;
      }

      let html = '';
      defaulters.forEach(d => {
        html += `
          <tr class="hover:bg-red-950/30 transition">
            <td class="py-2.5 px-3 font-bold text-red-400">${d.applicant_id}</td>
            <td class="py-2.5 px-3 font-semibold text-slate-200">${d.applicant_name}</td>
            <td class="py-2.5 px-3 font-bold text-amber-400">${d.cibil_score}</td>
            <td class="py-2.5 px-3 text-rose-400 font-bold">${d.past_defaults} write-offs</td>
            <td class="py-2.5 px-3 text-slate-300">${d.active_loans}</td>
            <td class="py-2.5 px-3 text-slate-400">${d.late_payments_last_2yrs}</td>
            <td class="py-2.5 px-3 text-slate-300 max-w-xs truncate" title="${d.credit_remarks}">${d.credit_remarks}</td>
            <td class="py-2.5 px-3">
              <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-400 border border-rose-800">${d.status}</span>
            </td>
            <td class="py-2.5 px-3 text-center flex items-center justify-center gap-2">
              <button onclick="loadDefaulterToForm('${d.applicant_id}', '${d.applicant_name.replace(/'/g, "\\'")}')" 
                class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 text-[10px] font-semibold cursor-pointer" title="Test Application in Underwriting Form">
                <i class="fa-solid fa-play mr-1"></i> Test
              </button>
              <button onclick="deleteDefaulter('${d.applicant_id}')" 
                class="p-1 rounded bg-slate-800 hover:bg-rose-900 text-rose-400 hover:text-white text-[10px] cursor-pointer" title="Remove Defaulter">
                <i class="fa-solid fa-trash"></i>
              </button>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    }

    function renderDefaulterQuickList(defaulters) {
      const box = document.getElementById('defaulterQuickList');
      if (!defaulters || defaulters.length === 0) {
        box.innerHTML = '<p class=\"text-slate-500 italic\">Zero default records on file. Click Add to report one.</p>';
        return;
      }

      let html = '';
      defaulters.forEach(d => {
        html += `
          <div class="p-2 rounded-lg bg-red-950/40 border border-red-900/50 flex justify-between items-center text-[11px]">
            <div>
              <p class="font-bold text-red-300">${d.applicant_name} <span class="font-mono text-slate-400">(${d.applicant_id})</span></p>
              <p class="text-[10px] text-slate-400">CIBIL: ${d.cibil_score} • ${d.credit_remarks}</p>
            </div>
            <div class="flex items-center gap-1.5 shrink-0">
              <span class="px-2 py-0.5 rounded bg-red-900/80 text-red-200 font-bold text-[10px]">
                ${d.past_defaults} Defaults
              </span>
              <button onclick="loadDefaulterToForm('${d.applicant_id}', '${d.applicant_name.replace(/'/g, "\\'")}')" 
                class="p-1 text-cyan-400 hover:text-cyan-200" title="Test in Loan Form">
                <i class="fa-solid fa-play text-[10px]"></i>
              </button>
            </div>
          </div>
        `;
      });
      box.innerHTML = html;
    }

    function switchMemoryTab(tab) {
      activeMemoryTab = tab;
      const btnHist = document.getElementById('tabBtnHistory');
      const btnDef = document.getElementById('tabBtnDefaulters');
      const viewHist = document.getElementById('viewHistory');
      const viewDef = document.getElementById('viewDefaulters');

      if (tab === 'history') {
        btnHist.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600 text-white cursor-pointer transition";
        btnDef.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white cursor-pointer transition";
        viewHist.classList.remove('hidden');
        viewDef.classList.add('hidden');
      } else {
        btnDef.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-700 text-white cursor-pointer transition";
        btnHist.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white cursor-pointer transition";
        viewDef.classList.remove('hidden');
        viewHist.classList.add('hidden');
      }
    }

    function openDefaulterModal() {
      document.getElementById('defaulterModal').classList.remove('hidden');
      document.getElementById('def_app_id').focus();
    }

    function closeDefaulterModal() {
      document.getElementById('defaulterModal').classList.add('hidden');
    }

    async function submitDefaulter() {
      const btn = document.getElementById('saveDefBtn');
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner animate-spin"></i> Saving...';

      const payload = {
        applicant_id: document.getElementById('def_app_id').value.trim(),
        applicant_name: document.getElementById('def_app_name').value.trim(),
        cibil_score: parseInt(document.getElementById('def_cibil').value),
        past_defaults: parseInt(document.getElementById('def_past_defaults').value),
        active_loans: parseInt(document.getElementById('def_active_loans').value) || 0,
        late_payments_last_2yrs: parseInt(document.getElementById('def_late_payments').value) || 0,
        credit_remarks: document.getElementById('def_remarks').value.trim()
      };

      try {
        const resp = await fetch('/api/defaulters', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const res = await resp.json();
        if (resp.ok) {
          alert(`✅ Defaulter ${payload.applicant_name} (${payload.applicant_id}) added to bureau watchlist!`);
          closeDefaulterModal();
          document.getElementById('defaulterForm').reset();
          await refreshMemory();
          switchMemoryTab('defaulters');
        } else {
          alert('Error: ' + res.detail);
        }
      } catch (err) {
        alert('Failed to save defaulter: ' + err);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-shield-halved"></i> Save to Defaulter Watchlist';
      }
    }

    async function deleteDefaulter(appId) {
      if (!confirm(`Are you sure you want to remove ${appId} from the Defaulters Watchlist?`)) {
        return;
      }
      try {
        const resp = await fetch(`/api/defaulters/${appId}`, { method: 'DELETE' });
        if (resp.ok) {
          await refreshMemory();
        } else {
          alert('Failed to remove defaulter.');
        }
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    function loadDefaulterToForm(appId, appName) {
      document.getElementById('app_id').value = appId;
      document.getElementById('app_name').value = appName;
      document.getElementById('monthly_income').value = 85000;
      document.getElementById('existing_emis').value = 4000;
      document.getElementById('requested_amount').value = 250000;
      document.getElementById('tenure_months').value = 24;
      document.getElementById('purpose').value = 'Personal loan';
      
      window.scrollTo({ top: 0, behavior: 'smooth' });
      document.getElementById('formStateLabel').innerText = `Loaded Defaulter: ${appId}`;
    }

    function toggleMissingIncome() {
      const incField = document.getElementById('monthly_income');
      if (incField.value) {
        incField.value = '';
        incField.placeholder = '[MISSING / NOT PROVIDED]';
      } else {
        incField.value = 75000;
        incField.placeholder = '';
      }
    }

    function loadScenario(key) {
      const data = scenariosData[key];
      if (!data) return;

      document.getElementById('app_id').value = data.applicant_id;
      document.getElementById('app_name').value = data.applicant_name;
      document.getElementById('monthly_income').value = data.monthly_income !== null ? data.monthly_income : '';
      document.getElementById('monthly_income').placeholder = data.monthly_income === null ? '[MISSING / NOT PROVIDED]' : '';
      document.getElementById('existing_emis').value = data.existing_emis || 0;
      document.getElementById('requested_amount').value = data.requested_amount || '';
      document.getElementById('tenure_months').value = data.tenure_months || 24;
      document.getElementById('purpose').value = data.purpose || 'Personal';

      submitUnderwriting();
    }

    async function submitUnderwriting() {
      const submitBtn = document.getElementById('submitBtn');
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa-solid fa-spinner animate-spin"></i> Specialists Evaluating...';

      const incomeVal = document.getElementById('monthly_income').value;
      const reqAmountVal = document.getElementById('requested_amount').value;
      const tenureVal = document.getElementById('tenure_months').value;

      const payload = {
        applicant_id: document.getElementById('app_id').value,
        applicant_name: document.getElementById('app_name').value,
        monthly_income: incomeVal !== '' ? parseFloat(incomeVal) : null,
        existing_emis: parseFloat(document.getElementById('existing_emis').value) || 0,
        requested_amount: reqAmountVal !== '' ? parseFloat(reqAmountVal) : null,
        tenure_months: tenureVal !== '' ? parseInt(tenureVal) : null,
        purpose: document.getElementById('purpose').value,
        interest_rate: parseFloat(document.getElementById('interest_rate').value) || 10.5,
        engine: document.querySelector('input[name="engine"]:checked').value
      };

      try {
        const resp = await fetch('/api/underwrite', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await resp.json();
        renderResult(result);
        await refreshMemory();
      } catch (err) {
        alert('Execution failed: ' + err);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run Multi-Agent Underwriting';
      }
    }

    function renderResult(data) {
      const dec = data.decision || 'UNKNOWN';
      const badge = document.getElementById('decisionBadge');
      const card = document.getElementById('verdictCard');

      card.className = "glass-panel rounded-2xl p-6 border transition-all duration-300";

      if (dec === 'SANCTION') {
        badge.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400"></i> <span class="text-emerald-400">SANCTIONED</span>';
        card.classList.add('border-emerald-600', 'glow-emerald');
      } else if (dec === 'DECLINE') {
        badge.innerHTML = '<i class="fa-solid fa-circle-xmark text-rose-500"></i> <span class="text-rose-500">DECLINED</span>';
        card.classList.add('border-rose-600', 'glow-rose');
      } else {
        badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-amber-400"></i> <span class="text-amber-400">REFERRED (HALTED)</span>';
        card.classList.add('border-amber-600', 'glow-amber');
      }

      document.getElementById('decisionTimestamp').innerText = new Date().toLocaleTimeString();

      // Metrics
      document.getElementById('resEmi').innerText = data.computed_monthly_emi ? `$${data.computed_monthly_emi.toLocaleString(undefined, {minimumFractionDigits: 2})}` : 'N/A';
      document.getElementById('resDti').innerText = data.emi_to_income_ratio ? `${(data.emi_to_income_ratio * 100).toFixed(1)}%` : 'N/A';
      document.getElementById('resCibil').innerText = data.bureau_profile ? `${data.bureau_profile.cibil_score}` : 'N/A';
      document.getElementById('resRiskTier').innerText = data.credit_risk_level ? `Tier: ${data.credit_risk_level}` : 'Bureau Pending';
      document.getElementById('resPayable').innerText = data.total_payable_amount ? `$${data.total_payable_amount.toLocaleString(undefined, {minimumFractionDigits: 2})}` : 'N/A';
      document.getElementById('resInterest').innerText = data.total_interest ? `Interest: $${data.total_interest.toLocaleString(undefined, {minimumFractionDigits: 2})}` : 'Principal Only';

      // Counter-Offer
      const coSection = document.getElementById('counterOfferSection');
      if (data.counter_offer && data.counter_offer.eligible_for_counter_offer) {
        coSection.classList.remove('hidden');
        document.getElementById('coMaxAmount').innerText = `$${data.counter_offer.max_eligible_loan_amount.toLocaleString(undefined, {minimumFractionDigits: 2})} (EMI: $${data.counter_offer.max_amount_emi.toLocaleString(undefined, {minimumFractionDigits: 2})})`;
        document.getElementById('coExtTenure').innerText = data.counter_offer.extended_tenure_months ? `${data.counter_offer.extended_tenure_months} Months (New EMI: $${data.counter_offer.extended_tenure_emi.toLocaleString(undefined, {minimumFractionDigits: 2})})` : 'Exceeds 84-month ceiling';
        document.getElementById('coNote').innerText = data.counter_offer.recommendation_note;
      } else {
        coSection.classList.add('hidden');
      }

      // Justification
      document.getElementById('justificationText').innerText = data.one_paragraph_justification || data.decision_reason;

      // Multi-Agent Trace
      const traceContainer = document.getElementById('traceContainer');
      const traces = data.agent_trace || [];
      document.getElementById('traceCount').innerText = `${traces.length} steps logged`;

      let traceHtml = '';
      traces.forEach((t, i) => {
        const isPass = t.status === 'SUCCESS' || t.status === 'PASS';
        const isInit = t.status === 'INITIALIZED';
        const icon = isPass ? 'fa-check text-emerald-400' : (isInit ? 'fa-play text-cyan-400' : 'fa-xmark text-rose-400');
        const borderCol = isPass ? 'border-emerald-950 bg-emerald-950/20' : (isInit ? 'border-cyan-950 bg-cyan-950/20' : 'border-rose-950 bg-rose-950/20');

        traceHtml += `
          <div class="p-2.5 rounded-xl border ${borderCol} flex items-start gap-3 text-xs">
            <span class="w-5 h-5 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center shrink-0 mt-0.5">
              <i class="fa-solid ${icon} text-[10px]"></i>
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between">
                <span class="font-bold text-slate-200">${t.agent_name}</span>
                <span class="text-[10px] font-mono text-slate-400">${t.status}</span>
              </div>
              <p class="text-[11px] text-cyan-300 font-mono mt-0.5">Action: ${t.action}</p>
              <p class="text-[10px] text-slate-500 font-mono truncate">Tool: ${t.tool_used}</p>
            </div>
          </div>
        `;
      });
      traceContainer.innerHTML = traceHtml;
    }

    init();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


def find_free_port(start_port: int = 8000, max_attempts: int = 20) -> int:
    """Finds an available TCP port starting from start_port."""
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start_port


def main():
    port = find_free_port(8000)
    url = f"http://127.0.0.1:{port}"

    print("=" * 80)
    print("  CSE476 CA2: MULTI-AGENT LOAN UNDERWRITING SYSTEM")
    print(f"  Starting local server at: {url}")
    print("  Persistent Memory: Active (underwriting_history.json)")
    print("  Tracking: Sanctioned / Declined / Defaulters Watchlist")
    print("  Powered by Semantic Kernel & Local Agent (Qwen 3 via Ollama)")
    print("=" * 80)

    # Open browser automatically after 1.2 seconds
    def open_browser():
        time.sleep(1.2)
        print(f"--> Opening default web browser to: {url}")
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    # Launch server
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
