from __future__ import annotations

from collections.abc import Mapping, Sequence
from posixpath import dirname, normpath
from typing import cast

from . import _github_actions as gh
from ._common import (
    ACTIONS_CACHE_VERSION,
    INIT_JOB_ID,
    JobDetails,
    is_implicitly_force,
    key_output,
    needs_build_output,
)
from ._validation import is_json_array, to_json_array, to_json_object, to_string
from ._yaml import multiline


def create(
    job_name: str, job: dict[str, object], jobs: Mapping[str, JobDetails]
) -> gh.Job:
    """Returns a tranformed job"""
    job_details = jobs[job_name]

    if_conditions = [
        "always()",
        f"(needs.{INIT_JOB_ID}.result == 'success')",
        *(
            f"(needs.{job}.result == 'success' || needs.{job}.result == 'skipped')"
            for job in job_details.needs
        ),
    ]
    if not is_implicitly_force(job_name, jobs):
        if_conditions.append(
            f"(needs.{INIT_JOB_ID}.outputs.{needs_build_output(job_name)}" " == 'true')"
        )

    if_out = " && ".join(if_conditions)

    needs_out = [INIT_JOB_ID, *job_details.needs]

    pre_steps = [
        *_get_clone_steps(job_details.paths),
        *_get_zstd_steps(),
        *_get_needs_restore_steps(job_details.needs, jobs),
    ]
    post_steps = [
        _get_commit_step(job_name, job_details.output_paths),
    ]

    steps = to_json_array(job["steps"], f"jobs.{job_name}.steps")

    steps_flattend = _flatten_array(steps)  # Allow nested for YAML anchors

    steps_out = [
        *pre_steps,
        *(
            gh.Step(run=step) if isinstance(step, str)
            # TODO: validate step
            else cast(gh.Step, to_json_object(step, f"jobs.{job_name}.steps[{i}]"))
            for i, step in enumerate(steps_flattend)
        ),
        *post_steps,
    ]

    return {
        "if": if_out,
        "needs": needs_out,
        "steps": steps_out,
        "runs-on": to_string(job["runs-on"], f"jobs.{job_name}.runs-on"),
    }


def _flatten_array(array: list[object]) -> list[object]:
    return [
        f
        for element in array
        for f in (_flatten_array(element) if is_json_array(element) else [element])
    ]


def _get_clone_steps(paths: Sequence[str]) -> list[gh.Step]:
    if not paths:
        return []

    if "./" in paths:
        sparse_checkout = ""
    else:
        patterns = [
            "/*",
            "!/*/",
        ]

        def add_dir(dir_: str, recursive: bool = False):
            if dir_ in (".", ""):
                return

            add_dir(dirname(dir_))

            pattern = f"/{dir_}/"
            anti_pattern = f"!/{dir_}/*/"

            if recursive and anti_pattern in patterns:
                patterns.remove(anti_pattern)
            if pattern not in patterns:
                patterns.append(pattern)
                if not recursive:
                    patterns.append(anti_pattern)

        for path in paths:
            if path.endswith("/"):
                add_dir(normpath(path), recursive=True)
            else:
                add_dir(dirname(normpath(path)))

        sparse_checkout = "\n".join(
            [
                "git sparse-checkout init --cone",
                "cat <<EOF > .git/info/sparse-checkout",
                *patterns,
                "EOF",
            ]
        )
    #
    #    def _get_sparse_cone_dirs(paths: Collection[str]) -> set[str]:
    #        return {normpath(dirname(path)) for path in paths}

    return [
        {
            # TODO: handle self hosted where directory might not be clean
            # and we want to re-use at least it's git objects
            "name": "Git clone",
            "shell": "bash",
            "run": multiline(
                # pylint: disable-next=consider-using-f-string  # too many braces
                """\
git init .
git remote add origin \
"https://x-access-token:${{secrets.GITHUB_TOKEN}}@github.com/${GITHUB_REPOSITORY}.git"
git config --local gc.auto 0
%s
git -c protocol.version=2 fetch --no-tags --depth=1 origin ${GITHUB_SHA}
git checkout ${GITHUB_SHA}
"""
                % sparse_checkout
            ),
        }
    ]


def _get_zstd_steps() -> list[gh.Step]:
    return [
        # Using a different version of tar from windows causes a cache miss with linux
        # https://github.com/actions/cache/issues/576#issuecomment-830796954
        {
            "if": "runner.os == 'Windows'",
            "name": "Use GNU tar instead BSD tar",
            "shell": "cmd",
            "run": r'echo C:\Program Files\Git\usr\bin>>"%GITHUB_PATH%"',
        },
        # If zstd is missing a different compression method will be used
        # and cause a cache miss
        {
            "name": "Check zstd on PATH",
            "shell": "bash",
            "run": "which zstd",
        },
    ]


def _get_needs_restore_steps(
    needs: Sequence[str], jobs: Mapping[str, JobDetails]
) -> list[gh.Step]:
    return [
        {
            "name": f"Restore {need}",
            "uses": f"martijnhols/actions-cache/restore@{ACTIONS_CACHE_VERSION}",
            "with": {
                "path": "\n".join(jobs[need].output_paths),
                "key": "${{ " f"needs.{INIT_JOB_ID}.outputs.{key_output(need)}" " }}",
            },
        }
        for need in needs
        if jobs[need].output_paths
    ]


def _get_commit_step(job_name: str, output_paths: Sequence[str]) -> gh.Step:
    return {
        "name": "Commit build",
        "uses": f"martijnhols/actions-cache/save@{ACTIONS_CACHE_VERSION}",
        "with": {
            "path": "\n".join(output_paths),
            "key": "${{ " f"needs.{INIT_JOB_ID}.outputs.{key_output(job_name)}" " }}",
        },
    }
