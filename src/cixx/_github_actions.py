from __future__ import annotations

from typing import TypedDict

_Dict = dict[str, object]


class Workflow(TypedDict):
    """Top level object"""

    on: _Dict
    jobs: dict[str, Job]


Step = TypedDict(
    "Step",
    {
        "if": str,
        "name": str,
        "id": str,
        "shell": str,
        "run": str,
        "uses": str,
        "with": dict[str, str],
    },
    total=False,
)

Job = TypedDict(
    "Job",
    {
        "if": str,
        "needs": list[str],
        "steps": list[Step],
        "runs-on": str | list[str],
        "outputs": dict[str, str],
    },
    total=False,
)
