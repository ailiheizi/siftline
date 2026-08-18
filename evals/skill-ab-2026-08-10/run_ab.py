#!/usr/bin/env python3
"""Reproducible A/B evaluation harness for the siftline-research skill.

Compares two conditions (baseline vs siftline-research skill) on three read-only
research tasks. Every session runs through the local ``opencode run`` CLI with
``--pure --auto --format json`` from a neutral ``tempfile`` working directory
(fresh session, no ``--continue``/``--session``/``--fork``; ``--pure`` disables
global plugins/skills/config so the baseline arm is not contaminated). Subcommands:

    generate    run the 3 tasks x 2 conditions (each task's two arms run adjacent)
    judge       blind pairwise judging (DeepSeek V4 Flash + Qwen 3.7 Max, reversed arm order)
    all         generate + judge + summary
    reprocess   re-extract assistant.txt from existing generated raw.jsonl (no model runs)
    summary     auto-aggregate results into summary.json / summary.md

``assistant.txt`` holds only the text events of the last ``step_finish`` with
``reason="stop"`` (matched by messageID); intermediate progress text is not
included. Each opencode subprocess has a configurable timeout (``--timeout``);
on timeout the process is terminated gracefully, whatever output arrived is
saved, and the run is marked failed (no SUCCESS).

Only the Python 3.11+ standard library is used. Runs are resumable: a run is
skipped when its ``SUCCESS`` marker already exists (override with ``--force``).
Nothing under evals/skill-ab-2026-08-10/output/ is read by any session except the
judge attachments produced here; content from yesterday's
``/Users/macos/Documents/temp 2/siftline-v3-eval-2026-08-09`` is never passed to
generation or judge sessions (enforced by ``guard_no_forbidden``).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent.parent
TASKS_DIR = EVAL_DIR / "tasks"
OUTPUT_DIR = EVAL_DIR / "output"
GENERATED_DIR = OUTPUT_DIR / "generated"
JUDGED_DIR = OUTPUT_DIR / "judged"

SKILL_DIR = REPO_ROOT / "skills" / "siftline-research"
SKILL_MD = SKILL_DIR / "SKILL.md"
SKILL_REFERENCES = [
    SKILL_DIR / "references" / name
    for name in (
        "artifact-discovery.md",
        "platform-routing.md",
        "query-patterns.md",
        "relation-types.md",
    )
]
SKILL_DIRECTIVE = (
    "Use $siftline-research from /Users/macos/Documents/other_project/siftline/"
    "skills/siftline-research to solve this request"
)

MODEL_DEFAULT = "opencode-go/deepseek-v4-flash"
MODEL_QWEN_MAX = "opencode-go/qwen3.7-max"
DEFAULT_TIMEOUT = 3600
OPENCODE_MIN = (1, 18, 0)

FORBIDDEN_DIRS = [Path("/Users/macos/Documents/temp 2/siftline-v3-eval-2026-08-09").resolve()]
CONDITIONS = ("baseline", "skill")

TASKS = {
    "task1": {
        "name": "overclock",
        "project": "/Users/macos/Documents/game/overclock-protocol",
        "prompt": TASKS_DIR / "task1_overclock.md",
    },
    "task2": {
        "name": "worldloom",
        "project": "/Users/macos/Documents/game/worldloom",
        "prompt": TASKS_DIR / "task2_worldloom.md",
    },
    "task3": {
        "name": "poiema",
        "project": "/Users/macos/Documents/other_project/poiema",
        "prompt": TASKS_DIR / "task3_poiema.md",
    },
}

# Anonymous arm labels sent to judges. skill is X on task1/task3 and Y on task2
# so the condition label alternates; judges never see this file.
MAPPING = {
    "task1": {"X": "skill", "Y": "baseline"},
    "task2": {"X": "baseline", "Y": "skill"},
    "task3": {"X": "skill", "Y": "baseline"},
}

# One X-first and one Y-first judge, run by two different fresh models.
JUDGES = [
    {"id": "flash-xy", "model": MODEL_DEFAULT, "order": ["X", "Y"]},
    {"id": "qwenmax-yx", "model": MODEL_QWEN_MAX, "order": ["Y", "X"]},
]

DIMENSIONS = (
    "task_fidelity",
    "current_state_accuracy",
    "mechanism_understanding",
    "relation_platform_search",
    "demand_pain_evidence",
    "counterevidence_boundary",
    "action_value",
    "cost_length_efficiency",
)


class EvalError(Exception):
    """Fatal harness error (wrong spec, missing files, forbidden input)."""


class ProcRegistry:
    """Tracks live subprocesses so a Ctrl-C can terminate them."""

    def __init__(self) -> None:
        self._procs: set = set()
        self._lock = threading.Lock()

    def add(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.add(proc)

    def discard(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.discard(proc)

    def terminate_all(self) -> None:
        with self._lock:
            for proc in list(self._procs):
                with contextlib.suppress(Exception):
                    proc.terminate()


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return None
    return tuple(int(g) for g in match.groups())


def check_opencode(opencode_bin: str) -> str:
    try:
        proc = subprocess.run(
            [opencode_bin, "--version"], capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError as exc:
        raise EvalError(f"opencode executable not found: {opencode_bin!r}") from exc
    version = parse_version(proc.stdout + proc.stderr)
    if version is None:
        raise EvalError(f"cannot parse opencode version from: {proc.stdout + proc.stderr!r}")
    if version < OPENCODE_MIN:
        raise EvalError(
            f"opencode {'.'.join(map(str, version))} < required "
            f"{'.'.join(map(str, OPENCODE_MIN))}"
        )
    return ".".join(map(str, version))


def guard_no_forbidden(paths: list[Path]) -> None:
    """Raise if any path resolves under yesterday's eval dir (or equals it)."""
    for raw in paths:
        path = Path(raw).resolve()
        for forbidden in FORBIDDEN_DIRS:
            if path == forbidden or forbidden in path.parents:
                raise EvalError(
                    f"forbidden input would be passed to a session: {path} (under {forbidden})"
                )


