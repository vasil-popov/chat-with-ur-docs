"""Unit tests for the supplementary LLM-as-judge (NO live LLM).

These tests use mock structured-output clients only. They lock in:
  * token tally + success path of ``judge_answer``,
  * non-fatal handling of unparsable judge output,
  * ``QualityScores`` 1-5 validation,
  * blindness of the manual-scoring CSV pair (no arch in the rater file),
  * ``judge_runs`` enrichment that skips error rows and never touches
    ``task_success``/``score``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.evaluation import judge
from app.evaluation.judge import (
    JudgeResult,
    QualityScores,
    _ManualRow,
    _write_manual_scoring,
    judge_answer,
    judge_runs,
)


class _FakeRaw:
    """Stand-in for an AIMessage carrying usage_metadata."""

    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.usage_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }


class _FakeStructured:
    """Mock of ``llm.with_structured_output(...)`` returning a canned dict."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.calls: list[Any] = []

    def invoke(self, messages: Any) -> dict[str, Any]:
        self.calls.append(messages)
        return self._response


class _FakeLLM:
    """Mock LLM whose ``with_structured_output`` yields a canned client."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._structured = _FakeStructured(response)

    def with_structured_output(self, _schema: Any, *, include_raw: bool) -> _FakeStructured:
        assert include_raw is True
        return self._structured


def _scores(**overrides: Any) -> QualityScores:
    base = {
        "correctness": 5,
        "completeness": 4,
        "relevance": 5,
        "conciseness": 4,
        "hallucination_detected": False,
        "rationale": "Matches the reference closely.",
    }
    base.update(overrides)
    return QualityScores(**base)


class TestQualityScoresValidation:
    def test_accepts_in_range_scores(self) -> None:
        scores = _scores()
        assert scores.correctness == 5

    def test_rejects_score_above_five(self) -> None:
        with pytest.raises(ValidationError):
            _scores(correctness=6)

    def test_rejects_score_below_one(self) -> None:
        with pytest.raises(ValidationError):
            _scores(relevance=0)


class TestJudgeAnswerSuccess:
    def test_returns_scores_and_tallies_tokens(self) -> None:
        parsed = _scores()
        llm = _FakeLLM(
            {"raw": _FakeRaw(120, 30), "parsed": parsed, "parsing_error": None}
        )

        result = judge_answer(
            question="How much did I spend on food?",
            reference_answer="You spent 42 on food.",
            answer_points=("mentions 42", "mentions food"),
            candidate="You spent 42 dollars on food this week.",
            llm=llm,
        )

        assert result.failed is False
        assert result.scores is parsed
        assert result.prompt_tokens == 120
        assert result.completion_tokens == 30
        # Cost is derived from token counts and per-1k prices; non-negative
        # regardless of whether pricing resolved from Settings or fell back to 0.
        assert result.est_cost_usd >= 0.0

    def test_cost_uses_resolved_prices(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(judge, "_judge_prices", lambda: (0.01, 0.03))
        llm = _FakeLLM(
            {"raw": _FakeRaw(2000, 1000), "parsed": _scores(), "parsing_error": None}
        )

        result = judge_answer(
            question="Q",
            reference_answer="REF",
            answer_points=(),
            candidate="CAND",
            llm=llm,
        )

        # 2 * 0.01 + 1 * 0.03 = 0.05.
        assert result.est_cost_usd == pytest.approx(0.05)

    def test_prompt_is_blind_to_architecture(self) -> None:
        llm = _FakeLLM(
            {"raw": _FakeRaw(10, 5), "parsed": _scores(), "parsing_error": None}
        )

        judge_answer(
            question="Q",
            reference_answer="REF",
            answer_points=("p1",),
            candidate="CAND",
            llm=llm,
        )

        sent = json.dumps(llm._structured.calls)
        assert "supervisor" not in sent.lower()
        assert "monolithic" not in sent.lower()
        assert "arch" not in sent.lower()


class TestJudgeAnswerFailure:
    def test_parse_failure_is_non_fatal(self) -> None:
        llm = _FakeLLM(
            {
                "raw": _FakeRaw(15, 0),
                "parsed": None,
                "parsing_error": ValueError("bad"),
            }
        )

        result = judge_answer(
            question="Q",
            reference_answer="REF",
            answer_points=(),
            candidate="CAND",
            llm=llm,
        )

        assert result.failed is True
        assert result.scores is None
        assert "bad" in (result.error or "")
        assert result.prompt_tokens == 15

    def test_invocation_exception_is_caught(self) -> None:
        class _RaisingStructured:
            def invoke(self, _messages: Any) -> dict[str, Any]:
                raise RuntimeError("network down")

        class _RaisingLLM:
            def with_structured_output(self, *_a: Any, **_k: Any) -> _RaisingStructured:
                return _RaisingStructured()

        result = judge_answer(
            question="Q",
            reference_answer="REF",
            answer_points=(),
            candidate="CAND",
            llm=_RaisingLLM(),
        )

        assert result.failed is True
        assert result.scores is None
        assert "network down" in (result.error or "")


class TestManualScoringExport:
    def test_blind_csv_omits_arch_and_key_maps_back(self, tmp_path: Path) -> None:
        manual_rows = [
            _ManualRow("s1", "supervisor", 0, "Q1", "A1"),
            _ManualRow("s2", "monolithic", 1, "Q2", "A2"),
            _ManualRow("s3", "supervisor", 0, "Q3", "A3"),
        ]
        manual_csv = tmp_path / "manual_scoring.csv"
        key_csv = tmp_path / "manual_scoring_key.csv"

        _write_manual_scoring(manual_rows, manual_csv, key_csv)

        with manual_csv.open(encoding="utf-8", newline="") as fh:
            manual = list(csv.DictReader(fh))
        with key_csv.open(encoding="utf-8", newline="") as fh:
            key = {r["anon_id"]: r for r in csv.DictReader(fh)}

        assert len(manual) == 3
        assert len(key) == 3

        # Rater-facing file must NOT leak architecture or scenario identity.
        rater_columns = set(manual[0].keys())
        assert "arch" not in rater_columns
        assert "scenario_id" not in rater_columns
        assert "repeat" not in rater_columns

        # Score columns are blank for the human to fill in.
        for row in manual:
            assert row["correctness"] == ""
            assert row["completeness"] == ""
            assert row["relevance"] == ""
            assert row["conciseness"] == ""

        # The key is the only place arch lives and maps every anon_id back.
        for row in manual:
            anon = row["anon_id"]
            assert anon in key
            assert key[anon]["arch"] in {"supervisor", "monolithic"}
            assert key[anon]["scenario_id"] in {"s1", "s2", "s3"}


class TestJudgeRunsBatch:
    def test_enriches_rows_skips_errors_and_preserves_score(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Use a real scenario id from the dataset so lookup succeeds.
        from app.evaluation.dataset.loader import load_dataset

        scenario = load_dataset().scenarios[0]

        runs_path = tmp_path / "runs.jsonl"
        good_row = {
            "scenario_id": scenario.id,
            "category": scenario.category,
            "arch": "supervisor",
            "repeat": 0,
            "message": scenario.message,
            "final_answer": "A grounded answer.",
            "score": {"task_success": True},
            "metrics": {},
        }
        error_row = {
            "scenario_id": scenario.id,
            "arch": "monolithic",
            "repeat": 0,
            "error": "boom",
        }
        runs_path.write_text(
            json.dumps(good_row) + "\n" + json.dumps(error_row) + "\n",
            encoding="utf-8",
        )

        llm = _FakeLLM(
            {"raw": _FakeRaw(50, 10), "parsed": _scores(), "parsing_error": None}
        )

        out_path = tmp_path / "runs_judged.jsonl"
        summary = judge_runs(
            runs_path,
            out_path=out_path,
            manual_csv_path=tmp_path / "manual.csv",
            key_csv_path=tmp_path / "key.csv",
            llm=llm,
        )

        assert summary.judged == 1
        assert summary.skipped_error == 1
        assert summary.prompt_tokens == 50
        assert summary.completion_tokens == 10

        judged = [
            json.loads(line)
            for line in out_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(judged) == 1
        enriched = judged[0]
        assert "quality" in enriched
        assert enriched["quality"]["correctness"] == 5
        # task_success / score must be untouched by the judge.
        assert enriched["score"] == {"task_success": True}

    def test_resume_skips_already_judged_rows(self, tmp_path: Path) -> None:
        from app.evaluation.dataset.loader import load_dataset

        scenario = load_dataset().scenarios[0]
        runs_path = tmp_path / "runs.jsonl"
        row = {
            "scenario_id": scenario.id,
            "arch": "supervisor",
            "repeat": 0,
            "message": scenario.message,
            "final_answer": "ans",
            "score": {"task_success": True},
        }
        runs_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

        out_path = tmp_path / "judged.jsonl"
        # Pre-seed the output as if already judged.
        out_path.write_text(
            json.dumps({**row, "quality": {"correctness": 3}}) + "\n",
            encoding="utf-8",
        )

        llm = _FakeLLM(
            {"raw": _FakeRaw(50, 10), "parsed": _scores(), "parsing_error": None}
        )
        summary = judge_runs(
            runs_path,
            out_path=out_path,
            manual_csv_path=tmp_path / "m.csv",
            key_csv_path=tmp_path / "k.csv",
            resume=True,
            llm=llm,
        )

        assert summary.judged == 0
        assert summary.skipped_resume == 1

    def test_no_judged_rows_does_not_touch_manual_csv(self, tmp_path: Path) -> None:
        # A runs file with ONLY an error row yields zero judged rows, so the
        # rater CSV pair must be left exactly as-is (no header-only clobber).
        runs_path = tmp_path / "runs.jsonl"
        error_row = {
            "scenario_id": "s-missing",
            "arch": "supervisor",
            "repeat": 0,
            "error": "boom",
        }
        runs_path.write_text(json.dumps(error_row) + "\n", encoding="utf-8")

        manual_csv = tmp_path / "manual_scoring.csv"
        key_csv = tmp_path / "manual_scoring_key.csv"
        # Pre-existing human annotation work that must survive untouched.
        prior_manual = "anon_id,question,answer,correctness\na001,Q,A,5\n"
        prior_key = "anon_id,scenario_id,arch,repeat\na001,s1,supervisor,0\n"
        manual_csv.write_text(prior_manual, encoding="utf-8")
        key_csv.write_text(prior_key, encoding="utf-8")

        llm = _FakeLLM(
            {"raw": _FakeRaw(50, 10), "parsed": _scores(), "parsing_error": None}
        )
        summary = judge_runs(
            runs_path,
            out_path=tmp_path / "judged.jsonl",
            manual_csv_path=manual_csv,
            key_csv_path=key_csv,
            llm=llm,
        )

        assert summary.judged == 0
        assert summary.skipped_error == 1
        # The prior export must be byte-for-byte preserved.
        assert manual_csv.read_text(encoding="utf-8") == prior_manual
        assert key_csv.read_text(encoding="utf-8") == prior_key
