"""CSV parsing, batching, prompt building, and aggregation for feedback analysis.

The LLM's only job is per-row tagging (sentiment + themes). Everything after
that -- counting, ranking, picking an example quote -- is plain, tested Python,
so the charts are always correct given the tags, independent of prompt wording.
"""

import json
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from llm_client import call_llm

TEXT_COLUMN_CANDIDATES = ("review_text", "feedback", "comment", "text", "review")
ID_COLUMN_CANDIDATES = ("review_id", "id")
VALID_SENTIMENTS = ("positive", "neutral", "negative")

CANONICAL_THEMES = (
    "bugs/reliability",
    "billing/pricing",
    "support responsiveness",
    "onboarding",
    "performance",
    "feature requests",
)


class FeedbackAnalysisError(Exception):
    """Raised when the model's output can't be trusted -- bad shape, an
    invalid sentiment value, or a row that didn't come back at all."""


@dataclass
class AnalysisResult:
    tagged: list
    counts: dict
    themes: list  # list of (theme, count), ranked
    quotes: dict  # theme -> example quote


def _find_column(columns, candidates):
    lookup = {c.lower().strip(): c for c in columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def parse_feedback_csv(path_or_buffer):
    """Read a feedback CSV, tolerant of column-name variants.

    Every row gets a stable string `id` (from review_id/id if present,
    otherwise the row number) and a normalized `text` field, so results can
    always be matched back to the source row regardless of the model's output
    order.
    """
    df = pd.read_csv(path_or_buffer)
    text_col = _find_column(df.columns, TEXT_COLUMN_CANDIDATES)
    if text_col is None:
        raise FeedbackAnalysisError(
            "No recognized text column. Expected one of: "
            + ", ".join(TEXT_COLUMN_CANDIDATES)
        )
    id_col = _find_column(df.columns, ID_COLUMN_CANDIDATES)

    rows = []
    for i, row in df.iterrows():
        text = row[text_col]
        if pd.isna(text) or not str(text).strip():
            continue
        parsed = row.to_dict()
        parsed["id"] = str(row[id_col]) if id_col else str(i)
        parsed["text"] = str(text).strip()
        rows.append(parsed)
    return rows


def chunk(rows, batch_size=20):
    """Split rows into batches so each model call's output stays bounded."""
    return [rows[i : i + batch_size] for i in range(0, len(rows), batch_size)]


def build_analysis_prompt(batch):
    """Build the prompt for one batch: id/text pairs in, a request for a
    JSON object of {id, sentiment, themes} out.

    The instruction to *reuse* theme tags across items -- rather than invent
    a new phrase per comment -- is the single highest-leverage sentence here:
    without it, aggregation downstream has nothing consistent to rank.
    """
    lines = "\n".join(f'{row["id"]}: "{row["text"]}"' for row in batch)
    themes_hint = ", ".join(CANONICAL_THEMES)
    return (
        "You are analyzing customer feedback. For each item below, assign:\n"
        '- "sentiment": exactly one of "positive", "neutral", "negative"\n'
        '- "themes": a list of 1 to 3 short theme tags\n\n'
        "Reuse the same theme tag across items whenever the underlying issue "
        "is the same -- do not invent a new phrase for every comment. Prefer "
        f"these theme tags when they genuinely fit: {themes_hint}. Only "
        "introduce a new theme tag if none of these fit.\n\n"
        "Feedback items (id: \"text\"):\n"
        f"{lines}\n\n"
        "Respond with a JSON object of exactly this shape, no other text:\n"
        '{"results": [{"id": "<id>", "sentiment": "<positive|neutral|negative>", '
        '"themes": ["<theme>", ...]}, ...]}\n'
        "One entry per feedback item above, using the same id."
    )


def parse_analysis_json(raw_json, batch):
    """Validate and match the model's response back to the source batch.

    Rejects an unrecognized sentiment value outright rather than silently
    keeping it, and raises if any id from the batch didn't come back --
    downstream aggregation should never have to handle a surprise category.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise FeedbackAnalysisError(f"Model did not return valid JSON: {e}") from e

    results = data.get("results") if isinstance(data, dict) else None
    if results is None:
        raise FeedbackAnalysisError("Expected a JSON object with a 'results' array.")

    batch_by_id = {row["id"]: row for row in batch}
    tagged = []
    seen_ids = set()
    for entry in results:
        entry_id = str(entry.get("id"))
        if entry_id not in batch_by_id:
            raise FeedbackAnalysisError(f"Model returned unknown id: {entry_id!r}")

        sentiment = entry.get("sentiment")
        if sentiment not in VALID_SENTIMENTS:
            raise FeedbackAnalysisError(
                f"Invalid sentiment {sentiment!r} for id {entry_id} "
                f"(expected one of {VALID_SENTIMENTS})"
            )

        themes = entry.get("themes")
        if not isinstance(themes, list) or not themes:
            raise FeedbackAnalysisError(f"Missing or empty themes for id {entry_id}")

        tagged.append({**batch_by_id[entry_id], "sentiment": sentiment, "themes": themes})
        seen_ids.add(entry_id)

    missing = set(batch_by_id) - seen_ids
    if missing:
        raise FeedbackAnalysisError(f"Model did not return results for ids: {sorted(missing)}")

    return tagged


def sentiment_counts(tagged):
    """Tally positive/neutral/negative, always reporting all three -- even
    at zero -- so a chart never silently drops a category."""
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for row in tagged:
        counts[row["sentiment"]] += 1
    return counts


def top_themes(tagged, n=10):
    """Rank themes by frequency across all tagged rows."""
    counter = Counter()
    for row in tagged:
        for theme in row["themes"]:
            counter[theme] += 1
    return counter.most_common(n)


def example_quote(tagged, theme):
    """The first source review mentioning `theme`, so every chart bar links
    back to a real sentence instead of just a number."""
    for row in tagged:
        if theme in row["themes"]:
            return row["text"]
    return ""


def analyze_feedback(rows, batch_size=20):
    """Run the full pipeline: batch, prompt, call the model, validate, and
    aggregate. This is the one function app.py calls."""
    tagged = []
    for batch in chunk(rows, batch_size):
        prompt = build_analysis_prompt(batch)
        raw = call_llm(prompt)
        tagged.extend(parse_analysis_json(raw, batch))

    themes = top_themes(tagged)
    return AnalysisResult(
        tagged=tagged,
        counts=sentiment_counts(tagged),
        themes=themes,
        quotes={theme: example_quote(tagged, theme) for theme, _ in themes},
    )
