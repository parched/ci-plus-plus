from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ruamel.yaml
from ruamel.yaml.representer import RoundTripRepresenter

from . import _github_actions as gh
from . import _init_job as init_job
from . import _normal_job as normal_job
from ._common import INIT_JOB_ID, JobDetails, outputs_file
from ._reuseable_workflow import expand_cixx_uses, replace_jobs_references
from ._transform import (
    flatten_nested_steps_and_expand_implicit_run,
    remove_x_properties,
)
from ._validation import Json, to_json_array_of_strings, to_json_object


def main():
    """Process command line arguments"""

    parser = argparse.ArgumentParser(description="Compile to GitHub Actions workflow.")
    parser.add_argument("input_file", help="Input CI++ YAML file")
    parser.add_argument(
        "output_file",
        nargs="?",
        help="GitHub Actions workflow YAML file, default stdout",
    )
    parser.add_argument(
        "--preprocess-only",
        "-E",
        action="store_true",
        help="Only expand YAML references, cixx-uses, nested steps, run strings",
    )

    args = parser.parse_args()

    input_file = Path(args.input_file)
    input_ = expand_cixx_uses(input_file)

    input_ = remove_x_properties(input_)
    input_ = flatten_nested_steps_and_expand_implicit_run(input_)

    input_ = replace_jobs_references(input_)

    if args.preprocess_only:
        output = input_
    else:
        output = _process(input_)

    if args.output_file:
        output_file = Path(args.output_file)
        output_file.parent.mkdir(exist_ok=True, parents=True)
    else:
        output_file = sys.stdout

    yaml = ruamel.yaml.YAML()

    class NonAliasingRTRepresenter(RoundTripRepresenter):
        """Removes aliases because they're not supported by github"""

        def ignore_aliases(self, data: object):
            return True

        def represent_scalar(self, tag, value, style=None, anchor=None):  # type: ignore
            return super().represent_scalar(tag, value, style)  # type: ignore

    yaml.Representer = NonAliasingRTRepresenter

    yaml.dump(output, output_file)  # type: ignore


def _process(input_: Json) -> gh.Workflow:
    input_ = to_json_object(input_, "top level")

    on = to_json_object(input_["on"], "on")  # pylint: disable=invalid-name
    jobs = to_json_object(input_["jobs"], "jobs")

    targets = {}
    # for key, event in on.items():
    #     event = to_json_object(event, f"on.{key}")
    #     # TODO: not all events are objects
    #     targets[key] = event.pop("targets")

    psuedo_jobs = {}
    normal_job_details = dict[str, JobDetails]()
    normal_jobs = dict[str, dict[str, Json]]()

    for job_key in list(jobs):  # copy before modify
        job = to_json_object(jobs[job_key], f"jobs.{job_key}")
        if "steps" in job:
            normal_job_details[job_key] = _process_job(job_key, job)
            normal_jobs[job_key] = job
        else:
            psuedo_jobs[job_key] = job

    on_out = on

    jobs_out = {
        INIT_JOB_ID: init_job.create(targets, normal_job_details, psuedo_jobs),
        **{
            job_name: normal_job.create(job_name, job, normal_job_details)
            for job_name, job in normal_jobs.items()
        },
    }

    return {
        "on": on_out,
        "jobs": jobs_out,
    }


def _process_job(key: str, job: dict[str, Json]) -> JobDetails:
    paths = to_json_array_of_strings(job.get("paths", ["./"]), f"jobs.{key}.paths")

    output_paths_raw = to_json_array_of_strings(
        job.get("output-paths", []), f"jobs.{key}.output-paths"
    )
    output_paths = [*output_paths_raw, outputs_file(key)]

    extra_key = job.get("extra-key", "")
    if not isinstance(extra_key, str):
        raise TypeError(f"jobs.{key}.extra-key")

    force = job.get("force", False)
    if not isinstance(force, bool):
        raise TypeError(f"jobs.{key}.force")

    needs = to_json_array_of_strings(job.get("needs", []), f"jobs.{key}.needs")

    outputs = job.get("outputs")

    return JobDetails(
        paths=paths,
        output_paths=output_paths,
        extra_key=extra_key,
        needs=needs,
        force=force,
        outputs=outputs,
    )


if __name__ == "__main__":
    main()
