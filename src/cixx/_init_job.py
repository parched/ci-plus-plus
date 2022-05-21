from __future__ import annotations

from collections.abc import Mapping
from posixpath import normpath
from textwrap import dedent

from . import _github_actions as gh
from ._common import (
    ACTIONS_CACHE_VERSION,
    JobDetails,
    is_implicitly_force,
    key_output,
    needs_build_output,
)
from ._yaml import multiline


def create(
    _targets: object, normal_jobs: Mapping[str, JobDetails], _psuedo_jobs: object
) -> gh.Job:
    """Returns the initialization job."""
    return {
        "runs-on": "ubuntu-20.04",
        "steps": [
            _get_git_fetch_step(),
            _get_key_generator_step(normal_jobs),
            *_get_cache_check_steps(normal_jobs),
        ],
        "outputs": {
            **{key_output(name): _get_key_step_output(name) for name in normal_jobs},
            **{
                needs_build_output(name): _get_cache_check_step_output(name)
                for name in normal_jobs
                if not is_implicitly_force(name, normal_jobs)
            },
        },
    }


def _get_git_fetch_step() -> gh.Step:
    return {
        # TODO: handle self hosted where directory might not be clean
        # and we want to re-used= at least it's git objects
        "id": "git-fetch",
        "name": "Git fetch",
        "shell": "bash",
        "run": multiline(
            """\
git init .
git remote add origin \
"https://x-access-token:${{secrets.GITHUB_TOKEN}}@github.com/${GITHUB_REPOSITORY}.git"
git config --local gc.auto 0
git -c protocol.version=2 fetch --filter=blob:none --depth=1 origin ${GITHUB_SHA}
"""
        ),
    }


_KEY_GENERATION_STEP_ID = "generate-keys"


def _get_key_generator_step(jobs: Mapping[str, JobDetails]) -> gh.Step:
    done = {}
    scripts = ["declare -A keys"]

    def add_job(name: str):
        if name in done:
            return

        job = jobs[name]

        # needs must come first
        for need in job.needs:
            add_job(need)

        if is_implicitly_force(name, jobs):
            suffix = "$RANDOM$RANDOM"
        else:
            paths_quoted = " ".join(f'"{normpath(path)}"' for path in job.paths)
            needs_quoted = " ".join(f'"${{keys[{need}]}}"' for need in job.needs)
            suffix = f"$(git_hash_files {paths_quoted} -- {needs_quoted})"
        # TODO: include extra-key
        script = dedent(
            f"""\
            keys[{name}]="{name}-{suffix}"
            echo "::set-output name={name}::${{keys[{name}]}}"
            """
        )

        scripts.append(script)

    for name in jobs:
        add_job(name)

    return {
        "id": _KEY_GENERATION_STEP_ID,
        "name": "Generate keys",
        "shell": "bash",
        "run": multiline(
            dedent(
                """\
            function git_hash_files {
                local files="true"

                for file in "$@"
                do
                    if [ $files = "true" ]
                    then
                        if [ "$file" = "--" ]
                        then
                            files="false"
                        elif [ -n "$file" ]
                        then
                            sha=$(git rev-parse "${GITHUB_SHA}:$file")
                            echo "$file: $sha" 1>&2
                            echo -n $sha
                        fi
                    else
                        echo "string: $file" 1>&2
                        echo -n "$file"
                    fi
                done | git hash-object --stdin
            }
            """
            )
            + "\n".join(scripts)
        ),
    }


def _get_key_step_output(job_name: str) -> str:
    return "${{ " f"steps.{_KEY_GENERATION_STEP_ID}.outputs.{job_name}" " }}"


def _get_cache_check_step_output(job_name: str) -> str:
    return (
        "${{ "
        f"steps.{_get_cache_check_step_id(job_name)}.outputs.cache-hit != 'true'"
        " }}"
    )


def _get_cache_check_step_id(job_name: str) -> str:
    return f"check-cache-{job_name}"


def _get_cache_check_steps(jobs: Mapping[str, JobDetails]) -> list[gh.Step]:
    return [
        {
            "name": f"Check {name} cache",
            "id": _get_cache_check_step_id(name),
            "uses": f"martijnhols/actions-cache/check@{ACTIONS_CACHE_VERSION}",
            "with": {
                "path": "\n".join(job.output_paths),
                "key": _get_key_step_output(name),
            },
        }
        for name, job in jobs.items()
        if not is_implicitly_force(name, jobs)
    ]
