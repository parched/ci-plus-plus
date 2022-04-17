from __future__ import annotations

import argparse
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from posixpath import dirname, normpath
from textwrap import dedent

import ruamel.yaml

from ._validation import to_json_array, to_json_array_of_strings, to_json_object
from ._yaml import multiline

__version__ = "0.1.0"


def main():
    """Process command line arguments"""

    parser = argparse.ArgumentParser(description="Compile to GitHub Actions workflow.")
    parser.add_argument("input_file", help="Input CI++ YAML file")
    parser.add_argument("output_file", help="GitHub Actions workflow YAML file")

    args = parser.parse_args()

    input_file = Path(args.input_file)
    output_file = Path(args.output_file)

    yaml = ruamel.yaml.YAML()

    input_: object = yaml.load(input_file)  # type: ignore

    _process(input_)

    output_file.parent.mkdir(exist_ok=True, parents=True)
    yaml.dump(input_, output_file)  # type: ignore


_CIXX_JOB_NAME = "cixx"
_ACTIONS_CACHE_VERSION = "204c5fc6f17f75fc56021276acb5aa4b6a051d8e"


def _process(input_: object):
    input_ = to_json_object(input_, "top level")

    # on = to_json_object(input_["on"], "on")  # pylint: disable=invalid-name
    jobs = to_json_object(input_["jobs"], "jobs")

    targets = {}
    # for key, event in on.items():
    #     event = to_json_object(event, f"on.{key}")
    #     # TODO: not all events are objects
    #     targets[key] = event.pop("targets")

    psuedo_jobs = {}
    normal_job_details = dict[str, _JobDetails]()
    normal_jobs = dict[str, dict[str, object]]()

    for job_key in list(jobs):  # copy before modify
        job = to_json_object(jobs[job_key], f"jobs.{job_key}")
        if "steps" in job:
            normal_job_details[job_key] = _process_job(job_key, job)
            normal_jobs[job_key] = job
        else:
            psuedo_jobs[job_key] = jobs.pop(job_key)

    jobs[_CIXX_JOB_NAME] = _create_cixx_job(targets, normal_job_details, psuedo_jobs)

    for job_name, job in normal_jobs.items():
        _insert_extra_steps(job_name, job, normal_job_details)


@dataclass(frozen=True, slots=True)
class _JobDetails:
    paths: list[str]
    output_paths: list[str]
    extra_key: str
    needs: list[str]
    force: bool


def _process_job(key: str, job: dict[str, object]) -> _JobDetails:
    paths = to_json_array_of_strings(job.pop("paths", ["./"]), f"jobs.{key}.paths")

    output_paths = to_json_array_of_strings(
        job.pop("output-paths", []), f"jobs.{key}.output-paths"
    )

    extra_key = job.pop("extra-key", "")
    if not isinstance(extra_key, str):
        raise TypeError(f"jobs.{key}.extra-key")

    force = job.pop("force", False)
    if not isinstance(force, bool):
        raise TypeError(f"jobs.{key}.force")

    if "needs" not in job:
        job["needs"] = []

    needs_orig = to_json_array_of_strings(job["needs"], f"jobs.{key}.needs")

    needs = list(needs_orig)
    needs_orig.append(_CIXX_JOB_NAME)

    # TODO: combine with existing "if"
    job["if"] = " && ".join(
        [
            "always()",
            f"(needs.{_CIXX_JOB_NAME}.result == 'success')",
            *(
                f"(needs.{job}.result == 'success' || needs.{job}.result == 'skipped')"
                for job in needs
            ),
            f"(needs.{_CIXX_JOB_NAME}.outputs.{_needs_build_output(key)} == 'true')",
        ]
    )

    return _JobDetails(
        paths=paths,
        output_paths=output_paths,
        extra_key=extra_key,
        needs=needs,
        force=force,
    )


def _insert_extra_steps(
    job_name: str, job: dict[str, object], jobs: Mapping[str, _JobDetails]
):
    job_details = jobs[job_name]

    pre_steps = [
        _get_clone_step(job_details.paths),
        *_get_zstd_steps(),
        *_get_needs_restore_steps(job_details.needs, jobs),
    ]
    post_steps = [
        _get_commit_step(job_name, job_details.output_paths),
    ]

    steps = to_json_array(job["steps"], f"jobs.{job_name}.steps")

    steps[0:0] = pre_steps
    steps[len(steps) :] = post_steps


