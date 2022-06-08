from __future__ import annotations

from typing import TypeGuard

Json = int | float | bool | str | None | list["Json"] | dict[str, "Json"]


def is_json_object(obj: Json) -> TypeGuard[dict[str, Json]]:
    """Checks if an object is a JSON object (YAML associative array)"""
    return isinstance(obj, dict)


def to_json_object(obj: Json, location: str) -> dict[str, Json]:
    """Checks if an object is a JSON object (YAML associative array)

    Args:
        obj: the object to check
        location: location of the object to use in exception message

    Returns:
        the same object

    Raises:
        TypeError: if it's not a JSON object
    """
    if is_json_object(obj):
        return obj
    raise TypeError(
        f"Expected an object at '{location}' but found {obj.__class__.__name__}"
    )


def is_json_array(obj: Json) -> TypeGuard[list[Json]]:
    """Checks if an object is a JSON array"""
    return isinstance(obj, list)


def to_json_array(obj: Json, location: str) -> list[Json]:
    """Checks if an object is a JSON array

    Args:
        obj: the object to check
        location: location of the object to use in exception message

    Returns:
        the same object

    Raises:
        TypeError: if it's not a JSON array
    """
    if is_json_array(obj):
        return obj
    raise TypeError(
        f"Expected an array at '{location}' but found {obj.__class__.__name__}"
    )


def to_json_array_of_strings(obj: Json, location: str) -> list[str]:
    """Checks if an object is a JSON array or strings

    Args:
        obj: the object to check
        location: location of the object to use in exception message

    Returns:
        the same object

    Raises:
        TypeError: if it's not a JSON array of strings
    """
    array = to_json_array(obj, location)
    for i, element in enumerate(array):
        if not isinstance(element, str):
            raise TypeError(
                f"Expected a string at '{location}[{i}]'"
                f" but found {element.__class__.__name__}"
            )

    return array  # type: ignore


def to_string(obj: Json, location: str) -> str:
    """Checks if an object is a JSON string

    Args:
        obj: the object to check
        location: location of the object to use in exception message

    Returns:
        the same object

    Raises:
        TypeError: if it's not a JSON string
    """
    if isinstance(obj, str):
        return obj
    raise TypeError(
        f"Expected a string at '{location}' but found {obj.__class__.__name__}"
    )