def validate_spec() -> None:
    required_files = [
        SKILL_MD,
        *SKILL_REFERENCES,
        *(spec["prompt"] for spec in TASKS.values()),
        EVAL_DIR / "rubric.md",
    ]
    missing = [str(p) for p in required_files if not p.is_file()]
    if missing:
        raise EvalError("missing required files: " + ", ".join(missing))
    for task_id, spec in TASKS.items():
        if not Path(spec["project"]).is_dir():
            raise EvalError(f"project dir not found for {task_id}: {spec['project']}")
        if set(MAPPING[task_id]) != {"X", "Y"}:
            raise EvalError(f"mapping must define exactly X and Y for {task_id}")
        if set(MAPPING[task_id].values()) != set(CONDITIONS):
            raise EvalError(f"mapping must map X/Y to both conditions for {task_id}")
    orders = {tuple(j["order"]) for j in JUDGES}
    if orders != {("X", "Y"), ("Y", "X")}:
        raise EvalError("judge orders must be X,Y and Y,X")


def resolve_tasks(tokens: list[str]) -> list[str]:
    if not tokens:
        return list(TASKS)
    resolved = []
    for token in tokens:
        token = token.strip().lower()
        if not token.startswith("task"):
            token = f"task{token}"
        if token not in TASKS:
            raise EvalError(f"unknown task: {token} (expected one of {sorted(TASKS)})")
        resolved.append(token)
    return resolved


def build_generate_prompt(task_id: str, condition: str) -> tuple[str, list[Path]]:
    if task_id not in TASKS or condition not in CONDITIONS:
        raise EvalError(f"unknown task/condition: {task_id}/{condition}")
    body = TASKS[task_id]["prompt"].read_text(encoding="utf-8")
    if condition == "baseline":
        return body, []
    attachments = [SKILL_MD, *SKILL_REFERENCES]
    guard_no_forbidden(attachments)
    return f"{SKILL_DIRECTIVE}\n\n{body}", attachments


def parse_events(raw: str) -> list[dict]:
    events = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def summarize_session(raw: str, exit_code: int) -> dict:
    events = parse_events(raw)
    session_ids = {event.get("sessionID") for event in events if event.get("sessionID")}
    timestamps = [e.get("timestamp") for e in events if isinstance(e.get("timestamp"), int)]
    stop_message_ids = [
        (event.get("part") or {}).get("messageID")
        for event in events
        if event.get("type") == "step_finish"
        and (event.get("part") or {}).get("reason") == "stop"
        and isinstance((event.get("part") or {}).get("messageID"), str)
    ]
    final_stop_message_id = stop_message_ids[-1] if stop_message_ids else None
    text_parts: list[str] = []
    tool_counts: Counter[str] = Counter()
    bash_commands: list[str] = []
    steps: list[dict] = []
    step_index = 0
    for event in events:
        etype = event.get("type")
        part = event.get("part") or {}
        if etype == "text":
            text = part.get("text")
            # Final assistant text is only the text events of the last stop message;
            # intermediate narration before/around tool calls is excluded.
            if (
                isinstance(text, str)
                and final_stop_message_id is not None
                and part.get("messageID") == final_stop_message_id
            ):
                text_parts.append(text)
        elif etype == "tool_use":
            tool = part.get("tool")
            if isinstance(tool, str):
                tool_counts[tool] += 1
            state = part.get("state") or {}
            if tool == "bash" and isinstance(state.get("input"), dict):
                command = state["input"].get("command")
                if isinstance(command, str):
                    bash_commands.append(command)
        elif etype == "step_finish":
            tokens = part.get("tokens") or {}
            cache = tokens.get("cache") or {}
            steps.append(
                {
                    "step": step_index,
                    "reason": part.get("reason"),
                    "timestamp": event.get("timestamp"),
                    "tokens_total": tokens.get("total"),
                    "input": tokens.get("input"),
                    "output": tokens.get("output"),
                    "reasoning": tokens.get("reasoning"),
                    "cache_read": cache.get("read"),
                    "cache_write": cache.get("write"),
                    "cost": part.get("cost"),
                }
            )
            step_index += 1
    totals = {
        "total": 0,
        "input": 0,
        "output": 0,
        "reasoning": 0,
        "cache_read": 0,
        "cache_write": 0,
        "cost": 0.0,
    }
    step_key = {
        "total": "tokens_total",
        "input": "input",
        "output": "output",
        "reasoning": "reasoning",
        "cache_read": "cache_read",
        "cache_write": "cache_write",
    }
    for step in steps:
        for key, source in step_key.items():
            if isinstance(step[source], (int, float)):
                totals[key] += step[source]
        if isinstance(step.get("cost"), (int, float)):
            totals["cost"] += step["cost"]
    siftline_re = re.compile(r"\bsiftline\b")
    siftline_calls = sum(1 for command in bash_commands if siftline_re.search(command))
    external_re = re.compile(r"\bsiftline\b|\bcurl\b|\bwget\b|\bgh api\b|\bwebfetch\b")
    external_ops = tool_counts.get("webfetch", 0) + sum(
        1 for command in bash_commands if external_re.search(command)
    )
    return {
        "session_id": next(iter(session_ids)) if session_ids else None,
        "wall_time_ms": max(timestamps) - min(timestamps) if len(timestamps) >= 2 else 0,
        "exit_code": exit_code,
        "final_stop_message_id": final_stop_message_id,
        "text_parts": text_parts,
        "steps": steps,
        "totals": totals,
        "tool_counts": dict(tool_counts),
        "bash_commands": bash_commands,
        "siftline_calls": siftline_calls,
        "external_ops": external_ops,
        "n_events": len(events),
    }


