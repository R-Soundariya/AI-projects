# AI PM Projects 101

A portfolio of five small, end-to-end AI products, each built the way a product manager would "vibe code" a prototype: describe the outcome you want, let an AI write the code, run it, poke at it until it's actually useful, then write down what you learned.

Four of the five are self-contained single-file web apps — no install, just open `index.html` — built with the Claude API. The fifth, **Customer Feedback Analyzer**, is a Python/Streamlit app backed by the OpenAI API, with its own tests.

Every project's own README explains two things:

- **How it works** — the architecture, the prompt design, the data flow.
- **How it was vibecoded** — the actual prompt-build-test loop used to get from idea to working app, so you can repeat the process on your own ideas.

| # | Project | Description | Live demo |
|---|---------|-------------|-----------|
| 1 | [🥬 Fresh Cart — Grocery List Optimiser](Grocery%20list%20optimiser/) | Generates deduplicated, section-organised grocery lists from weekly meal plans, with ₹ cost estimates, budget checks, and Sunday prep tips. Built with Claude. | [Open ↗](https://r-soundariya.github.io/AI-projects/Grocery%20list%20optimiser/) |
| 2 | [🧳 Safar Saathi — India Trip Planner](India%20trip%20planner/) | Day-by-day India itineraries with local food spots, hidden gems, transport costs, and full budget breakdowns — like advice from a local friend. Built with Claude. | [Open ↗](https://r-soundariya.github.io/AI-projects/India%20trip%20planner/) |
| 3 | [🧭 AI/ML Engineer — 90-Day Flight Plan](Career%20Roadmap/) | Built an AI-powered career switch roadmap tool using Claude — generates personalised 90-day plans with skill gap analysis and portfolio project suggestions. | [Open ↗](https://r-soundariya.github.io/AI-projects/Career%20Roadmap/) |
| 4 | [📦 Return Radar — Returns Root-Cause Analysis](Return%20Radar/) | Built a returns root-cause analysis tool using Claude — categorizes return reasons, surfaces price and seasonal patterns, and prioritizes fixes by impact. | [Open ↗](https://r-soundariya.github.io/AI-projects/Return%20Radar/) |
| 5 | [🗂️ Customer Feedback Analyzer](customer-feedback-analyzer/) | Python + Streamlit app that batches raw feedback through an LLM for sentiment/theme tagging, then aggregates in tested Python into ranked, quotable themes. | [Run locally](customer-feedback-analyzer/#how-to-run) — see README |

## Running the Python project

Four of the five projects need nothing — download the HTML file and open it. The fifth needs a local Python environment:

```
cd customer-feedback-analyzer
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then add your OPENAI_API_KEY
streamlit run app.py
```

## Running tests

`customer-feedback-analyzer` separates logic (prompt building + response parsing, pure functions) from the UI (Streamlit). The logic module is unit tested with the OpenAI API mocked out, so tests run offline, fast, and without an API key.

```
cd customer-feedback-analyzer
pip install -r requirements-dev.txt
pytest
```

## Why these five

Fresh Cart and Safar Saathi are pure LLM-generation products — describe a constraint, get back a structured plan. AI/ML Engineer Roadmap and Return Radar are structured-analysis products — feed in a specific situation (a career, a dataset) and get back categorized, prioritized output. Customer Feedback Analyzer is the odd one out on purpose: a real batching pipeline with validation and tests, the shape of "AI feature" that has to survive contact with a file bigger than a demo. Together they cover the core shapes of AI feature a PM is likely to prototype or ship: generation, analysis, and a production-shaped pipeline.
