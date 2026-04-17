"""Tests for simulation engine (rule-based agents, crowd pulse, state management)."""

import random

from app.services.simulation_v2.engine import (
    AgentProfile, Action, _rule_agent_act, _build_crowd_pulse,
    simulation_states, get_simulation_state, cleanup_simulation_state,
)


def _make_profile(
    name="TestAgent", personality="Average user", usage="moderate",
) -> AgentProfile:
    return AgentProfile(
        name=name, age=25, gender="female", occupation="Student",
        interests=["music", "tech"], personality=personality,
        social_media_usage=usage, is_llm=False,
    )


def _make_action(
    round_num=1, agent_name="Agent-1", action_type="post",
    content="test", sentiment="positive", sentiment_score=0.5,
    target_agent="",
) -> Action:
    return Action(
        round_num=round_num, agent_name=agent_name,
        agent_profile={"name": agent_name, "age": 25},
        action_type=action_type, content=content,
        target_agent=target_agent, sentiment=sentiment,
        sentiment_score=sentiment_score,
    )


class TestRuleAgentAct:
    def test_returns_action(self):
        profile = _make_profile()
        random.seed(42)
        action = _rule_agent_act(profile, round_num=1, feed=[])
        assert isinstance(action, Action)
        assert action.agent_name == "TestAgent"
        assert action.round_num == 1

    def test_heavy_users_engage_more(self):
        profile = _make_profile(usage="heavy")
        random.seed(0)
        engaged = 0
        for _ in range(100):
            action = _rule_agent_act(profile, 1, [])
            if action.action_type != "ignore":
                engaged += 1
        assert engaged > 60  # 80% engage probability

    def test_light_users_engage_less(self):
        profile = _make_profile(usage="light")
        random.seed(0)
        engaged = 0
        for _ in range(100):
            action = _rule_agent_act(profile, 1, [])
            if action.action_type != "ignore":
                engaged += 1
        assert engaged < 40  # 20% engage probability

    def test_fan_personality_tends_positive(self):
        profile = _make_profile(personality="Enthusiastic fan who loves this")
        random.seed(42)
        scores = []
        for _ in range(50):
            action = _rule_agent_act(profile, 1, [])
            if action.action_type != "ignore":
                scores.append(action.sentiment_score)
        if scores:
            avg = sum(scores) / len(scores)
            assert avg > 0.0  # Should trend positive

    def test_critical_personality_tends_negative(self):
        profile = _make_profile(personality="Critical skeptic who questions everything")
        random.seed(42)
        scores = []
        for _ in range(50):
            action = _rule_agent_act(profile, 1, [])
            if action.action_type != "ignore":
                scores.append(action.sentiment_score)
        if scores:
            avg = sum(scores) / len(scores)
            assert avg < 0.3  # Should trend less positive

    def test_reply_gets_target_from_feed(self):
        profile = _make_profile(usage="heavy")
        feed = [_make_action(agent_name="Alice", content="Great post!")]
        random.seed(1)
        # Run multiple times to get a reply action
        for _ in range(100):
            action = _rule_agent_act(profile, 1, feed)
            if action.action_type in ("reply", "share") and action.target_agent:
                assert action.target_agent == "Alice"
                break

    def test_rule_agents_dont_generate_text(self):
        profile = _make_profile(usage="heavy")
        random.seed(42)
        for _ in range(20):
            action = _rule_agent_act(profile, 1, [])
            assert action.content == ""


class TestBuildCrowdPulse:
    def test_empty_first_round(self):
        result = _build_crowd_pulse([], [], round_num=1)
        assert result == ""

    def test_generates_pulse_with_actions(self):
        rule_actions = [
            _make_action(action_type="like", sentiment="positive", sentiment_score=0.5),
            _make_action(action_type="share", sentiment="positive", sentiment_score=0.7, target_agent="Popular"),
            _make_action(action_type="dislike", sentiment="negative", sentiment_score=-0.5),
        ]
        result = _build_crowd_pulse(rule_actions, rule_actions, round_num=2)
        assert "CROWD PULSE" in result
        assert "1 liked" in result
        assert "1 shared" in result
        assert "1 disliked" in result

    def test_sentiment_trend_detection(self):
        prev_actions = [
            _make_action(round_num=1, sentiment="negative", sentiment_score=-0.5),
        ]
        current_actions = [
            _make_action(round_num=2, sentiment="positive", sentiment_score=0.8),
        ]
        all_actions = prev_actions + current_actions
        result = _build_crowd_pulse(current_actions, all_actions, round_num=2)
        assert "rising" in result


class TestSimulationState:
    def test_get_unknown_state(self):
        state = get_simulation_state("nonexistent-id")
        assert state["status"] == "unknown"

    def test_set_and_get_state(self):
        simulation_states["test-1"] = {"status": "running", "current_round": 3}
        state = get_simulation_state("test-1")
        assert state["status"] == "running"
        assert state["current_round"] == 3
        # Cleanup
        cleanup_simulation_state("test-1")

    def test_cleanup_removes_state(self):
        simulation_states["test-2"] = {"status": "completed"}
        cleanup_simulation_state("test-2")
        assert get_simulation_state("test-2")["status"] == "unknown"

    def test_cleanup_nonexistent_is_safe(self):
        cleanup_simulation_state("never-existed")  # Should not raise
