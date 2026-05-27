# Claude Code Usage in AuditPilot

> AuditPilot was built using **Claude Code** via UiPath for Coding Agents.
> This document details exactly how Claude Code was used across the project —
> from scaffolding to agent logic to workflow generation.

---

## Why Claude Code?

UiPath AgentHack awards **bonus judging points** for solutions that use coding agents
(Claude Code, Codex, Cursor, Gemini CLI) through UiPath for Coding Agents.

AuditPilot uses Claude Code as a **first-class development partner** — not just for
code suggestions, but to build, debug, and ship real UiPath automation components
end-to-end.

---

## Setup

### 1. Install UiPath CLI

```bash
npm install -g @uipath/cli
```

### 2. Install UiPath Skills

```bash
uip skills install
```

### 3. Authenticate

```bash
uip auth login
```

### 4. Launch Claude Code

```bash
claude
```

---

## What Claude Code Built

### 1. Project Scaffolding

Claude Code generated the entire folder structure from a plain English prompt:

**Prompt used:**
```
Create a UiPath automation project called AuditPilot that:
- Captures screenshots from Fivetran, Snowflake and GitHub web UIs
- Validates each screenshot with an AI agent
- Escalates anomalies via UiPath Maestro Case
- Generates an Excel control document
- Logs all agent decisions to Arize Phoenix

Scaffold the folder structure, README, config files, and agent modules.
```

**Output:** Full project structure including `src/`, `config/`, `docs/`, `tests/`
with placeholder files and a detailed README.

---

### 2. AI Validation Agent (`src/agents/validation_agent.py`)

Claude Code wrote the complete validation agent logic including:

- `validate_screenshot()` — core function with LLM prompt construction
- `check_blank_screenshot()` — blank/loading detection
- `detect_user_spike()` — statistical anomaly detection
- `run_audit()` — full orchestration entry point
- `record_human_decision()` — Maestro Case feedback handler

**Prompt used:**
```
Write a Python validation agent for AuditPilot that:
- Takes a screenshot path, tool name, connection name, and tab name as input
- Builds a prompt asking an LLM to detect access control anomalies
- Returns is_valid, anomalies list, summary, confidence score, and action
- Action must be one of: approve, retry, escalate
- Integrates with Arize Phoenix for tracing every decision
- Includes retry logic for blank screenshots
- Has a run_audit() entry point that loops over all connections in the config
```

---

### 3. Arize Logger (`src/agents/arize_logger.py`)

Claude Code built the full Arize Phoenix integration module:

- `init_arize()` — tracer initialization
- `log_validation()` — per-screenshot trace with LLM input/output
- `log_human_feedback()` — Maestro Case outcome logging
- `log_audit_run_summary()` — run-level metrics
- `check_agent_drift()` — month-over-month drift detection

**Prompt used:**
```
Write an Arize Phoenix logger for AuditPilot that:
- Initializes OpenTelemetry tracing via Phoenix
- Logs every AI validation decision as a span with: tool, connection, tab,
  LLM input, LLM output, confidence, anomalies, action, latency
- Logs human reviewer decisions as feedback spans linked to the original
- Logs a run-level summary span after each full audit run
- Includes a drift detection function comparing current vs baseline approval rates
- Handles ImportError gracefully when Arize is not installed
```

---

### 4. UiPath BPMN Workflow Scaffolding

Claude Code generated the BPMN process structure and `.xaml` workflow skeletons
for UiPath Studio Web:

**Prompt used:**
```
Generate a UiPath Maestro BPMN process for AuditPilot with these steps:
1. Monthly scheduler trigger
2. Orchestrator agent reads connections config
3. For each tool (Fivetran, Snowflake, GitHub): RPA captures screenshots
4. AI Validation Agent analyses each screenshot
5. Decision gateway: anomaly found?
   - YES: open Maestro Case, route to human reviewer
   - NO: auto-approve
6. Excel agent builds control document
7. Save, archive, email stakeholder

Include element-level retry configuration on all screenshot capture steps.
Use Try/Catch + RetryScope patterns per UiPath best practices.
```

---

### 5. Connections Config (`config/connections.sample.json`)

Claude Code generated the connections configuration schema:

**Prompt used:**
```
Create a JSON config file for AuditPilot that defines:
- Three SaaS tools: Fivetran (5 connections), Snowflake (2 connections), GitHub (2 connections)
- Each connection has: id, name, label
- Each tool has: name, url, connections array, tabs_to_capture array
- Output section with: excel_template path, archive_folder, report_name_format
- Notifications section with: email_recipients, email_subject template
```

---

### 6. BPMN Flow Diagram (`docs/bpmn_flow.svg`)

Claude Code generated the full SVG architecture diagram showing the
end-to-end AuditPilot flow with color-coded nodes for RPA, AI agents,
human-in-the-loop, Arize observability, and output steps.

---

### 7. Debugging & Refactoring

Claude Code was used iteratively to:

- Debug Arize Phoenix OpenTelemetry span context issues
- Refactor the validation agent to separate blank-check logic from LLM calls
- Add graceful fallback when Arize is not installed
- Improve JSON parsing error handling in the LLM response parser
- Add type hints and docstrings throughout

**Example debug prompt:**
```
The Arize span is not capturing the LLM output correctly. The log_validation()
function receives the raw LLM response but the span attribute shows empty.
Here is the current code: [paste]. Fix it and explain what was wrong.
```

---

## Multi-Step Reasoning Example

One of the most powerful uses of Claude Code was a **multi-step chain** where
it planned, built, debugged, and deployed a component without losing context:

```
Step 1: "Scaffold the validation agent with placeholder LLM call"
Step 2: "Now add Arize tracing to every validation decision"
Step 3: "The span IDs aren't being returned correctly — fix it"
Step 4: "Now add the human feedback function that references the span ID"
Step 5: "Write unit tests for the anomaly detection logic"
Step 6: "Publish this to UiPath Orchestrator via uip CLI"
```

Claude Code maintained full context across all 6 steps — understanding
that each step built on the previous one — exactly the multi-step reasoning
that UiPath AgentHack bonus criteria rewards.

---

## Human-in-the-Loop on Risky Steps

Claude Code was configured to **pause and ask for confirmation** before:

- Publishing workflows to UiPath Orchestrator production folders
- Overwriting existing Excel control document templates
- Modifying the Maestro BPMN process definition

This mirrors the AgentHack bonus criterion:
> *"Human-in-the-loop on risky steps — coding agent pauses before hard-to-reverse actions"*

---

## UiPath Skills Used via Claude Code

| Skill | Purpose |
|---|---|
| `uip run` | Run workflows locally for testing |
| `uip publish` | Publish packages to Orchestrator |
| `uip deploy` | Deploy processes to Orchestrator folders |
| `uip jobs list` | Monitor running jobs |
| `uip jobs logs` | Retrieve execution logs for debugging |
| `uip skills install` | Install UiPath skill set for Claude Code |

---

## Key Takeaway

Claude Code didn't just suggest code — it **built and shipped** real AuditPilot
components end-to-end. From scaffolding to agent logic to deployment, every
major component in this repo was built with Claude Code as the primary
development tool via UiPath for Coding Agents.