def run_session(
    opencode_bin: str,
    message: str,
    model: str,
    attachments: list[Path],
    workdir: Path,
    registry: ProcRegistry | None,
    timeout: int | None,
) -> tuple[int, str, str, list[str], bool]:
    """Run one opencode session; return (exit_code, stdout, stderr, command, timed_out).

    ``timeout=None`` disables the timeout. On timeout the process is terminated
    (SIGTERM, then SIGKILL if needed) and whatever partial output arrived is
    returned so the caller can still save it.
    """
    guard_no_forbidden([*attachments, workdir])
    command = [
        opencode_bin,
        "run",
        message,
        "--pure",
        "--auto",
        "--format",
        "json",
        "-m",
        model,
        "--dir",
        str(workdir),
    ]
    for attachment in attachments:
        command += ["-f", str(attachment)]
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if registry is not None:
        registry.add(proc)
    timed_out = False
    try:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            with contextlib.suppress(Exception):
                proc.terminate()
            try:
                out, err = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(Exception):
                    proc.kill()
                out, err = proc.communicate()
    finally:
        if registry is not None:
            registry.discard(proc)
    return proc.returncode, out, err, command, timed_out


def run_is_done(run_dir: Path) -> bool:
    return (run_dir / "SUCCESS").is_file()


def copy_attachments(attachments: list[Path], dest_dir: Path) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copies = []
    for src in attachments:
        guard_no_forbidden([src])
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        copies.append(str(dest))
    return copies


def arm_label(task_id: str, condition: str) -> str:
    return next(label for label, cond in MAPPING[task_id].items() if cond == condition)


