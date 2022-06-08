from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from ._validation import Json

INIT_JOB_ID = "cixx-init"

ACTIONS_CACHE_VERSION = "204c5fc6f17f75fc56021276acb5aa4b6a051d8e"


def outputs_file(job_name: str) -> str:
    """Return the filename for the job outputs"""
    return f"__cixx_outputs_{job_name}.json"


@dataclass(frozen=True, slots=True)
class JobDetails:
    """Settings for a job"""

    paths: list[str]
    output_paths: list[str]
    extra_key: str
    needs: list[str]
    force: bool
    outputs: Json


def _get_upstream_inclusive(
    job_name: str, jobs: Mapping[str, JobDetails]
) -> Mapping[str, JobDetails]:
    upstream = dict[str, JobDetails]()

    def add(name: str):
        if name in upstream:
            return
        job = jobs[name]
        upstream[name] = job
        for need in job.needs:
            add(need)

    add(job_name)

    return upstream


def is_implicitly_force(job_name: str, jobs: Mapping[str, JobDetails]) -> bool:
    """Returns whether this job will always run"""
    return any(job.force for job in _get_upstream_inclusive(job_name, jobs).values())


def key_output(job_name: str) -> str:
    """Returns the output ID for the cache key"""
    return f"key-{job_name}"


def needs_build_output(job_name: str) -> str:
    """Returns the output ID for the flag for needing a build"""
    return f"needs-build-{job_name}"
