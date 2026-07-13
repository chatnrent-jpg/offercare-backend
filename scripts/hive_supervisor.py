"""LangGraph hive supervisor — pytest gatekeeper with 2-strike loop prevention."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal, TypedDict

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:  # pragma: no cover - import guard for first-run setup
    print(
        "Hive supervisor requires langgraph and langchain-core.\n"
        "Install: pip install langgraph langchain-core",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_STRIKE_DEFAULT = 2
TRACE_TAIL_LINES = 48
HIVE_ERROR_ENV = "HIVE_LATEST_ERROR"
HIVE_STRIKE_ENV = "HIVE_STRIKE_COUNT"
HIVE_STATUS_ENV = "HIVE_STATUS"


class HiveState(TypedDict, total=False):
    """Stateful orchestration record for the multi-agent hive."""

    latest_error: str
    strike_count: int
    current_file_modified: str
    status: str


# ── Terminal chrome ──────────────────────────────────────────────────────────

_BANNER = r"""
+==================================================================+
|  VETTEDME HIVE SUPERVISOR                                      |
|  LangGraph - Gatekeeper - 2-Strike Loop Guard                    |
+==================================================================+
"""

_HALT_BANNER = r"""
+==================================================================+
|  CRITIC INTERVENTION REQUIRED: Loop detected.                    |
+==================================================================+
"""


def _ansi(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def _green(text: str) -> str:
    return _ansi("1;32", text)


def _yellow(text: str) -> str:
    return _ansi("1;33", text)


def _red(text: str) -> str:
    return _ansi("1;31", text)


def _cyan(text: str) -> str:
    return _ansi("1;36", text)


def _dim(text: str) -> str:
    return _ansi("2", text)


def _console_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _print_banner() -> None:
    _console_print(_cyan(_BANNER.strip()))


def _print_strike_card(strike_count: int, max_strikes: int, target: str, detail: str) -> None:
    line = "-" * 66
    _console_print(_yellow(f"\n+{line}+"))
    _console_print(_yellow(f"|  STRIKE {strike_count} / {max_strikes}".ljust(67) + "|"))
    _console_print(_yellow(f"|  Gatekeeper FAILED".ljust(67) + "|"))
    _console_print(_yellow(f"|  Target: {target[:54]}".ljust(67) + "|"))
    _console_print(_yellow(f"+{line}+"))
    _console_print(_dim(detail))


def _notify_halt(message: str) -> None:
    _console_print(_red(_HALT_BANNER.strip()))
    _console_print(_red(message))
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
                0,
                message,
                "VettedMe Hive Supervisor",
                0x10,  # MB_ICONHAND
            )
        except Exception:
            pass


def _sync_env(state: HiveState) -> None:
    os.environ[HIVE_ERROR_ENV] = str(state.get("latest_error") or "")
    os.environ[HIVE_STRIKE_ENV] = str(int(state.get("strike_count") or 0))
    os.environ[HIVE_STATUS_ENV] = str(state.get("status") or "RUNNING")


# ── Gatekeeper (pytest) ──────────────────────────────────────────────────────


def _python_executable() -> str:
    venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    venv_py_unix = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_py_unix.is_file():
        return str(venv_py_unix)
    return sys.executable


def _tail_text(blob: str, *, lines: int = TRACE_TAIL_LINES) -> str:
    rows = [row for row in blob.splitlines() if row.strip()]
    if len(rows) <= lines:
        return "\n".join(rows)
    return "\n".join(rows[-lines:])


def _run_pytest(*, pytest_args: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    cmd = [_python_executable(), "-m", "pytest", *pytest_args]
    _console_print(_dim(f"\n> Gatekeeper: {' '.join(cmd)}\n"))
    completed = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = "\n".join(
        part for part in (completed.stdout or "", completed.stderr or "") if part.strip()
    )
    if completed.returncode == 0:
        _console_print(combined or _green("pytest exited 0 with no captured output."))
    else:
        _console_print(_tail_text(combined))
    return completed.returncode, combined


def run_gatekeeper_node(state: HiveState) -> HiveState:
    """Run pytest; on pass mark SUCCESS, on fail capture trace and increment strikes."""
    next_state: HiveState = dict(state)
    next_state["status"] = "RUNNING"
    target = str(next_state.get("current_file_modified") or "(full suite)")
    pytest_args: list[str] = ["-q", "--tb=short"]
    if target and target != "(full suite)":
        pytest_args.append(target)

    exit_code, raw_trace = _run_pytest(pytest_args=pytest_args)

    if exit_code == 0:
        next_state["status"] = "SUCCESS"
        next_state["latest_error"] = ""
        _console_print(_green("\nPASS GATEKEEPER - status SUCCESS\n"))
        _sync_env(next_state)
        return next_state

    trace_tail = _tail_text(raw_trace)
    strike_count = int(next_state.get("strike_count") or 0) + 1
    next_state["strike_count"] = strike_count
    next_state["latest_error"] = trace_tail
    next_state["status"] = "RUNNING"
    _print_strike_card(
        strike_count,
        MAX_STRIKE_DEFAULT,
        target,
        "Captured pytest tail — routing to loop evaluator.",
    )
    _sync_env(next_state)
    return next_state


# ── Loop evaluator ───────────────────────────────────────────────────────────


def evaluate_loop_node(state: HiveState) -> HiveState:
    """Enforce 2-strike rule; publish error context for one correction attempt."""
    next_state: HiveState = dict(state)
    strike_count = int(next_state.get("strike_count") or 0)
    latest_error = str(next_state.get("latest_error") or "")
    max_strikes = MAX_STRIKE_DEFAULT

    feedback = SystemMessage(
        content=(
            "Hive loop evaluator — consecutive gatekeeper failure detected. "
            f"Strike {strike_count} of {max_strikes}."
        )
    )
    HumanMessage(content=latest_error or "(no trace captured)")
    _ = (feedback,)  # langchain message types wired for downstream agent hooks

    if strike_count >= max_strikes:
        next_state["status"] = "HALTED"
        halt_msg = (
            "CRITIC INTERVENTION REQUIRED: Loop detected.\n"
            f"Consecutive pytest failures: {strike_count}.\n"
            f"Active target: {next_state.get('current_file_modified') or '(full suite)'}\n"
            "Halt automation — human review required before re-running the hive."
        )
        _notify_halt(halt_msg)
        _sync_env(next_state)
        return next_state

    next_state["status"] = "RUNNING"
    os.environ[HIVE_ERROR_ENV] = latest_error
    _console_print(
        _cyan(
            f"\nCORRECTION WINDOW OPEN - strike {strike_count}/{max_strikes}. "
            f"{HIVE_ERROR_ENV} updated for agent retry.\n"
        )
    )
    if latest_error:
        _console_print(_dim("-- latest_error tail --"))
        _console_print(_dim(latest_error))
        _console_print(_dim("-- end tail --\n"))
    _sync_env(next_state)
    return next_state


# ── Routing ──────────────────────────────────────────────────────────────────


def route_after_gatekeeper(state: HiveState) -> Literal["evaluate_loop", "__end__"]:
    if state.get("status") == "SUCCESS":
        return "__end__"
    return "evaluate_loop"


def route_after_evaluate(state: HiveState) -> Literal["run_gatekeeper", "__end__"]:
    if state.get("status") == "HALTED":
        return "__end__"
    return "run_gatekeeper"


def build_hive_graph() -> StateGraph:
    graph = StateGraph(HiveState)
    graph.add_node("run_gatekeeper", run_gatekeeper_node)
    graph.add_node("evaluate_loop", evaluate_loop_node)
    graph.add_edge(START, "run_gatekeeper")
    graph.add_conditional_edges(
        "run_gatekeeper",
        route_after_gatekeeper,
        {"evaluate_loop": "evaluate_loop", "__end__": END},
    )
    graph.add_conditional_edges(
        "evaluate_loop",
        route_after_evaluate,
        {"run_gatekeeper": "run_gatekeeper", "__end__": END},
    )
    return graph


def run_hive(*, target_file: str | None = None) -> HiveState:
    _print_banner()
    initial: HiveState = {
        "latest_error": "",
        "strike_count": 0,
        "current_file_modified": target_file or "(full suite)",
        "status": "RUNNING",
    }
    _sync_env(initial)
    compiled = build_hive_graph().compile()
    final_state: HiveState = compiled.invoke(initial)
    status = str(final_state.get("status") or "RUNNING")
    _console_print(_cyan(f"\nHive session complete - status={status} - strikes={final_state.get('strike_count', 0)}\n"))
    return final_state


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VettedMe LangGraph hive supervisor — pytest gatekeeper with 2-strike halt.",
    )
    parser.add_argument(
        "--file",
        dest="target_file",
        default=None,
        help="Optional pytest target (file or node id). Default: full suite.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    final = run_hive(target_file=args.target_file)
    status = str(final.get("status") or "RUNNING")
    if status == "SUCCESS":
        return 0
    if status == "HALTED":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
