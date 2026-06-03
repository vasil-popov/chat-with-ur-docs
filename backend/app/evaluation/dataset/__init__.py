"""Golden benchmark dataset for thesis evaluation.

This package holds the annotated scenario set (``scenarios.yaml``), the Pydantic
v2 loader/validator (``loader.py``), the eval-DB seed/teardown helpers
(``seed.py``), and the sample RAG documents (``docs/``).

The dataset is the rule-based correctness backbone of the evaluation: every
expected ``tool_calls`` / ``args_expected`` value is ground truth that a scored
agent run is compared against. Keep expected values precise and grounded in the
real MCP / RAG tool signatures.
"""

from app.evaluation.dataset.loader import (
    KNOWN_TOOLS,
    Dataset,
    ExpectedOutcome,
    Scenario,
    ScenarioCategory,
    ToolCall,
    load_dataset,
    load_scenarios,
)

__all__ = [
    "KNOWN_TOOLS",
    "Dataset",
    "ExpectedOutcome",
    "Scenario",
    "ScenarioCategory",
    "ToolCall",
    "load_dataset",
    "load_scenarios",
]
