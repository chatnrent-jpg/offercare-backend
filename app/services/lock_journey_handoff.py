"""Lock handoff — journey pipeline preview after shift lock."""

from __future__ import annotations


def lock_journey_handoff_steps(*, vms_done: bool = False) -> list[dict]:
    return [
        {"label": "Locked", "done": True},
        {"label": "VMS confirmed", "done": vms_done},
        {"label": "Payroll", "done": False},
        {"label": "Paid", "done": False},
    ]
