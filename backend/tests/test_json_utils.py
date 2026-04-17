"""Tests for JSON extraction from LLM responses."""

import pytest
from app.services.json_utils import extract_json


class TestExtractJson:
    def test_plain_json_object(self):
        text = '{"action": "post", "content": "hello", "sentiment": "positive", "sentiment_score": 0.8}'
        result = extract_json(text)
        assert result["action"] == "post"
        assert result["sentiment_score"] == 0.8

    def test_plain_json_array(self):
        text = '[{"name": "Alice"}, {"name": "Bob"}]'
        result = extract_json(text)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    def test_markdown_code_block(self):
        text = """Here is the response:
```json
{"action": "share", "content": "wow!", "sentiment": "positive", "sentiment_score": 0.9}
```"""
        result = extract_json(text)
        assert result["action"] == "share"

    def test_json_with_surrounding_text(self):
        text = 'The agent decided: {"action": "like", "content": "", "sentiment": "neutral", "sentiment_score": 0.0} end.'
        result = extract_json(text)
        assert result["action"] == "like"

    def test_trailing_comma_fix(self):
        text = '{"action": "post", "content": "test",}'
        result = extract_json(text)
        assert result["action"] == "post"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Could not extract JSON"):
            extract_json("this is not json at all")

    def test_nested_json_object(self):
        text = '{"viral_score": 75, "summary": "Good campaign", "recommendations": ["Do A", "Do B"]}'
        result = extract_json(text)
        assert result["viral_score"] == 75
        assert len(result["recommendations"]) == 2

    def test_empty_markdown_block(self):
        text = """```json
[{"title": "Section 1", "question": "How?", "tools": ["graph_search"]}]
```"""
        result = extract_json(text)
        assert isinstance(result, list)
        assert result[0]["title"] == "Section 1"
