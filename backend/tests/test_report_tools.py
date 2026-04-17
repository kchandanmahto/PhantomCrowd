"""Tests for report agent tools (graph_search, action_search, sentiment_aggregate, identify_influencers)."""

from app.services.simulation_v2.engine import Action
from app.services.report.tools import (
    graph_search, action_search, sentiment_aggregate, identify_influencers,
)


def _make_action(
    round_num=1, agent_name="Agent-1", action_type="post",
    content="", target_agent="", sentiment="neutral", sentiment_score=0.0,
    age=25, gender="female", occupation="Student",
) -> Action:
    return Action(
        round_num=round_num,
        agent_name=agent_name,
        agent_profile={"name": agent_name, "age": age, "gender": gender, "occupation": occupation},
        action_type=action_type,
        content=content,
        target_agent=target_agent,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
    )


class TestGraphSearch:
    def test_finds_relevant_lines(self):
        context = "LUNA is a K-POP idol\nNOVA is a rival group\nStar Entertainment manages LUNA"
        result = graph_search(context, "LUNA idol")
        assert "LUNA" in result.result
        assert result.tool == "graph_search"

    def test_no_match(self):
        context = "LUNA is a K-POP idol"
        result = graph_search(context, "blockchain crypto")
        assert "No relevant graph data found" in result.result

    def test_empty_context(self):
        result = graph_search("", "anything")
        assert "No relevant graph data found" in result.result


class TestActionSearch:
    def test_filter_by_agent(self):
        actions = [
            _make_action(agent_name="Alice", content="hello"),
            _make_action(agent_name="Bob", content="world"),
        ]
        result = action_search(actions, {"agent": "Alice"})
        assert "1 actions" in result.result
        assert "Alice" in result.result

    def test_filter_by_action_type(self):
        actions = [
            _make_action(action_type="post", content="my post"),
            _make_action(action_type="like"),
            _make_action(action_type="share", target_agent="Agent-1"),
        ]
        result = action_search(actions, {"action_type": "post"})
        assert "1 actions" in result.result

    def test_filter_by_sentiment(self):
        actions = [
            _make_action(sentiment="positive", content="great!"),
            _make_action(sentiment="negative", content="bad"),
            _make_action(sentiment="positive", content="awesome"),
        ]
        result = action_search(actions, {"sentiment": "positive"})
        assert "2 actions" in result.result

    def test_filter_by_round_range(self):
        actions = [
            _make_action(round_num=1), _make_action(round_num=2),
            _make_action(round_num=3), _make_action(round_num=5),
        ]
        result = action_search(actions, {"round_min": 2, "round_max": 3})
        assert "2 actions" in result.result

    def test_filter_has_content(self):
        actions = [
            _make_action(content="a real post with content"),
            _make_action(content=""),
            _make_action(content="abc"),  # too short (<= 5)
        ]
        result = action_search(actions, {"has_content": True})
        assert "1 actions" in result.result

    def test_empty_actions(self):
        result = action_search([], {"agent": "Nobody"})
        assert "0 actions" in result.result


class TestSentimentAggregate:
    def test_overall_stats(self):
        actions = [
            _make_action(sentiment="positive", sentiment_score=0.8),
            _make_action(sentiment="positive", sentiment_score=0.6),
            _make_action(sentiment="negative", sentiment_score=-0.5),
        ]
        result = sentiment_aggregate(actions)
        assert "Total actions: 3" in result.result
        assert "Avg sentiment score: 0.300" in result.result

    def test_segment_by_age(self):
        actions = [
            _make_action(age=18, sentiment="positive", sentiment_score=0.9),
            _make_action(age=20, sentiment="positive", sentiment_score=0.7),
            _make_action(age=35, sentiment="negative", sentiment_score=-0.5),
        ]
        result = sentiment_aggregate(actions, {"age_min": 15, "age_max": 25})
        assert "Total actions: 2" in result.result

    def test_segment_by_gender(self):
        actions = [
            _make_action(gender="male", sentiment="positive", sentiment_score=0.5),
            _make_action(gender="female", sentiment="negative", sentiment_score=-0.3),
            _make_action(gender="female", sentiment="positive", sentiment_score=0.4),
        ]
        result = sentiment_aggregate(actions, {"gender": "female"})
        assert "Total actions: 2" in result.result

    def test_segment_no_match(self):
        actions = [_make_action(age=30)]
        result = sentiment_aggregate(actions, {"age_min": 50, "age_max": 60})
        assert "No actions match" in result.result

    def test_per_round_trend(self):
        actions = [
            _make_action(round_num=1, sentiment="positive", sentiment_score=0.5),
            _make_action(round_num=2, sentiment="negative", sentiment_score=-0.3),
        ]
        result = sentiment_aggregate(actions)
        assert "Trend by round:" in result.result
        assert "Round 1" in result.result
        assert "Round 2" in result.result


class TestIdentifyInfluencers:
    def test_basic_influencer_ranking(self):
        actions = [
            _make_action(agent_name="Popular", action_type="post", content="great post"),
            _make_action(agent_name="Fan-1", action_type="share", target_agent="Popular"),
            _make_action(agent_name="Fan-2", action_type="share", target_agent="Popular"),
            _make_action(agent_name="Fan-3", action_type="reply", target_agent="Popular", content="agreed!"),
            _make_action(agent_name="Nobody", action_type="post", content="ignored post"),
        ]
        result = identify_influencers(actions, top_n=3)
        assert "@Popular" in result.result
        # Popular should be #1: 2 shares (6) + 1 reply (2) + 1 post (0.5) = 8.5
        lines = result.result.split("\n")
        first_influencer = lines[1]  # First line after header
        assert "Popular" in first_influencer

    def test_top_n_limits_results(self):
        actions = [
            _make_action(agent_name=f"Agent-{i}", action_type="post", content=f"post {i}")
            for i in range(10)
        ]
        result = identify_influencers(actions, top_n=3)
        # Count lines with "@" (influencer entries)
        influencer_lines = [l for l in result.result.split("\n") if l.startswith("@")]
        assert len(influencer_lines) == 3

    def test_empty_actions(self):
        result = identify_influencers([], top_n=5)
        assert "Top 5 influencers:" in result.result
