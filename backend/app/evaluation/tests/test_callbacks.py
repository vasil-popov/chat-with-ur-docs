"""Unit tests for the metrics callback handler and the run wrapper.

No live LLM is used. Token extraction is exercised across every provider
field-name variant; tool-arg capture is regression-tested against FIX 2; and
``run_with_metrics`` is checked for config immutability via a tiny fake graph.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.evaluation.callbacks import (
    MetricsCallbackHandler,
    _extract_usage,
    _read_first_int,
    run_with_metrics,
)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class _FakeMessage:
    """Stand-in for a chat-model message carrying usage metadata."""

    def __init__(self, usage_metadata: dict[str, Any] | None) -> None:
        self.usage_metadata = usage_metadata
        self.response_metadata: dict[str, Any] = {}


class _FakeGeneration:
    def __init__(self, message: Any) -> None:
        self.message = message


class _FakeLLMResult:
    """Minimal LLMResult-shaped object: only attributes _extract_usage reads."""

    def __init__(
        self,
        usage_metadata: dict[str, Any] | None,
        llm_output: dict[str, Any] | None = None,
    ) -> None:
        self.llm_output = llm_output
        self.generations = [[_FakeGeneration(_FakeMessage(usage_metadata))]]


class TestTokenExtraction:
    def test_langchain_normalised_field_names(self) -> None:
        result = _FakeLLMResult(
            {"input_tokens": 30, "output_tokens": 12, "total_tokens": 42}
        )
        handler = MetricsCallbackHandler()
        _run(handler.on_llm_end(result))
        metrics = handler.build_metrics()
        assert metrics.prompt_tokens == 30
        assert metrics.completion_tokens == 12
        assert metrics.total_tokens == 42

    def test_gemini_field_names(self) -> None:
        result = _FakeLLMResult(
            {
                "prompt_token_count": 80,
                "candidates_token_count": 20,
                "total_token_count": 100,
            }
        )
        handler = MetricsCallbackHandler()
        _run(handler.on_llm_end(result))
        metrics = handler.build_metrics()
        assert metrics.prompt_tokens == 80
        assert metrics.completion_tokens == 20
        assert metrics.total_tokens == 100

    def test_openai_field_names(self) -> None:
        result = _FakeLLMResult(
            {"prompt_tokens": 15, "completion_tokens": 5},
            llm_output={
                "token_usage": {"prompt_tokens": 15, "completion_tokens": 5}
            },
        )
        handler = MetricsCallbackHandler()
        _run(handler.on_llm_end(result))
        metrics = handler.build_metrics()
        assert metrics.prompt_tokens == 15
        assert metrics.completion_tokens == 5
        # No provider total → fall back to prompt + completion.
        assert metrics.total_tokens == 20

    def test_missing_usage_records_zero_without_crash(self) -> None:
        result = _FakeLLMResult(None)
        handler = MetricsCallbackHandler()
        _run(handler.on_llm_end(result))
        metrics = handler.build_metrics()
        assert metrics.prompt_tokens == 0
        assert metrics.completion_tokens == 0
        assert metrics.total_tokens == 0

    def test_read_first_int_ignores_non_numeric(self) -> None:
        assert _read_first_int({"input_tokens": "oops"}, ("input_tokens",)) == 0
        assert _read_first_int({}, ("input_tokens",)) == 0

    def test_extract_usage_returns_none_when_absent(self) -> None:
        assert _extract_usage(_FakeLLMResult(None)) is None


class TestOnToolStart:
    def test_json_input_str_yields_full_args_dict(self) -> None:
        """Regression for FIX 2: args survive when only input_str is provided."""
        handler = MetricsCallbackHandler()
        _run(
            handler.on_tool_start(
                {"name": "log_expense"},
                '{"amount": 12.5, "category": "food"}',
            )
        )
        metrics = handler.build_metrics()
        assert metrics.tool_call_count == 1
        assert metrics.tools_called == [
            ("log_expense", {"amount": 12.5, "category": "food"})
        ]

    def test_structured_inputs_kwarg_is_preferred(self) -> None:
        handler = MetricsCallbackHandler()
        _run(
            handler.on_tool_start(
                {"name": "log_workout"},
                "ignored",
                inputs={"exercise": "squats", "reps": 10},
            )
        )
        assert handler.build_metrics().tools_called == [
            ("log_workout", {"exercise": "squats", "reps": 10})
        ]

    def test_non_json_input_str_falls_back_to_input_key(self) -> None:
        handler = MetricsCallbackHandler()
        _run(handler.on_tool_start({"name": "search"}, "plain text query"))
        assert handler.build_metrics().tools_called == [
            ("search", {"input": "plain text query"})
        ]


class TestHopCounting:
    def test_plumbing_names_are_excluded(self) -> None:
        handler = MetricsCallbackHandler()
        _run(handler.on_chain_start({"name": "RunnableSequence"}, {}))
        _run(handler.on_chain_start({"name": "supervisor"}, {}))
        _run(handler.on_chain_start({"name": "tracking"}, {}))
        _run(handler.on_chain_start({"name": "ChannelWrite"}, {}))
        assert handler.build_metrics().hops == 2

    def test_name_from_kwarg_is_honoured(self) -> None:
        handler = MetricsCallbackHandler()
        _run(handler.on_chain_start({}, {}, name="LangGraph"))
        _run(handler.on_chain_start({}, {}, name="agent"))
        assert handler.build_metrics().hops == 1


class _FakeGraph:
    """Records the config it was invoked with; never mutates the caller's dict."""

    def __init__(self) -> None:
        self.received_config: dict[str, Any] | None = None

    async def ainvoke(self, state: Any, config: dict[str, Any] | None = None) -> Any:
        self.received_config = config
        return {"messages": ["done"]}