def extract_json_object(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def generate_one(args: argparse.Namespace, task_id: str, condition: str) -> dict:
    run_dir = GENERATED_DIR / task_id / condition
    if not args.force and run_is_done(run_dir):
        return {"task_id": task_id, "condition": condition, "status": "skipped"}
    run_dir.mkdir(parents=True, exist_ok=True)
    message, attachments = build_generate_prompt(task_id, condition)
    if args.dry_run:
        preview = [args.opencode, "run", "--pure", "--auto", "--format", "json", "-m", args.model]
        preview += [str(att) for att in attachments]
        return {
            "task_id": task_id,
            "condition": condition,
            "status": "dry-run",
            "preview": preview,
        }
    workdir = Path(tempfile.mkdtemp(prefix=f"siftline-ab-{task_id}-{condition}-"))
    (run_dir / "prompt.txt").write_text(message, encoding="utf-8")
    copies = copy_attachments(attachments, run_dir / "attachments")
    started = now_iso()
    start_mono = time.monotonic()
    exit_code, out, err, command, timed_out = run_session(
        args.opencode,
        message,
        args.model,
        attachments,
        workdir,
        args.registry,
        None if args.timeout == 0 else args.timeout,
    )
    elapsed = round(time.monotonic() - start_mono, 3)
    (run_dir / "raw.jsonl").write_text(out, encoding="utf-8")
    (run_dir / "stderr.log").write_text(err, encoding="utf-8")
    summary = summarize_session(out, exit_code)
    status = "success" if exit_code == 0 and not timed_out else "failed"
    assistant = "\n".join(summary["text_parts"])
    meta = {
        "schema_version": "1",
        "kind": "generate",
        "task_id": task_id,
        "condition": condition,
        "arm_label": arm_label(task_id, condition),
        "model": args.model,
        "run_id": f"{int(time.time())}-{task_id}-{condition}",
        "project_path": TASKS[task_id]["project"],
        "command": command,
        "temp_cwd": str(workdir),
        "started_at": started,
        "finished_at": now_iso(),
        "elapsed_wall_clock_s": elapsed,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "timeout_seconds": args.timeout,
        "status": status,
        "session_id": summary["session_id"],
        "wall_time_ms": summary["wall_time_ms"],
        "assistant_chars": len(assistant),
        "assistant_stop_message_id": summary["final_stop_message_id"],
        "steps": summary["steps"],
        "totals": summary["totals"],
        "tool_counts": summary["tool_counts"],
        "siftline_calls": summary["siftline_calls"],
        "external_ops": summary["external_ops"],
        "n_events": summary["n_events"],
        "attachments": copies,
    }
    (run_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if exit_code == 0:
        (run_dir / "assistant.txt").write_text(assistant, encoding="utf-8")
        (run_dir / "SUCCESS").touch()
    return {
        "task_id": task_id,
        "condition": condition,
        "status": status,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "session_id": summary["session_id"],
        "elapsed_wall_clock_s": elapsed,
        "assistant_chars": meta["assistant_chars"],
    }


def build_arms_metadata(task_id: str, order: list[str]) -> str:
    lines = ["# 匿名臂元数据（不含条件标签）", ""]
    for arm in order:
        condition = MAPPING[task_id][arm]
        meta_path = GENERATED_DIR / task_id / condition / "meta.json"
        lines.append(f"## 臂 {arm}")
        if not meta_path.is_file():
            lines.append("- 无会话元数据")
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("status") != "success":
            lines.append(f"- 会话状态: {meta.get('status')} (exit {meta.get('exit_code')})")
            continue
        totals = meta.get("totals") or {}
        lines.extend(
            [
                f"- 输出长度(字符): {meta.get('assistant_chars')}",
                f"- 外部搜索/抓取次数: {meta.get('external_ops')}",
                f"- siftline 调用次数: {meta.get('siftline_calls')}",
                f"- 工具调用: {meta.get('tool_counts')}",
                f"- 总 token: {totals.get('total')} "
                f"(input {totals.get('input')}, output {totals.get('output')}, "
                f"reasoning {totals.get('reasoning')}, cache_read {totals.get('cache_read')})",
                f"- 总成本(USD): {totals.get('cost')}",
                f"- 墙钟时长(s): {round((meta.get('wall_time_ms') or 0) / 1000, 1)}",
                f"- 退出码: {meta.get('exit_code')}",
            ]
        )
        lines.append("")
    return "\n".join(lines)


def build_judge_message(task_id: str, order: list[str]) -> str:
    rubric = (EVAL_DIR / "rubric.md").read_text(encoding="utf-8")
    spec = TASKS[task_id]
    header = (
        f"\n\n## 本次实例\n"
        f"- task_id: {task_id}\n"
        f"- 项目路径: {spec['project']}\n"
        f"- 臂顺序（附件展示顺序）: {order[0]} 先，{order[1]} 后\n"
        f"- 附件说明: task.md = 共享任务正文；arm_{order[0]}.txt 与 arm_{order[1]}.txt "
        f"= 两个臂的最终产出（按上述顺序）；meta_arms.md = 匿名元数据。\n"
        f"- 只输出 rubric 规定的严格 JSON，winner 只能是 {order[0]} 或 {order[1]}。\n"
    )
    return rubric + header


def build_judge_attachments(task_id: str, order: list[str]) -> list[tuple[str, object]]:
    spec = TASKS[task_id]
    entries: list[tuple[str, object]] = [("task.md", spec["prompt"])]
    for arm in order:
        condition = MAPPING[task_id][arm]
        src = GENERATED_DIR / task_id / condition / "assistant.txt"
        if not src.is_file():
            raise EvalError(f"missing arm output for {task_id}/{arm}: {src}")
        entries.append((f"arm_{arm}.txt", src))
    entries.append(("meta_arms.md", build_arms_metadata(task_id, order)))
    return entries


def judge_one(args: argparse.Namespace, task_id: str, judge: dict) -> dict:
    run_dir = JUDGED_DIR / task_id / judge["id"]
    if not args.force and run_is_done(run_dir):
        return {"task_id": task_id, "judge_id": judge["id"], "status": "skipped"}
    run_dir.mkdir(parents=True, exist_ok=True)
    message = build_judge_message(task_id, judge["order"])
    entries = build_judge_attachments(task_id, judge["order"])
    if args.dry_run:
        preview = [
            args.opencode,
            "run",
            "--pure",
            "--auto",
            "--format",
            "json",
            "-m",
            judge["model"],
        ]
        return {
            "task_id": task_id,
            "judge_id": judge["id"],
            "status": "dry-run",
            "preview": preview,
        }
    workdir = Path(tempfile.mkdtemp(prefix=f"siftline-ab-judge-{task_id}-{judge['id']}-"))
    (run_dir / "prompt.txt").write_text(message, encoding="utf-8")
    att_dir = run_dir / "attachments"
    att_dir.mkdir(parents=True, exist_ok=True)
    attachments: list[Path] = []
    copies: list[str] = []
    for name, src in entries:
        if isinstance(src, Path):
            guard_no_forbidden([src])
            dest = att_dir / name
            shutil.copy2(src, dest)
        else:
            dest = att_dir / name
            dest.write_text(str(src), encoding="utf-8")
        attachments.append(dest)
        copies.append(str(dest))
    started = now_iso()
    start_mono = time.monotonic()
    exit_code, out, err, command, timed_out = run_session(
        args.opencode,
        message,
        judge["model"],
        attachments,
        workdir,
        args.registry,
        None if args.timeout == 0 else args.timeout,
    )
    elapsed = round(time.monotonic() - start_mono, 3)
    (run_dir / "raw.jsonl").write_text(out, encoding="utf-8")
    (run_dir / "stderr.log").write_text(err, encoding="utf-8")
    summary = summarize_session(out, exit_code)
    status = "success" if exit_code == 0 and not timed_out else "failed"
    assistant = "\n".join(summary["text_parts"])
    parsed = extract_json_object(assistant)
    meta = {
        "schema_version": "1",
        "kind": "judge",
        "task_id": task_id,
        "judge_id": judge["id"],
        "model": judge["model"],
        "arm_order": judge["order"],
        "run_id": f"{int(time.time())}-{task_id}-{judge['id']}",
        "project_path": TASKS[task_id]["project"],
        "command": command,
        "temp_cwd": str(workdir),
        "started_at": started,
        "finished_at": now_iso(),
        "elapsed_wall_clock_s": elapsed,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "timeout_seconds": args.timeout,
        "status": status,
        "session_id": summary["session_id"],
        "wall_time_ms": summary["wall_time_ms"],
        "assistant_chars": len(assistant),
        "assistant_stop_message_id": summary["final_stop_message_id"],
        "answer_parsed": parsed is not None,
        "steps": summary["steps"],
        "totals": summary["totals"],
        "tool_counts": summary["tool_counts"],
        "attachments": copies,
    }
    (run_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if parsed is not None:
        (run_dir / "result.json").write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if exit_code == 0:
        (run_dir / "assistant.txt").write_text(assistant, encoding="utf-8")
        (run_dir / "SUCCESS").touch()
    return {
        "task_id": task_id,
        "judge_id": judge["id"],
        "status": status,
        "answer_parsed": parsed is not None,
        "exit_code": exit_code,
        "timed_out": timed_out,
    }


def reprocess_one(run_dir: Path) -> dict:
    """Re-extract assistant.txt from an existing generated run's raw.jsonl.

    No model is run. Failed runs and runs without a final ``reason=stop`` are
    skipped (and any stale SUCCESS marker is removed, so a later ``generate``
    re-runs them); SUCCESS is never faked.
    """
    raw_path = run_dir / "raw.jsonl"
    meta_path = run_dir / "meta.json"
    success_path = run_dir / "SUCCESS"
    label = f"{run_dir.parent.name}/{run_dir.name}"
    if not raw_path.is_file():
        return {"run": label, "status": "skip", "reason": "no raw.jsonl"}
    if not meta_path.is_file():
        return {"run": label, "status": "skip", "reason": "no meta.json"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("status") != "success":
        with contextlib.suppress(FileNotFoundError):
            success_path.unlink()
        return {"run": label, "status": "skip", "reason": f"run status {meta.get('status')!r}"}
    exit_code = meta.get("exit_code", 0)
    summary = summarize_session(raw_path.read_text(encoding="utf-8"), exit_code)
    if summary["final_stop_message_id"] is None:
        with contextlib.suppress(FileNotFoundError):
            success_path.unlink()
        return {"run": label, "status": "skip", "reason": "no final stop in raw.jsonl"}
    assistant = "\n".join(summary["text_parts"])
    (run_dir / "assistant.txt").write_text(assistant, encoding="utf-8")
    meta["assistant_chars"] = len(assistant)
    meta["assistant_stop_message_id"] = summary["final_stop_message_id"]
    meta["reprocessed"] = True
    meta["reprocessed_at"] = now_iso()
    meta["session_id"] = summary["session_id"]
    meta["wall_time_ms"] = summary["wall_time_ms"]
    meta["totals"] = summary["totals"]
    meta["steps"] = summary["steps"]
    meta["tool_counts"] = summary["tool_counts"]
    meta["siftline_calls"] = summary["siftline_calls"]
    meta["external_ops"] = summary["external_ops"]
    meta["n_events"] = summary["n_events"]
    (run_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if exit_code == 0:
        success_path.touch()
    else:
        with contextlib.suppress(FileNotFoundError):
            success_path.unlink()
    return {
        "run": label,
        "status": "reprocessed",
        "assistant_chars": len(assistant),
        "exit_code": exit_code,
    }


def run_many(jobs: list[tuple[str, object]], workers: int, registry: ProcRegistry) -> dict:
    results: dict = {}

    def invoke(name: str, fn: object) -> dict:
        try:
            return fn() if callable(fn) else {}
        except Exception as exc:  # noqa: BLE001 - record any worker failure
            return {"name": name, "status": "error", "error": str(exc)}

    if workers <= 1:
        for name, fn in jobs:
            results[name] = invoke(name, fn)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_name = {pool.submit(invoke, name, fn): name for name, fn in jobs}
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                results[name] = future.result()
    return results


def print_results(results: dict) -> None:
    for name in sorted(results):
        entry = results[name]
        if entry.get("status") == "skipped":
            print(f"  {name}: skipped (already complete)")
        elif entry.get("status") == "dry-run":
            preview = entry.get("preview")
            if preview:
                print(f"  {name}: dry-run (would run): {' '.join(preview)}")
            else:
                print(f"  {name}: dry-run (would run)")
        elif entry.get("status") == "error":
            print(f"  {name}: error: {entry.get('error')}")
        else:
            suffix = " (timed out)" if entry.get("timed_out") else ""
            print(f"  {name}: {entry.get('status')} exit={entry.get('exit_code')}{suffix}")


def write_manifest() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated: dict = {}
    for task_id in TASKS:
        generated[task_id] = {}
        for condition in CONDITIONS:
            meta_path = GENERATED_DIR / task_id / condition / "meta.json"
            if meta_path.is_file():
                generated[task_id][condition] = json.loads(meta_path.read_text(encoding="utf-8"))
            else:
                generated[task_id][condition] = None
    judged: dict = {}
    for task_id in TASKS:
        judged[task_id] = {}
        for judge in JUDGES:
            meta_path = JUDGED_DIR / task_id / judge["id"] / "meta.json"
            if meta_path.is_file():
                judged[task_id][judge["id"]] = json.loads(meta_path.read_text(encoding="utf-8"))
            else:
                judged[task_id][judge["id"]] = None
    manifest = {
        "schema_version": "1",
        "generated": generated,
        "judged": judged,
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def resolve_winner(task_id: str, winner: str) -> str | None:
    if winner == "tie":
        return "tie"
    if winner not in ("X", "Y"):
        return None
    return MAPPING[task_id][winner]


def summarize_generated(meta: dict | None) -> dict:
    if meta is None:
        return {"available": False}
    return {
        "available": meta.get("status") == "success",
        "status": meta.get("status"),
        "exit_code": meta.get("exit_code"),
        "session_id": meta.get("session_id"),
        "wall_time_ms": meta.get("wall_time_ms"),
        "elapsed_wall_clock_s": meta.get("elapsed_wall_clock_s"),
        "assistant_chars": meta.get("assistant_chars"),
        "tokens": meta.get("totals"),
        "cost_usd": (meta.get("totals") or {}).get("cost"),
        "tool_counts": meta.get("tool_counts"),
        "siftline_calls": meta.get("siftline_calls"),
        "external_ops": meta.get("external_ops"),
        "steps": len(meta.get("steps") or []),
    }


def aggregate_judge(task_id: str, entry: dict) -> dict:
    result = entry.get("result")
    meta = entry.get("meta")
    base = {
        "judge_id": entry["judge_id"],
        "model": entry["model"],
        "order": entry["order"],
        "available": False,
    }
    if result is None or meta is None or meta.get("status") != "success":
        return base
    base["available"] = True
    base["answer_parsed"] = meta.get("answer_parsed")
    base["winner"] = result.get("winner")
    base["winner_condition"] = resolve_winner(task_id, result.get("winner"))
    base["totals"] = result.get("totals")
    base["penalty"] = result.get("penalty")
    base["confidence"] = result.get("confidence")
    base["scores"] = result.get("scores")
    base["quality_increment_worth_cost"] = result.get("quality_increment_worth_cost")
    base["reasons"] = result.get("reasons")
    base["winner_biggest_defect"] = result.get("winner_biggest_defect")
    base["spot_checks"] = result.get("spot_checks")
    return base


def collect_summary_data(task_ids: list[str]) -> dict:
    generated: dict = {}
    for task_id in task_ids:
        generated[task_id] = {}
        for condition in CONDITIONS:
            meta_path = GENERATED_DIR / task_id / condition / "meta.json"
            if meta_path.is_file():
                generated[task_id][condition] = json.loads(meta_path.read_text(encoding="utf-8"))
            else:
                generated[task_id][condition] = None
    judged: dict = {}
    for task_id in task_ids:
        judged[task_id] = {}
        for judge in JUDGES:
            meta_path = JUDGED_DIR / task_id / judge["id"] / "meta.json"
            result_path = JUDGED_DIR / task_id / judge["id"] / "result.json"
            entry = {"judge_id": judge["id"], "model": judge["model"], "order": judge["order"]}
            if meta_path.is_file():
                entry["meta"] = json.loads(meta_path.read_text(encoding="utf-8"))
            else:
                entry["meta"] = None
            if result_path.is_file():
                entry["result"] = json.loads(result_path.read_text(encoding="utf-8"))
            else:
                entry["result"] = None
            judged[task_id][judge["id"]] = entry
    return {"generated": generated, "judged": judged}


def aggregate_summary(data: dict) -> dict:
    tasks_out: dict = {}
    for task_id in data["generated"]:
        generated_out = {
            condition: summarize_generated(meta)
            for condition, meta in data["generated"][task_id].items()
        }
        judges_out = [
            aggregate_judge(task_id, entry)
            for entry in (data["judged"].get(task_id) or {}).values()
        ]
        available = [j for j in judges_out if j["available"]]
        tasks_out[task_id] = {
            "name": TASKS[task_id]["name"],
            "project": TASKS[task_id]["project"],
            "generated": generated_out,
            "judges": judges_out,
            "skill_wins": sum(1 for j in available if j["winner_condition"] == "skill"),
            "baseline_wins": sum(1 for j in available if j["winner_condition"] == "baseline"),
            "ties": sum(1 for j in available if j["winner_condition"] == "tie"),
            "unavailable_judges": len(judges_out) - len(available),
        }
    return {"schema_version": "1", "tasks": tasks_out}


def render_summary_markdown(aggregated: dict) -> str:
    lines = [
        "# skill-ab-2026-08-10 — 自动聚合（不替代最终人工解释）",
        "",
        "> 本文件由 `run_ab.py summary` 自动生成，仅做结构化聚合。",
        "> 最终结论必须由人工结合 output/generated 与 output/judged 下的原始产出、",
        "> 匿名映射（mapping.json）与成本记录后给出。",
        "",
    ]
    total_skill = 0
    total_baseline = 0
    total_ties = 0
    for task_id, task_out in aggregated["tasks"].items():
        gen = task_out["generated"]
        lines.append(f"## {task_id}（{task_out['name']}）")
        lines.append("")
        lines.append("### 生成会话（generated）")
        lines.append("")
        lines.append(
            "| 条件 | 状态 | exit | session_id | 时长s | token | 成本USD | 字符 | "
            "siftline | 外部op |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for condition in CONDITIONS:
            g = gen[condition]
            if not g["available"]:
                lines.append(f"| {condition} | 无 | - | - | - | - | - | - | - | - |")
                continue
            tokens = g.get("tokens") or {}
            lines.append(
                f"| {condition} | {g['status']} | {g['exit_code']} | `{g['session_id']}` | "
                f"{round((g['wall_time_ms'] or 0) / 1000, 1)} | {tokens.get('total')} | "
                f"{round(g.get('cost_usd') or 0, 6)} | {g['assistant_chars']} | "
                f"{g.get('siftline_calls')} | {g.get('external_ops')} |"
            )
        lines.append("")
        lines.append("### 盲评（judged，臂按 X/Y 匿名）")
        lines.append("")
        lines.append(
            "| judge | 模型 | winner | winner条件 | X总分 | Y总分 | 罚X | 罚Y | 置信 | 值得成本 |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for j in task_out["judges"]:
            if not j["available"]:
                lines.append(
                    f"| {j['judge_id']} | {j['model']} | - | - | - | - | - | - | - | - |"
                )
                continue
            totals = j.get("totals") or {}
            penalty = j.get("penalty") or {}
            lines.append(
                f"| {j['judge_id']} | {j['model']} | {j['winner']} | {j['winner_condition']} | "
                f"{totals.get('X')} | {totals.get('Y')} | {penalty.get('X')} | "
                f"{penalty.get('Y')} | {j['confidence']} | {j['quality_increment_worth_cost']} |"
            )
        lines.append("")
        lines.append(
            f"本任务计数：skill 胜 {task_out['skill_wins']}，baseline 胜 "
            f"{task_out['baseline_wins']}，平局 {task_out['ties']}，"
            f"裁判不可用 {task_out['unavailable_judges']}。"
        )
        lines.append("")
        total_skill += task_out["skill_wins"]
        total_baseline += task_out["baseline_wins"]
        total_ties += task_out["ties"]
    lines.append("## 汇总")
    lines.append("")
    lines.append(f"skill 胜 {total_skill}，baseline 胜 {total_baseline}，平局 {total_ties}。")
    lines.append("")
    lines.append(
        "以上计数仅做展示；胜负与质量增量是否值得成本，请人工结合各裁判 "
        "reasons/spot_checks 判定。"
    )
    return "\n".join(lines)


def cmd_generate(args: argparse.Namespace) -> None:
    version = check_opencode(args.opencode)
    validate_spec()
    tasks = resolve_tasks(args.tasks)
    conditions = [args.only] if args.only else list(CONDITIONS)
    jobs = [
        (
            f"{task_id}/{condition}",
            lambda t=task_id, c=condition: generate_one(args, t, c),
        )
        for task_id in tasks
        for condition in conditions
    ]
    print(f"[generate] opencode {version}; {len(jobs)} sessions, jobs={args.jobs}")
    results = run_many(jobs, args.jobs, args.registry)
    print_results(results)
    write_manifest()
    if any(r.get("status") == "failed" for r in results.values()):
        raise EvalError("at least one generation session failed; inspect stderr.log/raw.jsonl")


def cmd_judge(args: argparse.Namespace) -> None:
    version = check_opencode(args.opencode)
    validate_spec()
    tasks = resolve_tasks(args.tasks)
    jobs = [
        (
            f"{task_id}/{judge['id']}",
            lambda t=task_id, j=judge: judge_one(args, t, j),
        )
        for task_id in tasks
        for judge in JUDGES
    ]
    print(f"[judge] opencode {version}; {len(jobs)} judge sessions, jobs={args.jobs}")
    results = run_many(jobs, args.jobs, args.registry)
    print_results(results)
    write_manifest()
    if any(r.get("status") == "failed" for r in results.values()):
        raise EvalError("at least one judge session failed; inspect stderr.log/raw.jsonl")


def cmd_reprocess(args: argparse.Namespace) -> None:
    tasks = resolve_tasks(args.tasks)
    conditions = [args.only] if args.only else list(CONDITIONS)
    entries = [
        reprocess_one(GENERATED_DIR / task_id / condition)
        for task_id in tasks
        for condition in conditions
    ]
    print("[reprocess] no model runs; re-extracting assistant from existing raw.jsonl")
    done = 0
    skipped = 0
    for entry in sorted(entries, key=lambda e: e.get("run", "")):
        if entry["status"] == "reprocessed":
            done += 1
            print(
                f"  {entry['run']}: reprocessed chars={entry['assistant_chars']} "
                f"exit={entry['exit_code']}"
            )
        else:
            skipped += 1
            print(f"  {entry['run']}: skip ({entry['reason']})")
    print(f"[reprocess] {done} reprocessed, {skipped} skipped")
    write_manifest()


def cmd_summary(args: argparse.Namespace) -> None:
    tasks = resolve_tasks(args.tasks)
    data = collect_summary_data(tasks)
    aggregated = aggregate_summary(data)
    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(aggregated, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = Path(args.markdown)
    md_path.write_text(render_summary_markdown(aggregated), encoding="utf-8")
    print(f"[summary] wrote {json_path} and {md_path}")


def cmd_all(args: argparse.Namespace) -> None:
    cmd_generate(args)
    cmd_judge(args)
    cmd_summary(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_ab.py",
        description="A/B harness for the siftline-research skill.",
    )
    parser.add_argument("--opencode", default="opencode", help="path to the opencode binary")
    sub = parser.add_subparsers(dest="command", required=True)

    common = {
        "tasks": (
            ["--tasks"],
            {"nargs": "*", "default": [], "help": "task ids/numbers (default: all)"},
        ),
        "jobs": (
            ["--jobs"],
            {"type": int, "default": 2, "help": "parallel sessions (default 2)"},
        ),
        "force": (
            ["--force"],
            {"action": "store_true", "help": "rerun even if SUCCESS exists"},
        ),
        "dry_run": (
            ["--dry-run"],
            {"action": "store_true", "help": "plan sessions without running"},
        ),
    }

    def add_common(p: argparse.ArgumentParser) -> None:
        for names, kwargs in common.values():
            p.add_argument(*names, **kwargs)

    def add_timeout(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--timeout",
            type=int,
            default=DEFAULT_TIMEOUT,
            help=f"per-session timeout seconds; 0 disables (default {DEFAULT_TIMEOUT})",
        )

    p_gen = sub.add_parser("generate", help="run generation sessions")
    add_common(p_gen)
    add_timeout(p_gen)
    p_gen.add_argument("--only", choices=list(CONDITIONS), default=None, help="only one condition")
    p_gen.add_argument(
        "--model", default=MODEL_DEFAULT, help=f"generation model (default {MODEL_DEFAULT})"
    )
    p_gen.set_defaults(handler=cmd_generate)

    p_judge = sub.add_parser("judge", help="run judge sessions")
    add_common(p_judge)
    add_timeout(p_judge)
    p_judge.set_defaults(handler=cmd_judge)

    p_all = sub.add_parser("all", help="generate + judge + summary")
    add_common(p_all)
    add_timeout(p_all)
    p_all.add_argument(
        "--model", default=MODEL_DEFAULT, help=f"generation model (default {MODEL_DEFAULT})"
    )
    p_all.set_defaults(handler=cmd_all)

    p_reproc = sub.add_parser(
        "reprocess",
        help="re-extract assistant.txt from existing generated raw.jsonl (no model runs)",
    )
    p_reproc.add_argument(
        "--tasks", nargs="*", default=[], help="task ids/numbers (default: all)"
    )
    p_reproc.add_argument(
        "--only", choices=list(CONDITIONS), default=None, help="only one condition"
    )
    p_reproc.set_defaults(handler=cmd_reprocess)

    p_sum = sub.add_parser("summary", help="aggregate results (no human interpretation)")
    add_common(p_sum)
    p_sum.add_argument("--json", dest="json_out", default=str(OUTPUT_DIR / "summary.json"))
    p_sum.add_argument("--markdown", default=str(OUTPUT_DIR / "summary.md"))
    p_sum.set_defaults(handler=cmd_summary)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.registry = ProcRegistry()
    handler = args.handler
    if handler is None:
        parser.print_help()
        return 0
    try:
        handler(args)
    except KeyboardInterrupt:
        args.registry.terminate_all()
        print("\n[ab] interrupted; running sessions terminated", file=sys.stderr)
        return 130
    except EvalError as exc:
        print(f"[ab] error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
