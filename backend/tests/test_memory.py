"""Tests for agent memory system."""

from app.services.simulation_v2.memory import AgentMemory, RelationshipMemory


class TestAgentMemory:
    def test_initial_state(self):
        mem = AgentMemory()
        assert mem.my_posts == []
        assert mem.relationships == {}
        assert mem.get_context_prompt() == "No memory yet \u2014 this is my first interaction."

    def test_record_post(self):
        mem = AgentMemory()
        mem.record_my_action(1, "post", "I love this!", sentiment="positive", score=0.8)
        assert len(mem.my_posts) == 1
        assert mem.my_posts[0] == "I love this!"
        assert mem.sentiment_history[0]["score"] == 0.8

    def test_record_post_truncates_content(self):
        mem = AgentMemory()
        long_content = "x" * 300
        mem.record_my_action(1, "post", long_content)
        assert len(mem.my_posts[0]) == 200

    def test_non_post_action_doesnt_add_to_posts(self):
        mem = AgentMemory()
        mem.record_my_action(1, "like", "", target_agent="Bob")
        assert len(mem.my_posts) == 0

    def test_relationship_tracking(self):
        mem = AgentMemory()
        mem.record_my_action(1, "like", "", target_agent="Alice")
        assert "Alice" in mem.relationships
        assert mem.relationships["Alice"].interactions == 1
        assert mem.relationships["Alice"].sentiment_toward == 0.2

    def test_relationship_sentiment_increases_on_positive_actions(self):
        mem = AgentMemory()
        mem.record_my_action(1, "like", "", target_agent="Alice")
        mem.record_my_action(2, "share", "", target_agent="Alice")
        mem.record_my_action(3, "reply", "great!", target_agent="Alice")
        assert mem.relationships["Alice"].interactions == 3
        assert mem.relationships["Alice"].sentiment_toward == pytest.approx(0.6)

    def test_relationship_sentiment_decreases_on_dislike(self):
        mem = AgentMemory()
        mem.record_my_action(1, "dislike", "", target_agent="Bob")
        assert mem.relationships["Bob"].sentiment_toward == -0.3

    def test_relationship_sentiment_clamped(self):
        mem = AgentMemory()
        for _ in range(10):
            mem.record_my_action(1, "like", "", target_agent="Alice")
        assert mem.relationships["Alice"].sentiment_toward <= 1.0

        mem2 = AgentMemory()
        for _ in range(10):
            mem2.record_my_action(1, "dislike", "", target_agent="Bob")
        assert mem2.relationships["Bob"].sentiment_toward >= -1.0

    def test_seen_posts_capped_at_20(self):
        mem = AgentMemory()
        for i in range(25):
            mem.record_seen_post(f"Agent-{i}", f"Post content {i}", round_num=1)
        assert len(mem.seen_posts) == 20

    def test_opinions_capped_at_10(self):
        mem = AgentMemory()
        for i in range(15):
            mem.add_opinion(f"Opinion {i}")
        assert len(mem.opinions) == 10

    def test_get_context_prompt_with_data(self):
        mem = AgentMemory()
        mem.record_my_action(1, "post", "First post!", sentiment="positive", score=0.5)
        mem.record_my_action(2, "reply", "I agree!", target_agent="Alice", sentiment="positive", score=0.7)
        mem.record_seen_post("Bob", "Some interesting take", round_num=1)
        prompt = mem.get_context_prompt()
        assert "MY PREVIOUS POSTS:" in prompt
        assert "First post!" in prompt
        assert "MY RELATIONSHIPS WITH OTHER USERS:" in prompt
        assert "@Alice" in prompt
        assert "RECENT POSTS I SAW:" in prompt

    def test_sentiment_trend_stable(self):
        mem = AgentMemory()
        mem.record_my_action(1, "post", "ok", sentiment="neutral", score=0.1)
        mem.record_my_action(2, "post", "ok", sentiment="neutral", score=0.2)
        assert mem.get_sentiment_trend() == "stable"

    def test_sentiment_trend_positive(self):
        mem = AgentMemory()
        mem.record_my_action(1, "post", "meh", sentiment="neutral", score=-0.2)
        mem.record_my_action(5, "post", "great!", sentiment="positive", score=0.5)
        assert mem.get_sentiment_trend() == "increasingly positive"

    def test_sentiment_trend_negative(self):
        mem = AgentMemory()
        mem.record_my_action(1, "post", "nice", sentiment="positive", score=0.5)
        mem.record_my_action(5, "post", "ugh", sentiment="negative", score=-0.3)
        assert mem.get_sentiment_trend() == "increasingly negative"

    def test_sentiment_trend_single_entry(self):
        mem = AgentMemory()
        mem.record_my_action(1, "post", "hello", sentiment="neutral", score=0.0)
        assert mem.get_sentiment_trend() == "stable"


# Need pytest for approx
import pytest
