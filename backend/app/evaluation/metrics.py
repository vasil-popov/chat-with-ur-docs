from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

# Token accounting is done per 1,000 tokens because that is the unit vendors
# quote pricing in; keeping the divisor named avoids a magic literal in the
# cost formula.
TOKENS_PER_PRICING_UNIT = 1000


@dataclass
class RunMetrics:
    """Efficiency metrics captured for a single agent run.

    Token counts are summed across EVERY LLM invocation in the run. For the
    supervisor arm that includes the router's ``with_structured_output`` call as
    well as each specialist ReAct call, because callbacks propagate to all child
    runnables in the LangGraph execution.
    """

    latency_total_ms: float = 0.0
    latency_ttft_ms: float | None = None
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    est_cost_usd: float = 0.0
    tool_call_count: int = 0
    # Ordered (tool_name, args) pairs; a downstream scorer inspects the full args
    # dict for per-parameter argument-extraction checking, so args are kept whole.
    tools_called: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    # Best-effort count of LangGraph super-steps / chain-node transitions taken.
    # Approximated by the number of chain-node starts the handler observed; see
    # MetricsCallbackHandler.on_chain_start for the exact counting rule.
    hops: int = 0
    # Ordered, duplicate-preserving list of the non-plumbing graph-node names the
    # run entered (e.g. "supervisor", "tracking", "rag", "general", or the ReAct
    # "agent"/"tools" nodes). Phase 4 derives the supervisor's actual route from
    # the first specialist name appearing here.
    nodes_visited: list[str] = field(default_factory=list)
    # Marks a run that hit the graph recursion limit without terminating (i.e. it
    # never produced a final answer and was aborted by GraphRecursionError). Such
    # runs are scored as failures rather than excluded as errors.
    non_termination: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict (tuples become lists)."""
        return {
            "latency_total_ms": self.latency_total_ms,
            "latency_ttft_ms": self.latency_ttft_ms,
            "llm_call_count": self.llm_call_count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "est_cost_usd": self.est_cost_usd,
            "tool_call_count": self.tool_call_count,
            "tools_called": [
                [name, args] for name, args in self.tools_called
            ],
            "hops": self.hops,
            "nodes_visited": list(self.nodes_visited),
            "non_termination": self.non_termination,
        }


def compute_cost(
    prompt_tokens: int,
    completion_tokens: int,
    price_in_per_1k: float,
    price_out_per_1k: float,
) -> float:
    """Estimate USD cost from token counts and per-1k prices.

    Cost = prompt_tokens/1000 * price_in + completion_tokens/1000 * price_out.
    Prices are supplied by the caller (sourced from Settings at the call site);
    no price is hardcoded here.
    """
    if prompt_tokens < 0 or completion_tokens < 0:
        raise ValueError("Token counts must be non-negative.")
    if price_in_per_1k < 0 or price_out_per_1k < 0:
        raise ValueError("Prices must be non-negative.")

    prompt_cost = (prompt_tokens / TOKENS_PER_PRICING_UNIT) * price_in_per_1k
    completion_cost = (completion_tokens / TOKENS_PER_PRICING_UNIT) * price_out_per_1k
    return prompt_cost + completion_cost


def append_run_metrics(path: str, record: dict[str, Any]) -> None:
    """Append one record as a single JSON line to ``path`` (JSONL).

    Creates parent directories if missing. Safe to call repeatedly: the file is
    opened in append mode, so each call adds exactly one line and never truncates
    prior runs. Append-only and NOT safe for concurrent writers; the experiment
    is assumed to run sequentially.
    """
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
