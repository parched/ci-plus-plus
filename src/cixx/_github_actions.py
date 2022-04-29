from __future__ import annotations

from typing import TypedDict

_Dict = dict[str, object]


class Workflow(TypedDict):
    """Top level object"""

    on: _Dict
    jobs: dict[str, Job]


Job = TypedDict(
    "Job",
    {
        "if": str,
        "needs": list[str],
        "steps": list[_Dict],
        "runs-on": str | list[str],
        "outputs": dict[str, str],
    },
    total=False,
)
