"""Minimal unit tests for run_ab.py.

These tests never call a real model. They feed fake opencode JSONL fixtures and
patch the module-level output directories to temp paths. Run with:

    .venv/bin/python -m pytest evals/skill-ab-2026-08-10/tests/ -q
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
RUN_AB = HERE.parent / "run_ab.py"

spec = importlib.util.spec_from_file_location("run_ab", RUN_AB)
assert spec is not None and spec.loader is not None
run_ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_ab)

DIMENSIONS = run_ab.DIMENSIONS


def load(name: str) -> Path:
    return HERE.parent / name


@pytest.fixture(autouse=True)
def redirect_output_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_ab, "GENERATED_DIR", tmp_path / "generated")
    monkeypatch.setattr(run_ab, "JUDGED_DIR", tmp_path / "judged")
    monkeypatch.setattr(run_ab, "OUTPUT_DIR", tmp_path / "output")


def build_fake_raw() -> str:
    events = [
        {"type": "step_start", "timestamp": 1000000, "sessionID": "ses_test1",
         "part": {"id": "p1", "sessionID": "ses_test1", "type": "step-start"}},
        {"type": "text", "timestamp": 1000100, "sessionID": "ses_test1",
         "part": {"id": "p2", "messageID": "m1", "sessionID": "ses_test1",
                  "type": "text", "text": "第一步分析", "time": {}}},
        {"type": "tool_use", "timestamp": 1000200, "sessionID": "ses_test1",
         "part": {"type": "tool", "tool": "bash", "callID": "c1",
                  "state": {"status": "completed",
                            "input": {"command": 'siftline github search-repos "factorio roguelite"'
                                                 " --limit 5"},
                            "output": "{}", "title": "siftline ..."}}},
        {"type": "tool_use", "timestamp": 1000300, "sessionID": "ses_test1",
         "part": {"type": "tool", "tool": "webfetch", "callID": "c2",
                  "state": {"status": "completed"}}},
        {"type": "tool_use", "timestamp": 1000400, "sessionID": "ses_test1",
         "part": {"type": "tool", "tool": "read", "callID": "c3",
                  "state": {"status": "completed"}}},
        {"type": "step_finish", "timestamp": 1000500, "sessionID": "ses_test1",
         "part": {"id": "p6", "reason": "tool-calls", "messageID": "m1",
                  "sessionID": "ses_test1", "type": "step-finish",
                  "tokens": {"total": 5000, "input": 100, "output": 200, "reasoning": 10,
                             "cache": {"write": 50, "read": 4000}},
                  "cost": 0.001}},
        {"type": "text", "timestamp": 2000000, "sessionID": "ses_test1",
         "part": {"id": "p7", "messageID": "m2", "sessionID": "ses_test1",
                  "type": "text", "text": "最终结论", "time": {}}},
        {"type": "step_finish", "timestamp": 2000100, "sessionID": "ses_test1",
         "part": {"id": "p8", "reason": "stop", "messageID": "m2",
                  "sessionID": "ses_test1", "type": "step-finish",
                  "tokens": {"total": 7000, "input": 50, "output": 30, "reasoning": 0,
                             "cache": {"write": 0, "read": 7000}},
                  "cost": 0.002}},
    ]
    lines = [json.dumps(event) for event in events]
    lines.append("NOT-JSON progress line (must be tolerated)")
    return "\n".join(lines)


def make_args(**overrides):
    defaults = {
        "opencode": "opencode",
        "tasks": [],
        "jobs": 2,
        "force": False,
        "dry_run": False,
        "model": run_ab.MODEL_DEFAULT,
        "timeout": run_ab.DEFAULT_TIMEOUT,
        "registry": run_ab.ProcRegistry(),
    }
    defaults.update(overrides)
    return type("Args", (), defaults)()


class TestParsing:
    def test_parse_version(self) -> None:
        assert run_ab.parse_version("1.18.15") == (1, 18, 15)
        assert run_ab.parse_version("v2.0.1-beta") == (2, 0, 1)
        assert run_ab.parse_version("not a version") is None

    def test_check_opencode_rejects_old(self) -> None:
        with pytest.raises(run_ab.EvalError):
            run_ab.check_opencode("opencode-this-does-not-exist-xyz")

    def test_summarize_session(self) -> None:
        raw = build_fake_raw()
        summary = run_ab.summarize_session(raw, exit_code=0)
        assert summary["session_id"] == "ses_test1"
        assert summary["wall_time_ms"] == 1000100
        assert summary["exit_code"] == 0
        # only the final reason=stop message's text; the m1 progress text is excluded
        assert summary["final_stop_message_id"] == "m2"
        assert summary["text_parts"] == ["最终结论"]
        assert summary["tool_counts"] == {"bash": 1, "webfetch": 1, "read": 1}
        assert summary["siftline_calls"] == 1
        assert summary["external_ops"] == 2
        assert summary["n_events"] == 8
        totals = summary["totals"]
        assert totals["total"] == 12000
        assert totals["input"] == 150
        assert totals["output"] == 230
        assert totals["reasoning"] == 10
        assert totals["cache_read"] == 11000
        assert totals["cache_write"] == 50
        assert totals["cost"] == pytest.approx(0.003)
        assert len(summary["steps"]) == 2

    def test_summarize_session_multiple_messages_tool_calls(self) -> None:
        # three assistant messages: two tool-call turns with progress text,
        # then a final stop message; only the last stop message's text counts.
        def event(etype, ts, mid, reason=None, text=None, tool=None):
            part = {"id": f"p-{ts}", "messageID": mid, "sessionID": "s", "type": etype}
            if reason is not None:
                part["reason"] = reason
            if text is not None:
                part["text"] = text
            if tool is not None:
                part.update({"tool": tool, "state": {"input": {"command": tool}}})
            return json.dumps({"type": etype, "timestamp": ts, "sessionID": "s", "part": part})

        lines = [
            event("step_start", 0, "m0"),
            event("text", 1, "m1", text="思考中A"),
            event("tool_use", 2, "m1", tool="bash"),
            event("step_finish", 3, "m1", reason="tool-calls"),
            event("text", 4, "m2", text="思考中B"),
            event("tool_use", 5, "m2", tool="webfetch"),
            event("step_finish", 6, "m2", reason="tool-calls"),
            event("text", 7, "m3", text="最终答案正文"),
            event("step_finish", 8, "m3", reason="stop"),
        ]
        summary = run_ab.summarize_session("\n".join(lines), exit_code=0)
        assert summary["final_stop_message_id"] == "m3"
        assert summary["text_parts"] == ["最终答案正文"]
        assert summary["tool_counts"] == {"bash": 1, "webfetch": 1}
        assert len(summary["steps"]) == 3

    def test_summarize_session_no_stop(self) -> None:
        raw = "\n".join(
            [
                json.dumps({"type": "step_start", "timestamp": 1, "sessionID": "s",
                            "part": {"type": "step-start", "messageID": "m1"}}),
                json.dumps({"type": "text", "timestamp": 2, "sessionID": "s",
                            "part": {"type": "text", "messageID": "m1", "text": "被截断的正文"}}),
                json.dumps({"type": "step_finish", "timestamp": 3, "sessionID": "s",
                            "part": {"type": "step-finish", "messageID": "m1",
                                     "reason": "tool-calls", "tokens": {"total": 1}, "cost": 0}}),
            ]
        )
        summary = run_ab.summarize_session(raw, exit_code=0)
        assert summary["final_stop_message_id"] is None
        assert summary["text_parts"] == []

    def test_extract_json_object(self) -> None:
        plain = '{"winner": "X", "confidence": 8}'
        assert run_ab.extract_json_object(plain) == {"winner": "X", "confidence": 8}
        fenced = '```json\n{"winner": "Y"}\n```'
        assert run_ab.extract_json_object(fenced) == {"winner": "Y"}
        assert run_ab.extract_json_object("no json here") is None
        assert run_ab.extract_json_object('{"broken": ') is None


class TestPromptBuilding:
    def test_baseline_prompt_has_no_skill(self) -> None:
        message, attachments = run_ab.build_generate_prompt("task1", "baseline")
        assert run_ab.SKILL_DIRECTIVE not in message
        assert "siftline-research" not in message
        assert attachments == []

    def test_skill_prompt_prefixes_directive_and_attaches_files(self) -> None:
        message, attachments = run_ab.build_generate_prompt("task1", "skill")
        assert message.startswith(run_ab.SKILL_DIRECTIVE)
        assert run_ab.SKILL_MD.name in [p.name for p in attachments]
        assert len(attachments) == 5  # SKILL.md + 4 references

    def test_both_arms_share_task_body(self) -> None:
        baseline, _ = run_ab.build_generate_prompt("task3", "baseline")
        skill, _ = run_ab.build_generate_prompt("task3", "skill")
        assert skill.endswith(baseline)
        assert len(baseline) > 200


class TestContaminationGuard:
    def test_forbidden_input_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        forbidden = tmp_path / "old-eval-2026-08-09"
        forbidden.mkdir()
        bad_file = forbidden / "artifact.json"
        bad_file.write_text("{}", encoding="utf-8")
        good_file = tmp_path / "ok.md"
        good_file.write_text("ok", encoding="utf-8")
        monkeypatch.setattr(run_ab, "FORBIDDEN_DIRS", [forbidden.resolve()])
        with pytest.raises(run_ab.EvalError):
            run_ab.guard_no_forbidden([bad_file])
        run_ab.guard_no_forbidden([good_file])  # must not raise


class TestMapping:
    def test_mapping_integrity(self) -> None:
        run_ab.validate_spec()
        assert run_ab.arm_label("task1", "skill") == "X"
        assert run_ab.arm_label("task1", "baseline") == "Y"
        assert run_ab.arm_label("task2", "skill") == "Y"
        assert run_ab.arm_label("task3", "skill") == "X"
        assert run_ab.resolve_winner("task1", "X") == "skill"
        assert run_ab.resolve_winner("task2", "X") == "baseline"
        assert run_ab.resolve_winner("task1", "tie") == "tie"

    def test_mapping_file_matches_code(self) -> None:
        on_disk = json.loads(load("mapping.json").read_text(encoding="utf-8"))
        for task_id in run_ab.TASKS:
            assert on_disk[task_id] == run_ab.MAPPING[task_id]

    def test_adjacent_arm_ordering(self) -> None:
        order = [
            (task_id, condition)
            for task_id in run_ab.TASKS
            for condition in run_ab.CONDITIONS
        ]
        assert order == [
            ("task1", "baseline"), ("task1", "skill"),
            ("task2", "baseline"), ("task2", "skill"),
            ("task3", "baseline"), ("task3", "skill"),
        ]


class TestJudgeAssembly:
    def test_judge_attachments_use_anonymous_arms(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        generated = tmp_path / "generated"
        for condition in ("baseline", "skill"):
            d = generated / "task1" / condition
            d.mkdir(parents=True)
            (d / "assistant.txt").write_text(f"output-{condition}", encoding="utf-8")
        entries = run_ab.build_judge_attachments("task1", ["X", "Y"])
        by_name = dict(entries)
        assert by_name["task.md"] == run_ab.TASKS["task1"]["prompt"]
        assert by_name["arm_X.txt"] == generated / "task1" / "skill" / "assistant.txt"
        assert by_name["arm_Y.txt"] == generated / "task1" / "baseline" / "assistant.txt"
        assert "meta_arms.md" in by_name

    def test_judge_message_forbids_mapping_and_old_eval(self) -> None:
        message = run_ab.build_judge_message("task1", ["X", "Y"])
        assert "task1" in message
        assert run_ab.FORBIDDEN_DIRS[0].name in message
        assert "arm_order" in message or "臂顺序" in message


class TestResumeAndSkip:
    def test_run_is_done(self, tmp_path: Path) -> None:
        d = tmp_path / "run"
        d.mkdir()
        assert not run_ab.run_is_done(d)
        (d / "SUCCESS").touch()
        assert run_ab.run_is_done(d)

    def test_generate_skips_when_done(self) -> None:
        run_dir = run_ab.GENERATED_DIR / "task1" / "baseline"
        run_dir.mkdir(parents=True)
        (run_dir / "SUCCESS").touch()
        args = make_args()
        result = run_ab.generate_one(args, "task1", "baseline")
        assert result["status"] == "skipped"

    def test_generate_dry_run_creates_no_artifacts(self) -> None:
        args = make_args(dry_run=True)
        result = run_ab.generate_one(args, "task1", "skill")
        assert result["status"] == "dry-run"
        assert not (run_ab.GENERATED_DIR / "task1" / "skill" / "SUCCESS").exists()


class TestSummary:
    def test_aggregate_and_resolve(self) -> None:
        data = {
            "generated": {
                "task1": {
                    "baseline": {"status": "success", "exit_code": 0, "wall_time_ms": 1000,
                                 "assistant_chars": 10, "totals": {"cost": 0.01, "total": 100},
                                 "tool_counts": {}, "siftline_calls": 0, "external_ops": 0,
                                 "steps": [], "session_id": "s1"},
                    "skill": {"status": "success", "exit_code": 0, "wall_time_ms": 2000,
                              "assistant_chars": 20, "totals": {"cost": 0.05, "total": 200},
                              "tool_counts": {}, "siftline_calls": 2, "external_ops": 3,
                              "steps": [], "session_id": "s2"},
                }
            },
            "judged": {
                "task1": {
                    "flash-xy": {
                        "judge_id": "flash-xy", "model": run_ab.MODEL_DEFAULT,
                        "order": ["X", "Y"],
                        "meta": {"status": "success", "answer_parsed": True},
                        "result": {"winner": "X", "totals": {"X": 70, "Y": 60},
                                   "penalty": {"X": 0, "Y": 0}, "confidence": 8,
                                   "scores": dict.fromkeys(DIMENSIONS, 0),
                                   "reasons": ["a", "b", "c", "d"],
                                   "quality_increment_worth_cost": True},
                    }
                }
            },
        }
        aggregated = run_ab.aggregate_summary(data)
        task1 = aggregated["tasks"]["task1"]
        judge = task1["judges"][0]
        assert judge["winner"] == "X"
        assert judge["winner_condition"] == "skill"
        assert task1["skill_wins"] == 1
        assert task1["baseline_wins"] == 0
        assert task1["ties"] == 0

    def test_summary_marks_unavailable_judges(self) -> None:
        data = {
            "generated": {"task1": {"baseline": None, "skill": None}},
            "judged": {"task1": {"flash-xy": {"judge_id": "flash-xy", "model": "m",
                                              "order": ["X", "Y"], "meta": None, "result": None}}},
        }
        aggregated = run_ab.aggregate_summary(data)
        assert aggregated["tasks"]["task1"]["judges"][0]["available"] is False

    def test_render_markdown_contains_disclaimer(self) -> None:
        data = {
            "generated": {"task1": {"baseline": None, "skill": None}},
            "judged": {"task1": {"flash-xy": {"judge_id": "flash-xy", "model": "m",
                                              "order": ["X", "Y"], "meta": None, "result": None}}},
        }
        md = run_ab.render_summary_markdown(run_ab.aggregate_summary(data))
        assert "不替代最终人工解释" in md
        assert "mapping.json" in md


class TestWritePipeline:
    def _fake_popen(self, monkeypatch: pytest.MonkeyPatch, out: str, rc: int = 0) -> dict:
        captured: dict = {}

        class FakeProc:
            returncode = rc

            def __init__(self, command: list[str], **kwargs) -> None:
                captured["command"] = command

            def communicate(self, timeout: int | None = None) -> tuple[str, str]:
                return out, ""

            def terminate(self) -> None:
                pass

        monkeypatch.setattr(run_ab.subprocess, "Popen", FakeProc)
        return captured

    def test_generate_one_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = self._fake_popen(monkeypatch, build_fake_raw())
        args = make_args()
        result = run_ab.generate_one(args, "task1", "baseline")
        assert result["status"] == "success"
        command = captured["command"]
        assert command[0] == "opencode"
        assert command[1] == "run"
        assert "--pure" in command
        assert "--auto" in command
        assert "--format" in command and "json" in command
        assert "-m" in command and run_ab.MODEL_DEFAULT in command
        assert "--dir" in command
        assert "-f" not in command  # baseline has no attachments
        run_dir = run_ab.GENERATED_DIR / "task1" / "baseline"
        assert (run_dir / "SUCCESS").is_file()
        assert (run_dir / "raw.jsonl").is_file()
        assert (run_dir / "prompt.txt").is_file()
        assert (run_dir / "meta.json").is_file()
        assistant = (run_dir / "assistant.txt").read_text(encoding="utf-8")
        assert "最终结论" in assistant
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["status"] == "success"
        assert meta["session_id"] == "ses_test1"
        assert meta["siftline_calls"] == 1
        assert meta["external_ops"] == 2
        assert "--pure" in meta["command"]

    def test_generate_skill_command_attaches_five_files(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._fake_popen(monkeypatch, build_fake_raw())
        args = make_args()
        result = run_ab.generate_one(args, "task1", "skill")
        assert result["status"] == "success"
        command = captured["command"]
        assert "--pure" in command
        assert command.count("-f") == 5  # SKILL.md + 4 references

    def test_judge_one_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for condition in ("baseline", "skill"):
            d = run_ab.GENERATED_DIR / "task1" / condition
            d.mkdir(parents=True)
            (d / "assistant.txt").write_text(f"output-{condition}", encoding="utf-8")
        answer = {
            "task_id": "task1",
            "winner": "X",
            "confidence": 8,
            "totals": {"X": 70, "Y": 60},
            "penalty": {"X": 0, "Y": 0},
        }
        raw = "\n".join(
            [
                json.dumps({"type": "step_start", "timestamp": 1, "sessionID": "ses_judge1",
                            "part": {"type": "step-start", "messageID": "m1"}}),
                json.dumps({"type": "text", "timestamp": 2, "sessionID": "ses_judge1",
                            "part": {"type": "text", "messageID": "m1",
                                     "text": json.dumps(answer)}}),
                json.dumps({"type": "step_finish", "timestamp": 3, "sessionID": "ses_judge1",
                            "part": {"type": "step-finish", "messageID": "m1", "reason": "stop",
                                     "tokens": {"total": 100}, "cost": 0.0}}),
            ]
        )
        captured = self._fake_popen(monkeypatch, raw)
        args = make_args()
        result = run_ab.judge_one(args, "task1", run_ab.JUDGES[0])
        assert result["status"] == "success"
        command = captured["command"]
        assert "--pure" in command
        assert command.count("-f") == 4  # task.md + arm_X + arm_Y + meta_arms
        assert run_ab.JUDGES[0]["model"] in command
        run_dir = run_ab.JUDGED_DIR / "task1" / "flash-xy"
        assert (run_dir / "SUCCESS").is_file()
        assert (run_dir / "result.json").is_file()
        parsed = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        assert parsed["winner"] == "X"
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["answer_parsed"] is True

    def test_generate_dry_run_preview_contains_pure(self) -> None:
        args = make_args(dry_run=True)
        result = run_ab.generate_one(args, "task1", "skill")
        assert result["status"] == "dry-run"
        assert "--pure" in result["preview"]

    def test_judge_dry_run_preview_contains_pure(self) -> None:
        for condition in ("baseline", "skill"):
            d = run_ab.GENERATED_DIR / "task1" / condition
            d.mkdir(parents=True)
            (d / "assistant.txt").write_text(f"output-{condition}", encoding="utf-8")
        args = make_args(dry_run=True)
        result = run_ab.judge_one(args, "task1", run_ab.JUDGES[0])
        assert result["status"] == "dry-run"
        assert "--pure" in result["preview"]


class TestTimeout:
    def _timeout_proc(self, monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
        class TimeoutProc:
            returncode = -15

            def __init__(self, command: list[str], **kwargs) -> None:
                captured["command"] = command

            def communicate(self, timeout: int | None = None) -> tuple[str, str]:
                captured["calls"] = captured.get("calls", 0) + 1
                if captured["calls"] < 3:
                    raise run_ab.subprocess.TimeoutExpired("opencode", timeout)
                return "partial-json\n", "stderr-text"

            def terminate(self) -> None:
                captured["terminated"] = True

            def kill(self) -> None:
                captured["killed"] = True

        monkeypatch.setattr(run_ab.subprocess, "Popen", TimeoutProc)

    def test_run_session_timeout_terminates_and_salvages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}
        self._timeout_proc(monkeypatch, captured)
        workdir = Path(run_ab.tempfile.mkdtemp())
        rc, out, err, command, timed_out = run_ab.run_session(
            "opencode", "msg", "model", [], workdir, None, timeout=5
        )
        assert timed_out is True
        assert rc == -15
        assert out == "partial-json\n"
        assert err == "stderr-text"
        assert "--pure" in command
        assert captured.get("terminated") is True
        assert captured.get("killed") is True

    def test_generate_one_timeout_marks_failed_and_saves_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict = {}
        self._timeout_proc(monkeypatch, captured)
        args = make_args(timeout=5)
        result = run_ab.generate_one(args, "task1", "baseline")
        assert result["status"] == "failed"
        assert result["timed_out"] is True
        run_dir = run_ab.GENERATED_DIR / "task1" / "baseline"
        assert not (run_dir / "SUCCESS").exists()
        assert (run_dir / "raw.jsonl").is_file()
        assert (run_dir / "stderr.log").is_file()
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["timed_out"] is True
        assert meta["timeout_seconds"] == 5
        assert meta["status"] == "failed"


class TestReprocess:
    def _write_run(self, condition: str, raw: str, meta: dict) -> None:
        run_dir = run_ab.GENERATED_DIR / "task1" / condition
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "raw.jsonl").write_text(raw, encoding="utf-8")
        (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (run_dir / "assistant.txt").write_text("stale", encoding="utf-8")
        (run_dir / "SUCCESS").touch()

    def test_reprocess_valid_run(self) -> None:
        meta = {"schema_version": "1", "kind": "generate", "task_id": "task1",
                "condition": "baseline", "status": "success", "exit_code": 0,
                "assistant_chars": 999, "session_id": "old"}
        self._write_run("baseline", build_fake_raw(), meta)
        run_dir = run_ab.GENERATED_DIR / "task1" / "baseline"
        result = run_ab.reprocess_one(run_dir)
        assert result["status"] == "reprocessed"
        assert result["assistant_chars"] == len("最终结论")
        assert (run_dir / "assistant.txt").read_text(encoding="utf-8") == "最终结论"
        assert (run_dir / "SUCCESS").exists()
        updated = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert updated["assistant_chars"] == 4
        assert updated["reprocessed"] is True
        assert updated["session_id"] == "ses_test1"
        assert updated["assistant_stop_message_id"] == "m2"

    def test_reprocess_no_final_stop_removes_success(self) -> None:
        raw = "\n".join(
            [
                json.dumps({"type": "step_start", "timestamp": 1, "sessionID": "s",
                            "part": {"type": "step-start", "messageID": "m1"}}),
                json.dumps({"type": "text", "timestamp": 2, "sessionID": "s",
                            "part": {"type": "text", "messageID": "m1", "text": "截断正文"}}),
                json.dumps({"type": "step_finish", "timestamp": 3, "sessionID": "s",
                            "part": {"type": "step-finish", "messageID": "m1",
                                     "reason": "tool-calls"}}),
            ]
        )
        meta = {"status": "success", "exit_code": 0}
        self._write_run("skill", raw, meta)
        run_dir = run_ab.GENERATED_DIR / "task1" / "skill"
        result = run_ab.reprocess_one(run_dir)
        assert result["status"] == "skip"
        assert "final stop" in result["reason"]
        assert not (run_dir / "SUCCESS").exists()

    def test_reprocess_failed_run_skipped(self) -> None:
        self._write_run("baseline", build_fake_raw(), {"status": "failed", "exit_code": 2})
        run_dir = run_ab.GENERATED_DIR / "task1" / "baseline"
        result = run_ab.reprocess_one(run_dir)
        assert result["status"] == "skip"
        assert "failed" in result["reason"]
        assert not (run_dir / "SUCCESS").exists()

    def test_reprocess_missing_raw_skipped(self) -> None:
        run_dir = run_ab.GENERATED_DIR / "task1" / "baseline"
        run_dir.mkdir(parents=True)
        (run_dir / "meta.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")
        result = run_ab.reprocess_one(run_dir)
        assert result["status"] == "skip"
        assert result["reason"] == "no raw.jsonl"

    def test_main_reprocess_cli(self, capsys: pytest.CaptureFixture) -> None:
        self._write_run("baseline", build_fake_raw(),
                        {"status": "success", "exit_code": 0})
        rc = run_ab.main(["reprocess", "--tasks", "1"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "reprocessed" in out
        assert "no model runs" in out


class TestCli:
    def test_main_generate_dry_run(self, capsys: pytest.CaptureFixture) -> None:
        rc = run_ab.main(["generate", "--dry-run", "--tasks", "1", "--only", "skill"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "dry-run" in out
        assert "--pure" in out
        assert "--auto" in out

    def test_main_summary_writes_files(self, tmp_path: Path) -> None:
        rc = run_ab.main(
            [
                "summary",
                "--json",
                str(tmp_path / "summary.json"),
                "--markdown",
                str(tmp_path / "summary.md"),
            ]
        )
        assert rc == 0
        assert (tmp_path / "summary.json").is_file()
        assert (tmp_path / "summary.md").is_file()
