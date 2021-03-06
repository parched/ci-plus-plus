from pathlib import Path
from typing import Callable, TypeVar

import ruamel.yaml

from ._expressions import (
    get_full_expression_or_none,
    replace_full_expressions,
    replace_identifiers,
    to_expression,
)
from ._validation import Json, to_json_array_of_strings, to_json_object, to_string


# pylint: disable-next=too-many-locals  # should refactor this at some stage
def expand_cixx_uses(input_file: Path) -> dict[str, Json]:
    """Return the workflow with any cixx-uses expanded.

    Nested steps are useful when using YAML references
    """
    yaml = ruamel.yaml.YAML()

    input_object: Json = yaml.load(input_file)  # type: ignore
    input_ = to_json_object(input_object, f"{input_file}")

    jobs = to_json_object(input_["jobs"], f"{input_file}:jobs")
    new_jobs = dict[str, Json]()
    job_outputs = dict[str, Json]()

    for job_key in jobs:
        job = to_json_object(jobs[job_key], f"{input_file}:jobs.{job_key}")
        cixx_uses = job.get("cixx-uses")
        if cixx_uses is None:
            new_jobs[job_key] = job
        else:
            cixx_uses = to_string(cixx_uses, f"{input_file}:jobs.{job_key}.cixx-uses")
            inputs = job.get("with")

            # IDEA: support URLs, absolute paths, etc
            child = expand_cixx_uses(input_file.parent / cixx_uses)

            prefix = f"{job_key}-"
            while any(key.startswith(prefix) for key in jobs):
                prefix += "-"  # Make sure it's impossible to conflict

            child_fixed: dict[str, Json] = replace_identifiers(
                replace_full_expressions(
                    _add_job_prefix(child, prefix),
                    _get_full_expression_replacements("inputs", inputs),
                ),
                _get_expression_replacements("inputs", inputs),
            )

            # pylint: disable-next=unsubscriptable-object  # but it is
            new_jobs.update(to_json_object(child_fixed["jobs"], f"{child}:jobs"))
            on = to_json_object(  # pylint: disable=invalid-name
                # pylint: disable-next=unsubscriptable-object  # but it is
                child_fixed["on"],
                f"{child}:on",
            )
            cixx_call = to_json_object(on["cixx_call"], f"{child}:on:cixx_call")

            job_outputs[job_key] = cixx_call.get("outputs")

    outputs_full_replacements = [
        replacement
        for job, outputs in job_outputs.items()
        for context in ("needs", "jobs")
        for replacement in _get_full_expression_replacements(
            f"{context}.{job}.outputs", outputs
        )
    ]
    outputs_replacements = [
        replacement
        for job, outputs in job_outputs.items()
        for context in ("needs", "jobs")
        for replacement in _get_expression_replacements(
            f"{context}.{job}.outputs", outputs
        )
    ]
    with_new_jobs: dict[str, Json] = {**input_, "jobs": new_jobs}
    with_full_outputs_replacements: dict[str, Json] = replace_full_expressions(
        with_new_jobs, outputs_full_replacements
    )
    return replace_identifiers(with_full_outputs_replacements, outputs_replacements)


def _add_job_prefix(workflow: Json, prefix: str) -> dict[str, Json]:
    input_ = to_json_object(workflow, "top level")

    jobs = to_json_object(input_["jobs"], "jobs")
    new_jobs = {f"{prefix}{key}": value for key, value in jobs.items()}

    replacements = [
        (f"{context}.{job}", f"{context}.{prefix}{job}")
        for job in jobs
        for context in ("needs", "jobs")
    ]
    with_new_jobs: dict[str, Json] = {**input_, "jobs": new_jobs}
    return replace_identifiers(with_new_jobs, replacements)


_TJson1 = TypeVar("_TJson1", bound=Json)
_TJson2 = TypeVar("_TJson2", bound=Json)


def _get_replacements(
    name: str, obj: Json, replacer: Callable[[_TJson2], _TJson1]
) -> list[tuple[str, _TJson1]]:
    """Return the replacements with as much as can be expanded first"""
    replacements = list[tuple[str, _TJson1]]()
    match obj:
        case str():
            pass
        case float() | int() | bool() | None:
            pass
        case list():
            replacements.extend(
                (
                    replacement
                    for i, value in enumerate(obj)
                    for replacement in _get_replacements(
                        f"{name}[{i}]", value, replacer
                    )
                )
            )
        case dict():
            replacements.extend(
                (
                    replacement
                    for key, value in obj.items()
                    for replacement in _get_replacements(
                        f"{name}.{key}", value, replacer
                    )
                )
            )

    replacement = replacer(obj)
    replacements.append((name, replacement))
    return replacements


def _get_expression_replacements(name: str, obj: Json) -> list[tuple[str, str]]:
    return _get_replacements(name, obj, to_expression)


def _get_full_expression_replacements(name: str, obj: Json) -> list[tuple[str, Json]]:
    return _get_replacements(name, obj, lambda x: x)


def replace_jobs_references(input_: dict[str, Json]) -> dict[str, Json]:
    """Return the workflow with any jobs refenrences replace with needs.

    Nested steps are useful when using YAML references
    """
    jobs = to_json_object(input_["jobs"], "jobs")
    new_jobs = dict[str, Json]()
    for job_key in jobs:
        job = to_json_object(jobs[job_key], f"jobs.{job_key}")

        needs = to_json_array_of_strings(job.get("needs", []), f"jobs.{job_key}.needs")
        new_needs: list[Json] = [_replace_job_reference(need) for need in needs]

        new_job = replace_identifiers(job, [("jobs", "needs")])

        if new_needs:
            # pylint: disable-next=unsupported-assignment-operation
            new_job["needs"] = new_needs

        new_jobs[job_key] = new_job

    return {**input_, "jobs": new_jobs}


def _replace_job_reference(need: str) -> str:
    full_expression = get_full_expression_or_none(need)
    if full_expression is not None and full_expression.startswith("jobs."):
        return full_expression[5:]

    return need