def _get_clone_step(paths: Sequence[str]) -> dict[str, object]:
    quoted_dirs = " ".join(f'"{dir}"' for dir in _get_sparse_cone_dirs(paths))
    return {
        # TODO: handle self hosted where directory might not be clean
        # and we want to re-use at least it's git objects
        "id": "git-fetch",
        "name": "Git fetch",
        "shell": "bash",
        "run": multiline(
            # pylint: disable-next=consider-using-f-string  # too many braces
            """\
git init .
git remote add origin \
"https://x-access-token:${{secrets.GITHUB_TOKEN}}@github.com/${GITHUB_REPOSITORY}.git"
git config --local gc.auto 0
git sparse-checkout init --cone
git sparse-checkout set %s
git -c protocol.version=2 fetch --depth=1 origin ${GITHUB_SHA}
"""
            % quoted_dirs
        ),
    }


def _get_zstd_steps() -> list[dict[str, object]]:
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
    needs: Sequence[str], jobs: Mapping[str, _JobDetails]
) -> list[dict[str, object]]:
    return [
        {
            "name": f"Restore {need}",
            "uses": f"martijnhols/actions-cache/restore@{_ACTIONS_CACHE_VERSION}",
            "with": {
                "path": "\n".join(jobs[need].output_paths),
                "key": "${{ " f"needs.cixx.outputs.{_key_output(need)}" " }}",
            },
        }
        for need in needs
        if jobs[need].output_paths
    ]


def _get_commit_step(job_name: str, output_paths: Sequence[str]) -> dict[str, object]:
    return {
        "name": "Commit build",
        "uses": f"martijnhols/actions-cache/save@{_ACTIONS_CACHE_VERSION}",
        "with": {
            "path": "\n".join(output_paths),
            "key": "${{ " f"needs.cixx.outputs.{_key_output(job_name)}" " }}",
        },
    }


def _key_output(job_name: str) -> str:
    return f"key-{job_name}"


def _needs_build_output(job_name: str) -> str:
    return f"needs-build-{job_name}"


def _create_cixx_job(
    _targets: object, normal_jobs: Mapping[str, _JobDetails], _psuedo_jobs: object
) -> dict[str, object]:
    return {
        "runs-on": "ubuntu-20.04",
        "steps": [
            _get_git_fetch_step(),
            _get_key_generator_step(normal_jobs),
            *_get_cache_check_steps(normal_jobs),
        ],
        "outputs": {
            **{_key_output(name): _get_key_step_output(name) for name in normal_jobs},
            **{
                _needs_build_output(name): _get_cache_check_step_output(name)
                for name in normal_jobs
            },
        },
    }


def _get_git_fetch_step() -> dict[str, object]:
    return {
        # TODO: fetch without tags and depth=1 if describe not needed
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
git -c protocol.version=2 fetch --filter=blob:none --tags origin ${GITHUB_SHA}
last_tag=$(git describe --abbrev=0 --tags ${GITHUB_SHA})
count_since_last_tag=$(git rev-list "${last_tag}..${GITHUB_SHA}" --count)"
"""
        ),
    }


_KEY_GENERATION_STEP_ID = "generate-keys"


def _get_key_generator_step(jobs: Mapping[str, _JobDetails]) -> dict[str, object]:
    done = {}
    scripts = ["declare -A keys"]

    def add_job(name: str):
        if name in done:
            return

        job = jobs[name]

        # needs must come first
        for need in job.needs:
            add_job(need)

        paths_quoted = " ".join(f'"{normpath(path)}"' for path in job.paths)
        needs_quoted = " ".join(f'"${{keys[{need}]}}"' for need in job.needs)
        # TODO: include extra-key
        script = dedent(
            f"""\
            keys[{name}]="{name}-$(git-hash-files {paths_quoted} -- {needs_quoted})"
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


def _get_cache_check_steps(jobs: Mapping[str, _JobDetails]) -> list[dict[str, object]]:
    return [
        {
            "name": f"Check {name} cache",
            "id": _get_cache_check_step_id(name),
            "uses": f"martijnhols/actions-cache/check@{_ACTIONS_CACHE_VERSION}",
            "with": {
                "path": "\n".join(job.output_paths),
                "key": _get_key_step_output(name),
            },
        }
        for name, job in jobs.items()
    ]


def _get_sparse_cone_dirs(paths: Collection[str]) -> set[str]:
    return {normpath(dirname(path)) for path in paths}


# TODO: config object
