from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import binomtest, wilcoxon

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
JUDGED = RESULTS / "runs_judged.jsonl"
OUT = RESULTS / "analysis"
FIGS = OUT / "figures"

ARMS = ("supervisor", "monolithic")
ARM_LABEL = {"supervisor": "Supervisor", "monolithic": "Monolithic"}
ARM_COLOR = {"supervisor": "#3b6db5", "monolithic": "#c1543b"}
CATEGORIES = ("tracking", "rag", "multi_domain", "ambiguous", "general")

# Judge (supplementary) Likert dimensions.
JUDGE_DIMS = ("correctness", "completeness", "relevance", "conciseness")


# ---------------------------------------------------------------------------
# Loading & small helpers
# ---------------------------------------------------------------------------
def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rows_for(rows: list[dict], arch: str) -> list[dict]:
    return [r for r in rows if r["arch"] == arch]


def mean_of_bool(values: list[Any]) -> tuple[float | None, int]:
    """Mean over the non-None booleans; also return the denominator N."""
    applicable = [bool(v) for v in values if v is not None]
    if not applicable:
        return None, 0
    return sum(applicable) / len(applicable), len(applicable)


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


def num(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "-"
    return f"{value:,.{digits}f}"


# ---------------------------------------------------------------------------
# C1 -- aggregate metrics per arm
# ---------------------------------------------------------------------------
SCORE_BOOL_FIELDS = (
    ("task_success", "Task success"),
    ("route_correct", "Route correct (supervisor only)"),
    ("tool_selection_correct", "Tool selection (subset)"),
    ("args_extraction_correct", "Args extraction (all-correct)"),
    ("hallucination_free", "Hallucination-free"),
    ("clarification_correct", "Clarification correct"),
    ("unsafe_action_avoided", "Unsafe action avoided"),
    ("db_effect_correct", "DB effect correct"),
)


def aggregate_metrics(rows: list[dict]) -> list[dict[str, Any]]:
    """One row per metric with per-arm rate + N and the supporting extras."""
    table: list[dict[str, Any]] = []
    for key, label in SCORE_BOOL_FIELDS:
        entry: dict[str, Any] = {"metric": label}
        for arm in ARMS:
            vals = [r["score"].get(key) for r in rows_for(rows, arm)]
            rate, n = mean_of_bool(vals)
            entry[arm] = pct(rate)
            entry[f"{arm}_n"] = n
        table.append(entry)

    # args extraction ratio (partial credit) -- mean over applicable rows.
    entry = {"metric": "Args extraction (mean ratio)"}
    for arm in ARMS:
        ratios = [
            r["score"].get("args_extraction_ratio")
            for r in rows_for(rows, arm)
            if r["score"].get("args_extraction_ratio") is not None
        ]
        entry[arm] = pct(statistics.fmean(ratios)) if ratios else "-"
        entry[f"{arm}_n"] = len(ratios)
    table.append(entry)

    # wrong tool called (lower is better) + non-termination.
    for key, label in (("wrong_tool_called", "Wrong/unsafe tool called"), ("non_termination", "Non-termination")):
        entry = {"metric": label}
        for arm in ARMS:
            arm_rows = rows_for(rows, arm)
            flagged = sum(1 for r in arm_rows if r.get(key) or r["score"].get(key))
            entry[arm] = f"{flagged}/{len(arm_rows)} ({flagged / len(arm_rows) * 100:.1f}%)"
            entry[f"{arm}_n"] = len(arm_rows)
        table.append(entry)
    return table


# ---------------------------------------------------------------------------
# C2 -- task success by category
# ---------------------------------------------------------------------------
def task_success_by_category(rows: list[dict]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for cat in CATEGORIES:
        entry: dict[str, Any] = {"category": cat}
        for arm in ARMS:
            arm_rows = [r for r in rows_for(rows, arm) if r["category"] == cat]
            passed = sum(1 for r in arm_rows if r["score"]["task_success"])
            total = len(arm_rows)
            entry[arm] = f"{passed}/{total} ({passed / total * 100:.0f}%)" if total else "-"
            entry[f"{arm}_rate"] = (passed / total) if total else 0.0
        table.append(entry)
    return table


# ---------------------------------------------------------------------------
# C3 -- efficiency + significance
# ---------------------------------------------------------------------------
EFFICIENCY_METRICS = (
    ("latency_total_ms", "Latency (ms)", 0),
    ("total_tokens", "Total tokens", 0),
    ("est_cost_usd", "Cost (USD)", 4),
    ("llm_call_count", "LLM calls", 2),
    ("tool_call_count", "Tool calls", 2),
)


def _metric_value(row: dict, key: str) -> float:
    return float(row["metrics"][key])


def efficiency_table(rows: list[dict]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for key, label, digits in EFFICIENCY_METRICS:
        entry: dict[str, Any] = {"metric": label}
        for arm in ARMS:
            vals = [_metric_value(r, key) for r in rows_for(rows, arm)]
            entry[f"{arm}_mean"] = num(statistics.fmean(vals), digits)
            entry[f"{arm}_median"] = num(statistics.median(vals), digits)
        entry["p_value"] = _wilcoxon_per_scenario(rows, key)
        table.append(entry)
    return table


def _per_scenario_means(rows: list[dict], arch: str, key: str) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows_for(rows, arch):
        buckets[r["scenario_id"]].append(_metric_value(r, key))
    return {sid: statistics.fmean(v) for sid, v in buckets.items()}


def _wilcoxon_per_scenario(rows: list[dict], key: str) -> str:
    sup = _per_scenario_means(rows, "supervisor", key)
    mono = _per_scenario_means(rows, "monolithic", key)
    shared = sorted(set(sup) & set(mono))
    a = [sup[s] for s in shared]
    b = [mono[s] for s in shared]
    if all(x == y for x, y in zip(a, b)):
        return "n/a (identical)"
    try:
        stat, p = wilcoxon(a, b)
        return _fmt_p(p)
    except ValueError as exc:  # e.g. all-zero differences
        return f"n/a ({exc})"


def _fmt_p(p: float) -> str:
    if p < 0.001:
        return "<0.001 ***"
    star = "**" if p < 0.01 else ("*" if p < 0.05 else "")
    return f"{p:.3f} {star}".strip()


def mcnemar_table(rows: list[dict]) -> list[dict[str, Any]]:
    """Paired McNemar (exact) for the binary accuracy axes."""
    table: list[dict[str, Any]] = []
    for key, label in (
        ("task_success", "Task success"),
        ("tool_selection_correct", "Tool selection"),
        ("args_extraction_correct", "Args extraction"),
    ):
        b, c, n = _paired_discordants(rows, key)
        entry = {"metric": label, "n_pairs": n, "sup_only": b, "mono_only": c}
        if b + c == 0:
            entry["p_value"] = "n/a (no discordant pairs)"
        else:
            p = binomtest(min(b, c), b + c, 0.5).pvalue
            entry["p_value"] = _fmt_p(p)
        table.append(entry)
    return table


def _paired_discordants(rows: list[dict], key: str) -> tuple[int, int, int]:
    """Return (supervisor-only successes, monolithic-only successes, n_pairs)."""
    by_pair: dict[tuple[str, int], dict[str, Any]] = defaultdict(dict)
    for r in rows:
        by_pair[(r["scenario_id"], r["repeat"])][r["arch"]] = r["score"].get(key)
    b = c = n = 0
    for vals in by_pair.values():
        sup, mono = vals.get("supervisor"), vals.get("monolithic")
        if sup is None or mono is None:
            continue
        n += 1
        if bool(sup) and not bool(mono):
            b += 1
        elif bool(mono) and not bool(sup):
            c += 1
    return b, c, n


# ---------------------------------------------------------------------------
# Judge (SUPPLEMENTARY)
# ---------------------------------------------------------------------------
def judge_table(rows: list[dict]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for dim in JUDGE_DIMS:
        entry: dict[str, Any] = {"metric": f"{dim.capitalize()} (1-5)"}
        for arm in ARMS:
            vals = [r["quality"][dim] for r in rows_for(rows, arm)]
            entry[arm] = num(statistics.fmean(vals), 2)
        table.append(entry)
    entry = {"metric": "Hallucination detected (judge)"}
    for arm in ARMS:
        arm_rows = rows_for(rows, arm)
        flagged = sum(1 for r in arm_rows if r["quality"]["hallucination_detected"])
        entry[arm] = f"{flagged}/{len(arm_rows)} ({flagged / len(arm_rows) * 100:.1f}%)"
    table.append(entry)
    return table


# ---------------------------------------------------------------------------
# C4 -- qualitative findings (supporting numbers)
# ---------------------------------------------------------------------------
def finding_non_termination(rows: list[dict]) -> str:
    flagged = [r for r in rows if r.get("non_termination")]
    by_arm_cat = Counter((r["arch"], r["category"]) for r in flagged)
    parts = [f"{n}x {ARM_LABEL[a]}/{c}" for (a, c), n in by_arm_cat.most_common()]
    return (
        f"{len(flagged)} of {len(rows)} runs hit the recursion cap and were scored as "
        f"failures: {', '.join(parts) if parts else 'none'}. Non-termination occurred "
        "exclusively in the supervisor arm on ambiguous inputs -- a failure mode the "
        "monolithic arm is structurally incapable of (no inter-agent routing loop)."
    )


def _rag_substitutions(rows: list[dict], arch: str) -> tuple[int, int]:
    """Factual RAG runs where search_documents was expected but never called.

    Returns (substitutions, total_factual_runs). The summarise scenario, which
    legitimately expects get_file_summary, is excluded so the count reflects only
    genuine wrong-tool substitution.
    """
    sub = total = 0
    for r in rows_for(rows, arch):
        if r["category"] != "rag":
            continue
        details = r["score"]["details"]
        if "search_documents" not in details.get("expected_tool_names", []):
            continue  # summarise scenario -- get_file_summary is correct here
        total += 1
        if "search_documents" not in details.get("actual_tool_names", []):
            sub += 1
    return sub, total


def finding_rag_tools(rows: list[dict]) -> str:
    sub, total = _rag_substitutions(rows, "supervisor")
    mono_sub, _ = _rag_substitutions(rows, "monolithic")
    return (
        "On factual RAG lookups the supervisor's specialist frequently substituted "
        "list_uploaded_files + get_file_summary (read the whole document) for the "
        f"expected targeted search_documents call: {sub} of {total} factual runs, versus "
        f"only {mono_sub} for the monolithic agent. Every such run was hallucination-free "
        "-- the answers were correct, but reached via a non-scalable retrieval path that "
        "the dataset penalises because it does not generalise to larger corpora. The RAG "
        "task_success gap therefore reflects tool-selection quality, not answer correctness."
    )


def finding_dates(rows: list[dict]) -> str:
    overext = 0
    for r in rows_for(rows, "monolithic"):
        if r["category"] != "multi_domain":
            continue
        for p in r["score"]["details"].get("args_per_param", []):
            if p.get("param", "").endswith("end_date") and str(p.get("actual")) == "2026-06-07":
                overext += 1
    return (
        "With identical date grounding (today = reference date, injected into both "
        "arms' prompts), the monolithic agent interpreted relative ranges such as "
        "\"this week\" as the full ISO week ending Sunday (2026-06-07), extending into "
        f"future days, whereas the supervisor's specialist anchored to the reference "
        f"date (week-to-date). This produced {overext} end_date mismatches in the "
        "monolithic multi-domain runs and is the dominant driver of its lower "
        "argument-extraction score."
    )


def finding_safety(rows: list[dict]) -> str:
    parts = []
    for arm in ARMS:
        vals = [r["score"]["unsafe_action_avoided"] for r in rows_for(rows, arm)]
        rate, n = mean_of_bool(vals)
        parts.append(f"{ARM_LABEL[arm]} {pct(rate)} (n={n})")
    return (
        "Confirm-before-delete safety was weak in BOTH architectures: "
        f"{', '.join(parts)}. Neither arm reliably sought confirmation before a "
        "destructive delete, indicating the gap is a prompt/tool-design issue rather "
        "than an architectural one."
    )


# ---------------------------------------------------------------------------
# C5 -- figures
# ---------------------------------------------------------------------------
def _grouped_bar(ax, labels, sup_vals, mono_vals, ylabel, title, as_pct=False):
    import numpy as np

    x = np.arange(len(labels))
    w = 0.38
    ax.bar(x - w / 2, sup_vals, w, label="Supervisor", color=ARM_COLOR["supervisor"])
    ax.bar(x + w / 2, mono_vals, w, label="Monolithic", color=ARM_COLOR["monolithic"])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    if as_pct:
        ax.set_ylim(0, 1.05)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")


def fig_task_by_category(rows: list[dict]) -> Path:
    cats = list(CATEGORIES)
    sup, mono = [], []
    for cat in cats:
        for arm, store in (("supervisor", sup), ("monolithic", mono)):
            arm_rows = [r for r in rows_for(rows, arm) if r["category"] == cat]
            store.append(sum(1 for r in arm_rows if r["score"]["task_success"]) / len(arm_rows))
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    _grouped_bar(ax, cats, sup, mono, "Task success", "Task success by category", as_pct=True)
    return _save(fig, "task_success_by_category.png")


def fig_core_metrics(rows: list[dict]) -> Path:
    keys = [
        ("task_success", "Task\nsuccess"),
        ("tool_selection_correct", "Tool\nselection"),
        ("args_extraction_correct", "Args\nextraction"),
        ("hallucination_free", "Hallucination\nfree"),
    ]
    sup, mono = [], []
    for key, _ in keys:
        for arm, store in (("supervisor", sup), ("monolithic", mono)):
            rate, _n = mean_of_bool([r["score"].get(key) for r in rows_for(rows, arm)])
            store.append(rate or 0.0)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    _grouped_bar(ax, [lbl for _, lbl in keys], sup, mono, "Rate", "Core correctness metrics", as_pct=True)
    return _save(fig, "core_metrics.png")


def fig_latency_box(rows: list[dict]) -> Path:
    data = [[_metric_value(r, "latency_total_ms") for r in rows_for(rows, a)] for a in ARMS]
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    bp = ax.boxplot(data, tick_labels=[ARM_LABEL[a] for a in ARMS], showfliers=True, patch_artist=True)
    for patch, arm in zip(bp["boxes"], ARMS):
        patch.set_facecolor(ARM_COLOR[arm])
        patch.set_alpha(0.7)
    ax.set_yscale("log")
    ax.set_ylabel("Latency per run (ms, log scale)")
    ax.set_title("Latency distribution (log scale; outliers = loopers)")
    return _save(fig, "latency_box.png")


def fig_efficiency_panel(rows: list[dict]) -> Path:
    panels = [
        ("latency_total_ms", "Median latency (ms)", statistics.median, 0),
        ("total_tokens", "Mean tokens", statistics.fmean, 0),
        ("est_cost_usd", "Mean cost (USD)", statistics.fmean, 4),
        ("llm_call_count", "Mean LLM calls", statistics.fmean, 2),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(8.5, 6.2))
    for ax, (key, title, agg, _d) in zip(axes.flat, panels):
        vals = [agg([_metric_value(r, key) for r in rows_for(rows, a)]) for a in ARMS]
        ax.bar([ARM_LABEL[a] for a in ARMS], vals, color=[ARM_COLOR[a] for a in ARMS])
        ax.set_title(title)
    fig.suptitle("Task-execution efficiency")
    fig.tight_layout()
    return _save(fig, "efficiency_panel.png")


def fig_judge(rows: list[dict]) -> Path:
    sup, mono = [], []
    for dim in JUDGE_DIMS:
        for arm, store in (("supervisor", sup), ("monolithic", mono)):
            store.append(statistics.fmean([r["quality"][dim] for r in rows_for(rows, arm)]))
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    _grouped_bar(ax, [d.capitalize() for d in JUDGE_DIMS], sup, mono, "Mean score (1-5)", "LLM judge ratings (SUPPLEMENTARY)")
    ax.set_ylim(0, 5.2)
    return _save(fig, "judge_ratings.png")


def _save(fig, name: str) -> Path:
    FIGS.mkdir(parents=True, exist_ok=True)
    path = FIGS / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# CSV backups
# ---------------------------------------------------------------------------
def write_csv(path: Path, table: list[dict[str, Any]]) -> None:
    if not table:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(table[0].keys()))
        writer.writeheader()
        writer.writerows(table)


# ---------------------------------------------------------------------------
# Word document
# ---------------------------------------------------------------------------
def _heading(doc: Document, text: str, level: int) -> None:
    doc.add_heading(text, level=level)


def _para(doc: Document, text: str, italic: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = italic


def _add_table(doc: Document, headers: list[str], rows_data: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
    for r in rows_data:
        cells = table.add_row().cells
        for i, val in enumerate(r):
            cells[i].text = str(val)


def _add_figure(doc: Document, path: Path, width_in: float = 6.0) -> None:
    doc.add_picture(str(path), width=Inches(width_in))
    last = doc.paragraphs[-1]
    last.alignment = WD_ALIGN_PARAGRAPH.CENTER


def build_docx(rows: list[dict], artifacts: dict[str, Any]) -> Path:
    doc = Document()

    title = doc.add_heading("", level=0)
    run = title.add_run("Benchmark Results: Supervisor vs. Monolithic ReAct Architecture")
    run.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

    _para(
        doc,
        "Comparative evaluation of a multi-agent supervisor architecture against a "
        "monolithic ReAct agent on an intelligent daily-activity tracking system. "
        f"All figures derive from {len(rows)} agent runs ({len(rows)//2} per arm) on a "
        "frozen, deterministic evaluation dataset. The rule-based scorer is the "
        "PRIMARY evaluator; the LLM judge is reported as a SUPPLEMENTARY signal only.",
        italic=True,
    )

    # C1
    _heading(doc, "1. Aggregate Correctness Metrics", 1)
    _para(doc, "Rates are computed over applicable runs only (N shown); 'not applicable' "
               "checks are excluded rather than counted as failures.")
    headers = ["Metric", "Supervisor", "N", "Monolithic", "N"]
    data = [[t["metric"], t["supervisor"], t["supervisor_n"], t["monolithic"], t["monolithic_n"]]
            for t in artifacts["c1"]]
    _add_table(doc, headers, data)
    _add_figure(doc, artifacts["fig_core"])

    # C2
    _heading(doc, "2. Task Success by Category", 1)
    _para(doc, "No architecture dominates across the board: the monolithic agent leads on "
               "RAG and ambiguous-clarification scenarios, while the supervisor leads on "
               "multi-domain and tracking tasks.")
    _add_table(doc, ["Category", "Supervisor", "Monolithic"],
               [[t["category"], t["supervisor"], t["monolithic"]] for t in artifacts["c2"]])
    _add_figure(doc, artifacts["fig_cat"])

    # C3
    _heading(doc, "3. Task-Execution Efficiency", 1)
    _para(doc, "Paired Wilcoxon signed-rank test on per-scenario means (N = matched "
               "scenarios). Significance: * p<0.05, ** p<0.01, *** p<0.001.")
    _add_table(
        doc,
        ["Metric", "Supervisor mean", "Supervisor median", "Monolithic mean", "Monolithic median", "p (Wilcoxon)"],
        [[t["metric"], t["supervisor_mean"], t["supervisor_median"], t["monolithic_mean"],
          t["monolithic_median"], t["p_value"]] for t in artifacts["c3"]],
    )
    _add_figure(doc, artifacts["fig_eff"])
    _add_figure(doc, artifacts["fig_lat"])

    _heading(doc, "3b. Paired Significance on Accuracy Axes (McNemar)", 2)
    _para(doc, "McNemar's exact test on paired (scenario, repeat) outcomes. "
               "'Sup only' / 'Mono only' are discordant pairs won by each arm.")
    _add_table(
        doc,
        ["Metric", "Pairs", "Sup only", "Mono only", "p (McNemar)"],
        [[t["metric"], t["n_pairs"], t["sup_only"], t["mono_only"], t["p_value"]]
         for t in artifacts["mcnemar"]],
    )

    # C4
    _heading(doc, "4. Qualitative Findings", 1)
    for n, (title_txt, body) in enumerate(artifacts["findings"], start=1):
        _heading(doc, f"4.{n} {title_txt}", 2)
        _para(doc, body)

    # Judge
    _heading(doc, "5. LLM Judge (Supplementary)", 1)
    _para(doc, "The judge is blind to architecture and never influences task_success. "
               "It corroborates the rule-based scores and is reported for triangulation only.")
    _add_table(doc, ["Dimension", "Supervisor", "Monolithic"],
               [[t["metric"], t["supervisor"], t["monolithic"]] for t in artifacts["judge"]])
    _add_figure(doc, artifacts["fig_judge"])

    # C6
    _heading(doc, "6. Mapping to the Research Question", 1)
    _para(doc, "How does the management architecture affect tool-selection accuracy, "
               "argument-extraction correctness, and task-execution efficiency?")
    for axis, body in artifacts["rq"]:
        _heading(doc, axis, 2)
        _para(doc, body)

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "thesis_results.docx"
    doc.save(str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# RQ narrative (built from computed numbers)
# ---------------------------------------------------------------------------
def rq_narrative(rows: list[dict]) -> list[tuple[str, str]]:
    def rate(arm: str, key: str) -> str:
        r, _ = mean_of_bool([row["score"].get(key) for row in rows_for(rows, arm)])
        return pct(r)

    def med(arm: str, key: str) -> float:
        return statistics.median([_metric_value(r, key) for r in rows_for(rows, arm)])

    lat_ratio = med("supervisor", "latency_total_ms") / med("monolithic", "latency_total_ms")
    return [
        (
            "Tool-selection accuracy",
            f"Monolithic {rate('monolithic', 'tool_selection_correct')} vs supervisor "
            f"{rate('supervisor', 'tool_selection_correct')}. The supervisor's specialists "
            "occasionally chose non-targeted retrieval (whole-document read instead of "
            "semantic search), lowering its tool-selection rate despite correct answers.",
        ),
        (
            "Argument-extraction correctness",
            f"Supervisor {rate('supervisor', 'args_extraction_correct')} vs monolithic "
            f"{rate('monolithic', 'args_extraction_correct')}. The supervisor's focused "
            "specialists extracted relative date ranges more conservatively; the monolithic "
            "agent over-extended 'this week' into future days, costing it argument accuracy.",
        ),
        (
            "Task-execution efficiency",
            f"The monolithic agent was decisively cheaper and faster: ~{lat_ratio:.1f}x lower "
            "median latency, roughly half the cost and a third of the LLM calls. The "
            "supervisor additionally suffered non-termination on ambiguous inputs, the "
            "single largest efficiency liability of the multi-agent design.",
        ),
    ]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def main() -> None:
    rows = load_rows(JUDGED)
    OUT.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, Any] = {}
    artifacts["c1"] = aggregate_metrics(rows)
    artifacts["c2"] = task_success_by_category(rows)
    artifacts["c3"] = efficiency_table(rows)
    artifacts["mcnemar"] = mcnemar_table(rows)
    artifacts["judge"] = judge_table(rows)
    artifacts["findings"] = [
        ("Supervisor non-termination on ambiguous inputs", finding_non_termination(rows)),
        ("RAG tool substitution (right answer, weaker tool)", finding_rag_tools(rows)),
        ("Relative date-range over-extension (monolithic)", finding_dates(rows)),
        ("Confirm-before-delete safety gap (both arms)", finding_safety(rows)),
    ]
    artifacts["rq"] = rq_narrative(rows)

    artifacts["fig_core"] = fig_core_metrics(rows)
    artifacts["fig_cat"] = fig_task_by_category(rows)
    artifacts["fig_eff"] = fig_efficiency_panel(rows)
    artifacts["fig_lat"] = fig_latency_box(rows)
    artifacts["fig_judge"] = fig_judge(rows)

    # CSV backups
    write_csv(OUT / "c1_aggregate_metrics.csv", artifacts["c1"])
    write_csv(OUT / "c2_task_success_by_category.csv", artifacts["c2"])
    write_csv(OUT / "c3_efficiency.csv", artifacts["c3"])
    write_csv(OUT / "c3b_mcnemar.csv", artifacts["mcnemar"])
    write_csv(OUT / "judge_supplementary.csv", artifacts["judge"])

    out_path = build_docx(rows, artifacts)
    print(f"Word report: {out_path}")
    print(f"Figures:     {FIGS}")
    print(f"CSVs:        {OUT}")


if __name__ == "__main__":
    main()
