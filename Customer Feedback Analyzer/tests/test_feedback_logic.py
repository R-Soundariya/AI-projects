import io
import json
from unittest.mock import patch

import pytest

from feedback_logic import (
    FeedbackAnalysisError,
    analyze_feedback,
    build_analysis_prompt,
    chunk,
    example_quote,
    parse_analysis_json,
    parse_feedback_csv,
    sentiment_counts,
    top_themes,
)


def csv_buffer(text):
    return io.StringIO(text)


class TestParseFeedbackCsv:
    def test_recognizes_review_text_column(self):
        rows = parse_feedback_csv(csv_buffer("review_id,review_text\n1,Great app\n2,Terrible bugs\n"))
        assert len(rows) == 2
        assert rows[0]["text"] == "Great app"
        assert rows[0]["id"] == "1"

    @pytest.mark.parametrize("column", ["feedback", "comment", "text", "review"])
    def test_recognizes_column_variants(self, column):
        rows = parse_feedback_csv(csv_buffer(f"{column}\nsomething useful\n"))
        assert rows[0]["text"] == "something useful"

    def test_falls_back_to_row_number_when_no_id_column(self):
        rows = parse_feedback_csv(csv_buffer("review_text\nfirst\nsecond\n"))
        assert [r["id"] for r in rows] == ["0", "1"]

    def test_prefers_explicit_id_column(self):
        rows = parse_feedback_csv(csv_buffer("id,review_text\n42,hello\n"))
        assert rows[0]["id"] == "42"

    def test_raises_on_unrecognized_columns(self):
        with pytest.raises(FeedbackAnalysisError):
            parse_feedback_csv(csv_buffer("foo,bar\n1,2\n"))

    def test_skips_blank_rows(self):
        rows = parse_feedback_csv(csv_buffer("review_text\nreal one\n\n"))
        assert len(rows) == 1


class TestChunk:
    def test_splits_into_batches(self):
        rows = [{"id": str(i)} for i in range(5)]
        assert [len(b) for b in chunk(rows, batch_size=2)] == [2, 2, 1]

    def test_single_batch_when_smaller_than_size(self):
        rows = [{"id": "1"}]
        assert chunk(rows, batch_size=20) == [rows]

    def test_empty_rows(self):
        assert chunk([], batch_size=20) == []


class TestBuildAnalysisPrompt:
    def test_includes_ids_and_text(self):
        prompt = build_analysis_prompt([{"id": "1", "text": "the app crashed"}])
        assert "1:" in prompt
        assert "the app crashed" in prompt

    def test_instructs_theme_reuse(self):
        prompt = build_analysis_prompt([{"id": "1", "text": "x"}])
        assert "reuse" in prompt.lower()

    def test_requests_json_shape(self):
        prompt = build_analysis_prompt([{"id": "1", "text": "x"}])
        assert "sentiment" in prompt
        assert "themes" in prompt


class TestParseAnalysisJson:
    def test_valid_response(self):
        batch = [{"id": "1", "text": "great"}]
        raw = json.dumps({"results": [{"id": "1", "sentiment": "positive", "themes": ["onboarding"]}]})
        tagged = parse_analysis_json(raw, batch)
        assert tagged[0]["sentiment"] == "positive"
        assert tagged[0]["themes"] == ["onboarding"]
        assert tagged[0]["text"] == "great"

    def test_rejects_invalid_sentiment(self):
        batch = [{"id": "1", "text": "x"}]
        raw = json.dumps({"results": [{"id": "1", "sentiment": "mixed", "themes": ["bugs/reliability"]}]})
        with pytest.raises(FeedbackAnalysisError):
            parse_analysis_json(raw, batch)

    def test_raises_on_missing_id(self):
        batch = [{"id": "1", "text": "x"}, {"id": "2", "text": "y"}]
        raw = json.dumps({"results": [{"id": "1", "sentiment": "positive", "themes": ["bugs/reliability"]}]})
        with pytest.raises(FeedbackAnalysisError):
            parse_analysis_json(raw, batch)

    def test_raises_on_unknown_id(self):
        batch = [{"id": "1", "text": "x"}]
        raw = json.dumps({"results": [{"id": "99", "sentiment": "positive", "themes": ["bugs/reliability"]}]})
        with pytest.raises(FeedbackAnalysisError):
            parse_analysis_json(raw, batch)

    def test_raises_on_missing_themes(self):
        batch = [{"id": "1", "text": "x"}]
        raw = json.dumps({"results": [{"id": "1", "sentiment": "positive", "themes": []}]})
        with pytest.raises(FeedbackAnalysisError):
            parse_analysis_json(raw, batch)

    def test_raises_on_malformed_json(self):
        with pytest.raises(FeedbackAnalysisError):
            parse_analysis_json("not json", [{"id": "1", "text": "x"}])

    def test_raises_when_results_key_missing(self):
        batch = [{"id": "1", "text": "x"}]
        with pytest.raises(FeedbackAnalysisError):
            parse_analysis_json(json.dumps({"wrong_key": []}), batch)


class TestAggregation:
    TAGGED = [
        {"id": "1", "text": "a", "sentiment": "positive", "themes": ["onboarding"]},
        {"id": "2", "text": "b", "sentiment": "negative", "themes": ["bugs/reliability"]},
        {"id": "3", "text": "c", "sentiment": "negative", "themes": ["bugs/reliability", "performance"]},
    ]

    def test_sentiment_counts_tallies_all_three(self):
        assert sentiment_counts(self.TAGGED) == {"positive": 1, "neutral": 0, "negative": 2}

    def test_sentiment_counts_zero_when_no_rows(self):
        assert sentiment_counts([]) == {"positive": 0, "neutral": 0, "negative": 0}

    def test_top_themes_ranks_by_frequency(self):
        assert top_themes(self.TAGGED)[0] == ("bugs/reliability", 2)

    def test_example_quote_returns_matching_text(self):
        assert example_quote(self.TAGGED, "onboarding") == "a"
        assert example_quote(self.TAGGED, "performance") == "c"

    def test_example_quote_empty_when_no_match(self):
        assert example_quote(self.TAGGED, "nonexistent") == ""


class TestAnalyzeFeedback:
    def test_batches_and_aggregates(self):
        rows = [{"id": str(i), "text": f"review {i}"} for i in range(3)]

        def fake_response(prompt):
            ids_in_batch = [row["id"] for row in rows if f'{row["id"]}: "{row["text"]}"' in prompt]
            return json.dumps({
                "results": [
                    {"id": i, "sentiment": "positive", "themes": ["onboarding"]}
                    for i in ids_in_batch
                ]
            })

        with patch("feedback_logic.call_llm", side_effect=fake_response) as mock_call:
            result = analyze_feedback(rows, batch_size=2)

        assert mock_call.call_count == 2
        assert len(result.tagged) == 3
        assert result.counts == {"positive": 3, "neutral": 0, "negative": 0}
        assert result.themes == [("onboarding", 3)]

    def test_raises_if_a_batch_fails_validation(self):
        rows = [{"id": "1", "text": "x"}]
        bad_response = json.dumps({"results": [{"id": "1", "sentiment": "mixed", "themes": ["bugs/reliability"]}]})
        with patch("feedback_logic.call_llm", return_value=bad_response):
            with pytest.raises(FeedbackAnalysisError):
                analyze_feedback(rows, batch_size=20)
