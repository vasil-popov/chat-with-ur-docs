"""Unit tests for the metric value objects and cost computation.

These run with NO live LLM. They lock in the cost formula, the JSON-serialisability
of RunMetrics, and the non-negative-input guard.
"""

from __future__ import annotations

import json

import pytest

from app.evaluation.metrics import RunMetrics, compute_cost


class TestComputeCost:
    def test_formula_matches_per_1k_pricing(self) -> None:
        # 2000 prompt tokens @ $0.01/1k + 1000 completion @ $0.03/1k.
        cost = compute_cost(2000, 1000, price_in_per_1k=0.01, price_out_per_1k=0.03)
        assert cost == pytest.approx(2 * 0.01 + 1 * 0.03)

    def test_zero_prices_yield_zero_cost(self) -> None:
        assert compute_cost(5000, 5000, 0.0, 0.0) == 0.0

    def test_zero_tokens_yield_zero_cost(self) -> None:
        assert compute_cost(0, 0, 0.01, 0.03) == 0.0

    def test_negative_prompt_tokens_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_cost(-1, 0, 0.01, 0.03)

    def test_negative_completion_tokens_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_cost(0, -1, 0.01, 0.03)

    def test_negative_price_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_cost(10, 10, -0.01, 0.03)


class TestRunMetricsToDict:
    def test_to_dict_is_json_serialisable_with_tool_args(self) -> None:
        metrics = RunMetrics(
            llm_call_count=2,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            tool_call_count=1,
            tools_called=[("log_expense", {"amount": 12.5, "category": "food"})],
            hops=3,
        )

        as_dict = metrics.to_dict()

        # json.dumps must not raise: tuples become lists in to_dict.
        encoded = json.dumps(as_dict)
        decoded = json.loads(encoded)
        assert decoded["tools_called"] == [
            ["log_expense", {"amount": 12.5, "category": "food"}]
        ]
        assert decoded["hops"] == 3

    def test_to_dict_empty_tools_is_serialisable(self) -> None:
        metrics = RunMetrics()
        json.dumps(metrics.to_dict())  # must not raise