class TestRunWithMetrics:
    def test_caller_config_is_not_mutated(self) -> None:
        graph = _FakeGraph()
        original_config = {"recursion_limit": 7, "callbacks": []}
        snapshot = {"recursion_limit": 7, "callbacks": []}

        _result, _metrics = _run(
            run_with_metrics(graph, {"messages": []}, original_config, 0.01, 0.03)
        )

        # Caller's dict is untouched; the handler was added only to the copy.
        assert original_config == snapshot

    def test_recursion_limit_is_preserved_and_handler_injected(self) -> None:
        graph = _FakeGraph()
        config = {"recursion_limit": 11}

        _run(run_with_metrics(graph, {"messages": []}, config, 0.0, 0.0))

        assert graph.received_config is not None
        assert graph.received_config["recursion_limit"] == 11
        callbacks = graph.received_config["callbacks"]
        assert isinstance(callbacks, list) and len(callbacks) == 1
        assert isinstance(callbacks[0], MetricsCallbackHandler)

    def test_works_when_config_is_none(self) -> None:
        graph = _FakeGraph()
        result, metrics = _run(
            run_with_metrics(graph, {"messages": []}, None, 0.0, 0.0)
        )
        assert result == {"messages": ["done"]}
        assert metrics.latency_total_ms >= 0.0

    def test_graph_recursion_error_marks_non_termination(self) -> None:
        """A GraphRecursionError is captured as data, not propagated."""

        class _RecursingGraph:
            async def ainvoke(self, state: Any, config: dict[str, Any] | None = None) -> Any:
                from langgraph.errors import GraphRecursionError

                raise GraphRecursionError("Recursion limit reached")

        result, metrics = _run(
            run_with_metrics(
                _RecursingGraph(), {"messages": []}, {"recursion_limit": 5}, 0.0, 0.0
            )
        )

        assert result is None
        assert metrics.non_termination is True
        assert metrics.latency_total_ms >= 0.0

    def test_non_recursion_exception_propagates(self) -> None:
        """Only GraphRecursionError is swallowed; other errors must surface."""

        class _ExplodingGraph:
            async def ainvoke(self, state: Any, config: dict[str, Any] | None = None) -> Any:
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            _run(
                run_with_metrics(
                    _ExplodingGraph(), {"messages": []}, None, 0.0, 0.0
                )
            )
