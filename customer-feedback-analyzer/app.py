"""Streamlit UI: upload, charts, per-theme example quotes.

All the interesting product work -- parsing, batching, prompting, validating,
aggregating -- lives in feedback_logic.py. This file only renders it.
"""

import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from feedback_logic import FeedbackAnalysisError, analyze_feedback, parse_feedback_csv

load_dotenv()

st.set_page_config(page_title="Customer Feedback Analyzer", page_icon="\U0001f5c2️", layout="centered")

# Sentiment is a status, not an identity -- it gets the reserved good/warning/critical
# palette. Never reused as a generic series color elsewhere on this page.
SENTIMENT_COLORS = {"positive": "#0ca30c", "neutral": "#c98a10", "negative": "#d03b3b"}
# Theme frequency is a ranked magnitude, not a set of unrelated categories --
# one sequential hue, not a categorical rainbow that would imply otherwise.
THEME_COLOR = "#2a78d6"

st.title("\U0001f5c2️ Customer Feedback Analyzer")
st.caption(
    "Upload raw customer feedback and get sentiment plus a ranked, quotable list of "
    "themes -- the part after labeling that a product team would actually put in a "
    "roadmap review."
)

use_sample = st.checkbox("Analyze the sample feedback instead of uploading")
uploaded = None if use_sample else st.file_uploader(
    "Upload a CSV with a review_text column (or feedback / comment / text / review)",
    type="csv",
)

if st.button("Analyze", type="primary", disabled=not (use_sample or uploaded)):
    if not os.environ.get("OPENAI_API_KEY"):
        st.error("No OPENAI_API_KEY found. Copy .env.example to .env, add your key, and restart.")
        st.stop()

    source = "sample_feedback.csv" if use_sample else uploaded
    try:
        rows = parse_feedback_csv(source)
        with st.spinner(f"Analyzing {len(rows)} reviews..."):
            result = analyze_feedback(rows)
    except FeedbackAnalysisError as e:
        st.error(f"Couldn't analyze this file: {e}")
        st.stop()

    st.session_state["result"] = result
    st.session_state["row_count"] = len(rows)

if "result" in st.session_state:
    result = st.session_state["result"]
    counts = result.counts

    st.subheader(f"Sentiment breakdown · {st.session_state['row_count']} reviews")
    sentiment_fig = go.Figure(
        go.Bar(
            x=[counts["positive"], counts["neutral"], counts["negative"]],
            y=["Positive", "Neutral", "Negative"],
            orientation="h",
            marker_color=[SENTIMENT_COLORS[s] for s in ("positive", "neutral", "negative")],
            text=[counts["positive"], counts["neutral"], counts["negative"]],
            textposition="outside",
        )
    )
    sentiment_fig.update_layout(
        showlegend=False, height=220, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_visible=False, yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(sentiment_fig, use_container_width=True)

    st.subheader("Top themes")
    themes = result.themes
    labels = [t for t, _ in themes]
    values = [c for _, c in themes]
    theme_fig = go.Figure(
        go.Bar(
            x=values[::-1], y=labels[::-1], orientation="h",
            marker_color=THEME_COLOR, text=values[::-1], textposition="outside",
        )
    )
    theme_fig.update_layout(
        showlegend=False, height=max(220, 42 * len(labels)),
        margin=dict(l=10, r=10, t=10, b=10), xaxis_visible=False,
    )
    st.plotly_chart(theme_fig, use_container_width=True)

    st.subheader("Example quotes by theme")
    for theme, count in themes:
        with st.container(border=True):
            mention_word = "mention" if count == 1 else "mentions"
            st.markdown(f"**{theme}** · {count} {mention_word}")
            st.markdown(f"> {result.quotes[theme]}")
