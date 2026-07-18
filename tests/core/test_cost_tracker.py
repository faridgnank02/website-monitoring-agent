from core.llm.cost_tracker import CostTracker
from core.llm.config import LLMResponse


def test_track_call_records_cost():
    tracker = CostTracker()
    resp = LLMResponse(
        model="m",
        content="c",
        usage={"prompt_tokens": 1000, "completion_tokens": 500},
        cost_input_per_1k=0.01,
        cost_output_per_1k=0.03,
        latency_ms=100.0,
        trace_id="run-1",
    )
    tracker.track("run-1", "parse", resp)
    summary = tracker.summary("run-1")
    assert summary["total_cost"] == 0.025
    assert summary["total_latency_ms"] == 100.0
    assert summary["calls"] == 1
