"""LangChain callback handler that captures per-run efficiency metrics.

How the supervisor router LLM call is counted
---------------------------------------------
A callback handler passed via ``config={"callbacks": [handler]}`` to a compiled
LangGraph graph propagates to EVERY child runnable that runs under that config —
including the supervisor's ``router_llm = llm.with_structured_output(...)`` call
inside ``supervisor_node``. That routing call is a chat-model invocation, so it
fires ``on_chat_model_start`` and ``on_llm_end`` exactly like the specialist
ReAct calls. We therefore never special-case routing: counting every chat-model
start automatically includes the router. On a single-domain query the supervisor
arm reports one extra LLM call (the route decision) plus the FINISH-route call,
which is precisely the routing overhead the thesis sets out to measure.

Chat models emit ``on_chat_model_start`` (NOT ``on_llm_start``). Gemini is a chat
model, so we override both hooks and increment on each. The two hooks are
mutually exclusive for a given invocation in LangChain, so handling both counts
chat and (hypothetical) completion models without double-counting.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from app.evaluation.metrics import RunMetrics, compute_cost

logger = logging.getLogger(__name__)

# LangGraph/Runnable plumbing chain names that wrap or sit between graph nodes.
# Excluding these from the hop count leaves only actual graph-node entries
# (supervisor, tracking, rag, general, the ReAct "agent"/"tools" nodes, etc.),
# giving a defensible super-step approximation. Mirrors the plumbing subset of
# chat_service._INTERNAL_NAMES (kept local to avoid a service->evaluation import).
_HOP_PLUMBING_NAMES = frozenset({
    "LangGraph", "RunnableSequence", "RunnableLambda", "RunnableParallel",
    "__start__", "__end__", "ChatPromptTemplate", "ChannelWrite",
    "ChannelRead", "ToolNode",
})

# Field-name variants seen across providers. Gemini reports prompt/candidates/
# total_token_count; OpenAI-style reports prompt_tokens/completion_tokens;
# LangChain's normalised usage_metadata reports input_tokens/output_tokens.
_PROMPT_KEYS = ("input_tokens", "prompt_tokens", "prompt_token_count")
_COMPLETION_KEYS = ("output_tokens", "completion_tokens", "candidates_token_count")
_TOTAL_KEYS = ("total_tokens", "total_token_count")


def _read_first_int(source: dict[str, Any], keys: tuple[str, ...]) -> int:
    """Return the first present, int-coercible value among ``keys``, else 0."""
    for key in keys:
        value = source.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _extract_usage(response: LLMResult) -> dict[str, Any] | None:
    """Find a token-usage dict from an LLMResult, defensively.

    Priority: llm_output["usage_metadata"], then the message's usage_metadata,
    then response_metadata["usage_metadata"]/["token_usage"]. Returns None when
    nothing usable is found so the caller can record zero without crashing.
    """
    llm_output = response.llm_output or {}
    if isinstance(llm_output, dict):
        usage = llm_output.get("usage_metadata") or llm_output.get("token_usage")
        if isinstance(usage, dict):
            return usage

    for generations in response.generations:
        for generation in generations:
            message = getattr(generation, "message", None)
            if message is None:
                continue
            usage = getattr(message, "usage_metadata", None)
            if isinstance(usage, dict):
                return usage
            metadata = getattr(message, "response_metadata", None) or {}
            if isinstance(metadata, dict):
                usage = metadata.get("usage_metadata") or metadata.get("token_usage")
                if isinstance(usage, dict):
                    return usage
    return None


class MetricsCallbackHandler(AsyncCallbackHandler):
    """Accumulates metrics for ONE run. Never share an instance across runs.

    The handler is stateful: each hook mutates internal counters. A fresh handler
    must be created per run (``run_with_metrics`` does this) so counts from
    different runs never bleed into one another.
    """

    def __init__(self) -> None:
        self._llm_call_count = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_tokens = 0
        self._tool_call_count = 0
        self._tools_called: list[tuple[str, dict[str, Any]]] = []
        self._chain_starts = 0
        self._first_token_perf: float | None = None
        self._run_start_perf: float | None = None

    async def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[BaseMessage]], **kwargs: Any) -> None:
        """Count a chat-model invocation (Gemini, and the supervisor router)."""
        self._llm_call_count += 1

    async def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Count a completion-model invocation (non-chat models)."""
        self._llm_call_count += 1

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Record the monotonic time of the FIRST streamed content token only."""
        if self._first_token_perf is None:
            self._first_token_perf = time.perf_counter()

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Add this call's token usage to the running totals (defensively)."""
        usage = _extract_usage(response)
        if usage is None:
            return
        self._prompt_tokens += _read_first_int(usage, _PROMPT_KEYS)
        self._completion_tokens += _read_first_int(usage, _COMPLETION_KEYS)
        self._total_tokens += _read_first_int(usage, _TOTAL_KEYS)

    async def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> None:
        """Record an ordered (tool_name, args) pair and bump the tool count.

        Prefer the structured ``inputs`` kwarg when LangChain supplies it; if it is
        absent, parse the JSON ``input_str`` so the full argument dict is preserved
        for downstream per-parameter argument-extraction scoring.
        """
        name = (serialized or {}).get("name", "unknown")
        inputs = kwargs.get("inputs")
        if isinstance(inputs, dict):
            args = dict(inputs)
        else:
            try:
                parsed = json.loads(input_str)
                args = parsed if isinstance(parsed, dict) else {"input": input_str}
            except (json.JSONDecodeError, TypeError):
                args = {"input": input_str}
        self._tools_called.append((name, args))
        self._tool_call_count += 1

    async def on_chain_start(self, serialized: dict[str, Any], inputs: Any, *, run_id: UUID | None = None, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        """Count graph-node entries as a best-effort ``hops`` approximation.

        Each ``on_chain_start`` is counted unless its name is LangGraph/Runnable
        plumbing (see ``_HOP_PLUMBING_NAMES``). What remains are actual graph-node
        entries (supervisor, tracking, rag, general, the ReAct agent/tools nodes),
        which approximate the number of super-steps the run took. The chain name
        can arrive on ``serialized["name"]`` or as the run ``name`` kwarg, so both
        are checked. This is an approximation, documented as such on RunMetrics.
        """
        name = (serialized or {}).get("name") or kwargs.get("name")
        if name in _HOP_PLUMBING_NAMES:
            return
        self._chain_starts += 1

    def build_metrics(self) -> RunMetrics:
        """Return a RunMetrics with everything the handler observed.

        Latency totals are NOT set here; the runner owns wall-clock timing. TTFT
        is filled in only if a first token was seen and a run start was recorded.
        Token totals fall back to prompt+completion when no provider total was
        reported, so total_tokens stays consistent.
        """
        prompt_plus_completion = self._prompt_tokens + self._completion_tokens
        if self._total_tokens == 0 and prompt_plus_completion > 0:
            logger.warning(
                "Provider returned no aggregate total_tokens; falling back to "
                "prompt+completion sum (%d).",
                prompt_plus_completion,
            )
        total = self._total_tokens or prompt_plus_completion
        ttft_ms = self._compute_ttft_ms()
        return RunMetrics(
            latency_ttft_ms=ttft_ms,
            llm_call_count=self._llm_call_count,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            total_tokens=total,
            tool_call_count=self._tool_call_count,
            tools_called=list(self._tools_called),
            hops=self._chain_starts,
        )

    def mark_run_start(self, perf_now: float) -> None:
        """Record the run start instant so TTFT can be derived from it."""
        self._run_start_perf = perf_now

    def _compute_ttft_ms(self) -> float | None:
        if self._first_token_perf is None or self._run_start_perf is None:
            return None
        return (self._first_token_perf - self._run_start_perf) * 1000.0


def _merge_callbacks(config: dict[str, Any] | None, handler: MetricsCallbackHandler) -> dict[str, Any]:
    """Return a deep-ish copy of ``config`` with ``handler`` added to callbacks.

    The caller's dict is never mutated. Existing callbacks and keys such as
    ``recursion_limit`` are preserved.
    """
    merged = copy.copy(config) if config else {}
    existing = merged.get("callbacks")
    if isinstance(existing, list):
        merged["callbacks"] = [*existing, handler]
    elif existing is None:
        merged["callbacks"] = [handler]
    else:
        # A CallbackManager or BaseCallbackHandler was passed; wrap into a list.
        merged["callbacks"] = [existing, handler]
    return merged


async def run_with_metrics(
    graph: Any,
    state: Any,
    config: dict[str, Any] | None,
    price_in_per_1k: float,
    price_out_per_1k: float,
) -> tuple[Any, RunMetrics]:
    """Invoke ``graph`` once and return ``(result, populated RunMetrics)``.

    A fresh handler is created per call (handlers are stateful). The handler is
    merged into a copy of ``config`` so the caller's dict — including
    ``recursion_limit`` — is left untouched. Wall-clock latency and estimated
    cost are filled in here; the handler supplies the rest.
    """
    handler = MetricsCallbackHandler()
    merged_config = _merge_callbacks(config, handler)

    start_perf = time.perf_counter()
    handler.mark_run_start(start_perf)
    result = await graph.ainvoke(state, config=merged_config)
    end_perf = time.perf_counter()

    metrics = handler.build_metrics()
    metrics.latency_total_ms = (end_perf - start_perf) * 1000.0
    metrics.est_cost_usd = compute_cost(
        metrics.prompt_tokens,
        metrics.completion_tokens,
        price_in_per_1k,
        price_out_per_1k,
    )
    return result, metrics
