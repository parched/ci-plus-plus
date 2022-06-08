from ._validation import Json, is_json_array, to_json_array, to_json_object


def remove_x_properties(workflow: Json) -> dict[str, Json]:
    """Return workflow with 'x-' properties removed

    These are used for YAML references.
    """
    input_ = to_json_object(workflow, "top level")
    return {k: v for k, v in input_.items() if not k.startswith("x-")}


def flatten_nested_steps_and_expand_implicit_run(workflow: Json) -> dict[str, Json]:
    """Return the workflow with any nested job steps flattened.

    Nested steps are useful when using YAML references
    """
    input_ = to_json_object(workflow, "top level")

    jobs = to_json_object(input_["jobs"], "jobs")
    new_jobs = dict[str, Json]()

    for job_key in jobs:
        job = to_json_object(jobs[job_key], f"jobs.{job_key}")
        steps = job.get("steps")
        if steps:
            new_steps: list[Json] = [
                {"run": step} if isinstance(step, str) else step
                for step in _flatten_array(
                    to_json_array(steps, f"jobs.{job_key}.steps")
                )
            ]
            new_job: Json = {**job, "steps": new_steps}
        else:
            new_job = job

        new_jobs[job_key] = new_job

    return {**input_, "jobs": new_jobs}


def _flatten_array(array: list[Json]) -> list[Json]:
    return [
        f
        for element in array
        for f in (_flatten_array(element) if is_json_array(element) else [element])
    ]
