from core.llm.config import LLMResponse
from core.llm.cost_tracker import CostTracker, TrackedCall


def _make_response(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_input_per_1k: float = 0.01,
    cost_output_per_1k: float = 0.03,
    latency_ms: float = 100.0,
    model: str = "m",
) -> LLMResponse:
    usage = {}
    if prompt_tokens or completion_tokens:
        usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
    return LLMResponse(
        model=model,
        content="c",
        usage=usage,
        cost_input_per_1k=cost_input_per_1k,
        cost_output_per_1k=cost_output_per_1k,
        latency_ms=latency_ms,
        trace_id="run-1",
    )


def test_track_call_records_cost():
    tracker = CostTracker()
    resp = _make_response(
        prompt_tokens=1000,
        completion_tokens=500,
        latency_ms=100.0,
    )
    tracker.track("run-1", "parse", resp)
    summary = tracker.summary("run-1")
    assert summary["total_cost"] == 0.025
    assert summary["total_latency_ms"] == 100.0
    assert summary["calls"] == 1


def test_summary_without_run_id_returns_all_calls():
    tracker = CostTracker()
    tracker.track("run-1", "parse", _make_response(prompt_tokens=1000, completion_tokens=500))
    tracker.track("run-2", "analyze", _make_response(prompt_tokens=2000, completion_tokens=1000))
    summary = tracker.summary()
    assert summary["calls"] == 2
    assert summary["total_cost"] == 0.075
    assert summary["total_latency_ms"] == 200.0
    assert summary["total_prompt_tokens"] == 3000
    assert summary["total_completion_tokens"] == 1500


def test_summary_filters_by_run_id():
    tracker = CostTracker()
    tracker.track("run-1", "parse", _make_response(prompt_tokens=1000, completion_tokens=500))
    tracker.track("run-2", "analyze", _make_response(prompt_tokens=2000, completion_tokens=1000))
    tracker.track("run-1", "parse", _make_response(prompt_tokens=1000, completion_tokens=500))
    summary = tracker.summary("run-2")
    assert summary["calls"] == 1
    assert summary["total_cost"] == 0.05
    assert summary["total_latency_ms"] == 100.0
    assert summary["total_prompt_tokens"] == 2000
    assert summary["total_completion_tokens"] == 1000


def test_reset_clears_all_calls_when_no_run_id():
    tracker = CostTracker()
    tracker.track("run-1", "parse", _make_response())
    tracker.track("run-2", "analyze", _make_response())
    tracker.reset()
    assert tracker.summary()["calls"] == 0
    assert tracker._calls == []


def test_reset_run_id_removes_only_that_run():
    tracker = CostTracker()
    tracker.track("run-1", "parse", _make_response(prompt_tokens=1000))
    tracker.track("run-2", "analyze", _make_response(prompt_tokens=2000))
    tracker.track("run-1", "parse", _make_response(prompt_tokens=3000))
    tracker.reset("run-1")
    assert tracker.summary("run-2")["calls"] == 1
    assert tracker.summary("run-2")["total_prompt_tokens"] == 2000
    all_summary = tracker.summary()
    assert all_summary["calls"] == 1
    assert all_summary["total_prompt_tokens"] == 2000


def test_multiple_calls_aggregated_correctly():
    tracker = CostTracker()
    tracker.track("run-1", "parse", _make_response(prompt_tokens=1000, completion_tokens=500))
    tracker.track("run-1", "analyze", _make_response(prompt_tokens=2000, completion_tokens=1000))
    tracker.track("run-1", "report", _make_response(prompt_tokens=3000, completion_tokens=1500))
    summary = tracker.summary("run-1")
    assert summary["calls"] == 3
    assert summary["total_cost"] == 0.15
    assert summary["total_latency_ms"] == 300.0
    assert summary["total_prompt_tokens"] == 6000
    assert summary["total_completion_tokens"] == 3000


def test_edge_case_zero_latency_and_empty_usage():
    tracker = CostTracker()
    resp = LLMResponse(
        model="m",
        content="c",
        usage={},
        cost_input_per_1k=0.01,
        cost_output_per_1k=0.03,
        latency_ms=0.0,
        trace_id="run-1",
    )
    tracker.track("run-1", "parse", resp)
    summary = tracker.summary("run-1")
    assert summary["calls"] == 1
    assert summary["total_cost"] == 0.0
    assert summary["total_latency_ms"] == 0.0
    assert summary["total_prompt_tokens"] == 0
    assert summary["total_completion_tokens"] == 0


def test_total_prompt_and_completion_tokens():
    tracker = CostTracker()
    tracker.track("run-1", "parse", _make_response(prompt_tokens=1000, completion_tokens=500))
    tracker.track("run-1", "analyze", _make_response(prompt_tokens=2500, completion_tokens=1200))
    summary = tracker.summary("run-1")
    assert summary["total_prompt_tokens"] == 3500
    assert summary["total_completion_tokens"] == 1700


def test_tracked_call_shape_and_defaults():
    call = TrackedCall(
        run_id="run-1",
        task="parse",
        model="m",
        cost=0.025,
        latency_ms=100.0,
        prompt_tokens=1000,
        completion_tokens=500,
    )
    assert call.run_id == "run-1"
    assert call.task == "parse"
    assert call.model == "m"
    assert call.cost == 0.025
    assert call.latency_ms == 100.0
    assert call.prompt_tokens == 1000
    assert call.completion_tokens == 500
