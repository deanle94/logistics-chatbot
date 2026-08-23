# AI-Powered Logistics Analytics Dashboard — Requirements Notes
 
> **Golden rule of the whole spec:** AI must NOT generate answers without computation.
> The AI only *interprets* the question and *routes* it to a tool. Your code does all the math.
 
**Priority tags used in this document:**
- 🔴 `core` — can make or break the grade. Do these first and get them right.
- 🟡 `easy-to-forget` — cheap to do, costly to skip.
- ⚪ untagged — required, but straightforward.
- ⭐ `bonus` — optional, only if time is left.
---
 
## 1. What we are building (one sentence)
 
A web app where a logistics manager can 
- See a dashboard of delivery stats
- Ask questions in plain English 
- Get demand forecasts — 

Note: All powered by **one unified dataset**, where AI only routes questions and code does the actual math.
 
**Three levels of intelligence, one system:**
 
| Level | Meaning | Where it lives |
|---|---|---|
| Descriptive | Dashboards and visualizations | Dashboard section |
| Diagnostic | Natural-language questions answered from data | Chat box → Query tool |
| Predictive & Prescriptive | Forecasting demand + inventory advice | Chat box → Forecasting tool |
 
> Note: forecasting does **not** need a separate tab. It is triggered by a chat
> question ("Predict demand for SKU X for the next 4 months") and returned as a
> rich answer card.
 
---
 
## 2. Features to build
 
### 2.1 Dashboard — 🔴 `core` (KPIs) 
Minimum **5 KPIs** (all required, missing one = checklist failure):
- [ ] Total orders
- [ ] Delivered orders
- [ ] Delayed orders
- [ ] On-time delivery rate
- [ ] Average delivery time
Minimum **2 charts** required by the spec — we will show these **3** (reuses the same displays as the chat, so the third is nearly free):
 
| # | Dashboard chart | Display type | What it shows |
|---|---|---|---|
| 1 | Order volume over time | Line chart | Orders per week/month across the whole dataset |
| 2 | Delivery performance | Stacked bar | On-time vs delayed orders per month |
| 3 | Carrier breakdown | Bar chart | Orders (or delay rate) per carrier, sorted highest first |
 
> Fixed queries, no AI involved — the page always loads the same three charts.
 
### 2.2 Natural-language queries — 🔴 `core`
- [ ] User types a plain-English question (e.g. "Show delayed orders by week for the last 3 months", "Which carrier has the highest delay rate?")
- [ ] System interprets the question → retrieves relevant data
- [ ] Returns: a direct answer, a chart, or both
### 2.3 Dynamic chart generation
- [ ] System automatically selects an appropriate chart type (time series → line, comparison → bar, etc.)
- [ ] Charts render dynamically from query results
- [ ] Supports a defined subset of analytical queries (it's OK to not support everything — see Limitations in README)
**Displays the UI must support** (each answer shows the one that fits the data):
 
| # | Display | Used when the answer is… |
|---|---|---|
| 1 | Stat card | A single number ("How many orders were delivered late last month?") |
| 2 | Line chart | Values over time ("Show delayed orders by week for the last 3 months") |
| 3 | Bar chart | Comparison across categories ("Which carrier has the highest delay rate?") |
| 4 | Stacked bar | Two series side by side (on-time vs delayed per month) |
| 5 | Forecast line | History (solid) + prediction (dashed) on one chart |
| 6 | Data table toggle | Always available under every chart — doubles as Explainability |
 
### 2.4 Explainability — 🟡 `easy-to-forget`
Every answer or chart must show its work:
- [ ] Filters used (e.g. time range)
- [ ] Metrics and dimensions
- [ ] Query plan / structured interpretation (recommended)
- [ ] Access to underlying data (table or summary)
> Cheap win: this is just displaying the structured query the AI already
> produced. A few lines of UI code protects a lot of trust points.
 
### 2.5 Forecasting (via chat)
The forecast answer card must contain **all four**:
- [ ] Forecast values
- [ ] Visualization: historical + forecast on one chart (solid vs dashed line)
- [ ] Inventory recommendation
- [ ] Explanation of methodology
Acceptable methods (simple is explicitly fine):
- Moving average · Linear regression · Exponential smoothing · Simple trend models
---
 
### Decision log (fill as we build — becomes the README "Key design decisions" section)
 
Format for every entry: **Decision → Why → Trade-off (what we gave up)**
 
| # | Decision | Why | Trade-off accepted |
|---|---|---|---|
| 1 | AI outputs structured JSON, never SQL | Safe: code builds queries, AI can't inject or invent | Less flexible — only pre-defined metrics/filters work |
| 2 | Chat and dashboard share one query tool | Numbers can never disagree; less code | Dashboard slightly over-powered for fixed queries |
| 3 | Simple forecasting method (e.g. moving average) | Spec allows it; explainable; fits time budget | Lower accuracy than real models (ARIMA, ML) |
| 4 | Limited question "menu" + polite refusals | Correct answers only; no hallucinated numbers | Some reasonable questions get "not supported" |
 
> Cheap win: keep this table updated for 2 minutes after every decision, and
> the hardest README sections (Key decisions, Assumptions, Limitations) write
> themselves at the end.
 
### Required system flow
```
User question → AI interpretation → Tool selection → Structured input
→ Computation → Result → Explanation → Visualization
```
 
### Two required analytical tools
| Tool | Used for | Example questions |
|---|---|---|
| A. Query tool | Dashboard queries, aggregations, KPI calculations | "Show delayed orders by week", "Which carrier has the highest delay rate?" |
| B. Forecasting tool | Predicting future demand | "Predict demand for SKU X for the next 4 months", "How much inventory should I plan?" |
 
> Design tip: the dashboard calls the Query tool directly (hardcoded queries);
> the chat calls the same Query tool via the AI interpreter. One shared
> calculator = dashboard and chat can never disagree.
 
---
 
## 4. Deliverables to ship
 
- [ ] 🔴 `core` — **Live public URL**, fully usable without local setup, stable for reviewers. (Deploy early, not on the last day — a down URL means nothing can be graded.)
- [ ] Test credentials, if authentication is used
- [ ] Source code repository
- [ ] 🟡 `easy-to-forget` — **README.md** covering:
  - Setup: local instructions + environment variables
  - Architecture: system overview, key design decisions, data flow
  - AI approach: how questions are interpreted, how tools are selected
  - Assumptions: simplifications made
  - Limitations: unsupported features or queries
  - Future improvements: what you would build next
---

## 5. Bonus — ⭐ only if time is left
 
- Query history
- Caching
- Tests
- Docker setup
- Advanced explainability
- Handling ambiguous queries ("did you mean last month or last 30 days?")
> A cheaper UX trick with similar payoff: suggested question chips above the
> chat box (e.g. "Predict demand for SKU X") so reviewers instantly discover
> the forecasting feature.
 
---