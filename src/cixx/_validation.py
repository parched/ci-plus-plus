from typing import TypeGuard


def is_json_object(obj: object) -> TypeGuard[dict[str, object]]:
    """Checks if an object is a JSON object (YAML associative array)"""
    return isinstance(obj, dict)


def to_json_object(obj: object, location: str) -> dict[str, object]:
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


def is_json_array(obj: object) -> TypeGuard[list[object]]:
    """Checks if an object is a JSON array"""
    return isinstance(obj, list)


def to_json_array(obj: object, location: str) -> list[object]:
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


def to_json_array_of_strings(obj: object, location: str) -> list[str]:
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


def to_string(obj: object, location: str) -> str:
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
