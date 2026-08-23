# Architecture — AI-Powered Logistics Analytics Dashboard

## 1. Context and goals

# Project Summary

A web app for logistics managers with three features — **KPI dashboard**, **natural-language Q&A**, and **demand forecasting** — built on one shared dataset (400 rows from `mock_logistics_data.csv`, read-only in PostgreSQL).

## Core Rule

The AI only **translates** questions into tool calls — it never calculates.
All numbers come from our own code.
This keeps data accurate and AI behavior trustworthy.

## Decision Record

This document is the single source of truth for decisions — see **Section 4** for all trade-offs.

---

## 2. High-level design

```mermaid
flowchart TB
    subgraph Browser["Browser UI"]
        DV["Dashboard view<br/>(5 KPIs + 3 charts)"]
        CV["Chat view<br/>(answers + explainability)"]
    end

    DV --> RD
    CV --> RC

    subgraph PY["One Python service (FastAPI)"]
        RD["Dashboard routes<br/>/api/kpis · /api/charts<br/>no AI"]
        RC["Chat route<br/>/api/chat"]
        AG["Agent layer (LangChain)<br/>interpret + pick tool"]
        TL["Tools layer<br/>query tool · forecast tool<br/>+ parameter validation"]
        CALC["Calculator module<br/>the only home of every formula"]
        DAL["Data access<br/>(SQLAlchemy)"]
    end

    RC --> AG
    AG <--> LLM["LLM provider<br/>(Claude, swappable via LangChain)"]
    AG --> TL
    RD --> CALC
    TL --> CALC
    CALC --> DAL
    DAL --> PG["PostgreSQL<br/>(seeded from CSV, read-only role)"]
```

**In words:** every number — dashboard or chat — passes through the same calculator module. The agent can only _ask_ for numbers. It can never produce them.

**Two deployables in total:** this service and the database.

---

## 3. Components and responsibilities

Everything except the browser and the database runs in one Python process. Separation is by **module**, not by service.

| Module                               | Responsibility                                                                                                         |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| **UI**                               | Render the dashboard (5 KPIs, 3 charts) and the chat (answer cards + explainability panel)                             |
| **Dashboard routes**                 | Serve fixed KPI/chart requests by calling the calculator                                                               |
| **Chat route**                       | Take a question, hand it to the agent, return the answer plus its interpretation                                       |
| **Agent layer** (LangChain)          | Interpret the question, pick a tool, produce **structured parameters**                                                 |
| **LLM provider** (Claude, swappable) | Natural-language understanding only                                                                                    |
| **Tools layer**                      | Exactly two tools (query, forecast); validate parameters against a whitelist before running them                       |
| **Calculator module**                | **The single owner of every formula and business definition** — "delayed", on-time rate, average delivery time, demand |
| **Data access** (SQLAlchemy)         | Typed models, sessions, safe query building                                                                            |
| **PostgreSQL**                       | Store the 400 rows seeded once from the CSV; read-only role                                                            |

### Separation of concerns by folder

We run one service, so that boundary does not exist for free. We recreate it with folders and one rule per folder.

| Layer                          | Folder                 | Rule                                                                        |
| ------------------------------ | ---------------------- | --------------------------------------------------------------------------- |
| AI interpretation              | `agent/`               | Never imports `calculator/` or `data/`. Reaches them only through `tools/`. |
| Business logic / orchestration | `api/`, `tools/`       | Holds no formulas. Calls the calculator.                                    |
| Data computation               | `calculator/`, `data/` | Never imports `agent/`. Only `data/` touches the database.                  |

Each folder is one layer. The import rules are the boundary: as long as they hold, the layers stay independent and any one of them can later move into its own service.

---

## 4. Key decisions and reasoning

### Decision 1 — One calculator module owns every formula

|               |                                                                                                                             |
| ------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Decision**  | All formulas and business definitions live in one module. Routes and tools only call it.                                    |
| **Why**       | Dashboard and chat can be asked the same question. Two copies of a formula drift apart, and the product contradicts itself. |
| **Trade-off** | The module becomes a change bottleneck. Fine at this scale.                                                                 |

### Decision 2 — One service for both the dashboard and the chat

|                      |                                                                                                                                                                                                        |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Decision**         | One Python (FastAPI) service serves both. The agent must be Python, so the whole stack is Python and the calculator is a plain in-process call.                                                        |
| **Why**              | Fewer parts, fewer independent failures — the app is either up or down. No serialization, no protocol layer, no second toolchain. Good for the MVP(dev fast)                                           |
| **Trade-off**        | The layers lose their process boundary. Folders and import rules replace it (section 3).                                                                                                               |
| **Rejected for now** | Separate dashboard and chat services. Worth it when workloads diverge — chat is slow and LLM-bound, the dashboard is fast and cacheable. The calculator is already the seam, so the split stays cheap. |

### Decision 3 — AI never computes

|               |                                                                                                                                                            |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Decision**  | The agent only outputs a tool choice, structured parameters, and prose around a tool result. Every number traces back to a tool run over the real dataset. |
| **Why**       | It is the one rule that makes the numbers trustworthy. A model that can answer from memory will eventually answer wrongly and confidently.                 |
| **Trade-off** | Only pre-defined metrics and filters work. Some reasonable questions get "I can't answer that". We prefer a refusal to a wrong number.                     |

**Two layers make this structural, not a prompt instruction:**

1. **Forced tool use** — the model must emit a tool call before it can reply. Plain text is not a legal first answer.
2. **Numbers come from the tool result field**, not from model text. The UI prints the tool's value; the agent writes the words around it.

---

## 5. Data flow

**Dashboard path (no AI involved):**

```mermaid
flowchart LR
    A[UI] --> B[Dashboard Route]
    B --> C[Calculator]
    C --> D[SQLAlchemy]
    D --> E[(PostgreSQL)]
    E --> F[KPIs / Chart Data]
    F --> A
```

**Chat path (query):**

```mermaid
flowchart LR
    A[UI] --> B[Chat Route]
    B --> C[Agent]
    C --> D[LLM Interprets]
    D --> E["Structured Params
    {metric, filters, group_by}"]
    E --> F[Query Tool]
    F --> G[Validation]
    G --> H[Calculator]
    H --> I["Result + Params
    Echoed Back"]
    I --> C
    C --> J[Agent Wraps in Prose]
    J --> K["UI: Answer + Chart
    + Explainability Panel"]
```

**Chat path (forecast):**

```mermaid
flowchart LR
    A[UI] --> B[Chat Route]
    B --> C[Forecast Tool]
    C --> D[Historical Series]
    C --> E[Forecast Values]
    C --> F[Inventory Recommendation]
    C --> G[Methodology Note]
    D --> H["UI: One Chart
    History (solid) + Forecast (dashed)"]
    E --> H
    F --> H
    G --> H
```

**Explainability comes free:** the structured parameters the AI produced _are_ the explanation. Every answer card shows them back, plus access to the underlying rows.

---
