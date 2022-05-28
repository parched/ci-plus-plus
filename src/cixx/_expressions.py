import json
import re
from collections.abc import Collection, Iterator
from typing import Callable, TypeVar, cast


def to_expression(obj: object) -> str:
    """Return the conversion of a object containing template strings to an expression"""
    match obj:
        case str():
            return _template_str_to_expression(obj)
        case float() | int() | bool() | None:
            return json.dumps(obj)
        case dict() | list():
            # There is no array or object literal so need to use fromJSON
            json_template = to_json_template(
                # https://github.com/microsoft/pyright/issues/3552
                obj  # pyright: ignore [reportUnknownArgumentType]
            )
            json_expression = _format_split_template(
                list(_split_template(json_template))
            )
            return f"""fromJSON({json_expression})"""
        case _:
            raise TypeError("Unsupported JSON type")


def to_json_template(obj: object) -> str:
    """Return the JSON conversion of a object containing template strings"""
    match obj:
        case str():
            return _template_str_to_json(obj)
        case dict():
            obj_ = cast(dict[str, object], obj)
            pairs = (f"{json.dumps(k)}:{to_json_template(v)}" for k, v in obj_.items())
            return f"{{{','.join(pairs)}}}"
        case list():
            obj_ = cast(list[object], obj)
            return f"[{','.join(to_json_template(e) for e in obj_)}]"
        case float() | int() | bool() | None:
            return json.dumps(obj)
        case _:
            raise TypeError("Unsupported JSON type")


def get_full_expression_or_none(obj: str) -> str | None:
    """Return the expression if this string is a full expresssion or None"""
    if obj.startswith("${{"):
        if not obj.endswith("}}"):
            raise ValueError(f"Expected '}}' at end in: {obj}")
        return obj[3:-2].strip()
    return None


def _template_str_to_expression(obj: str) -> str:
    """Return the expression conversion of a template string"""
    if (full_expression := get_full_expression_or_none(obj)) is not None:
        return full_expression
    # TODO support unpack assignment
    # if obj.startswith("*${{"):
    #     return f"\t${{{{toJson({obj})}}}}\b" # needs post processing in bash
    return _format_split_template(list(_split_template(obj)))


def _template_str_to_json(obj: str) -> str:
    """Return the JSON conversion of a template string"""
    expression = _template_str_to_expression(obj)
    return f"${{{{toJson({expression})}}}}"


T = TypeVar("T")


def _replace_strings(obj: T, replacer: Callable[[str], object]) -> T:
    """Replace strings in an object

    Args:
        obj: The object to make replacements in
        replacer: A function to generate the replacement

    Returns:
        The obect with strings repalced

    Raises:
        TypeError: If an non JSON compatible type is encountered
    """
    match obj:
        case str():
            return replacer(obj)
        case dict():
            obj_ = cast(dict[str, object], obj)
            new = {k: _replace_strings(v, replacer) for k, v in obj_.items()}
            if all(a is b for a, b in zip(new.values(), obj_.values())):
                return obj_  # type: ignore
            return new  # type: ignore
        case list():
            obj_ = cast(list[object], obj)
            new = [_replace_strings(element, replacer) for element in obj_]
            if all(a is b for a, b in zip(new, obj_)):
                return obj_  # type: ignore
            return new  # type: ignore
        case float() | int() | bool() | None:
            return obj  # type: ignore
        case _:
            raise TypeError("Unsupported JSON type")


def replace_full_expressions(obj: T, replacements: Collection[tuple[str, object]]) -> T:
    """Replace strings that are a full expression in an object

    Args:
        obj: The object to make replacements in
        replacements: A collection of (old, new)

    Returns:
        The object with the full expressions replaced
    """
    return _replace_strings(obj, lambda s: _replace_full_expression(s, replacements))


def _replace_full_expression(
    obj: str, replacements: Collection[tuple[str, object]]
) -> object:
    if (full_expression := get_full_expression_or_none(obj)) is not None:
        for expression, replacement in replacements:
            if expression == full_expression:
                return replacement

    return obj


def replace_identifiers(obj: T, replacements: Collection[tuple[str, str]]) -> T:
    """Replace identifiers in an object containing template strings

    Args:
        obj: The object to make replacements in
        replacements: A collection of (old, new)

    Returns:
        The replaced template or the same str if no replacements
    """
    return _replace_strings(
        obj, lambda s: replace_identiers_in_template_str(s, replacements)
    )


def _split_template(obj: str) -> Iterator[tuple[str, bool]]:
    start = 0
    in_expression = False
    in_string = False
    i = 0
    while i < len(obj):
        if in_expression:
            if in_string:
                if obj[i : i + 2] == "''":
                    i += 2
                else:
                    if obj[i] == "'":
                        in_string = False
                    i += 1
            elif obj[i : i + 2] == "}}":
                yield (obj[start:i], True)
                start = i + 2
                i = start
                in_expression = False
            else:
                if obj[i] == "'":
                    in_string = True
                i += 1
        elif obj[i : i + 3] == "${{":
            yield (obj[start:i], False)
            start = i + 3
            i = start
            in_expression = True
            in_string = False
        else:
            i += 1
    if in_expression:
        raise ValueError(f"Incomplete expression in: {obj}")
    yield obj[start:], False


def _format_split_template(split: list[tuple[str, bool]]) -> str:
    if len(split) == 0:
        return "''"
    if len(split) == 1 and not split[0][1]:
        # There's no expressions
        escaped = split[0][0].replace("'", "''")
        return f"'{escaped}'"

    parts = list[str]()
    args = list[str]()
    i = 0
    for part, is_expression in split:
        if is_expression:
            parts.append(f"{{{i}}}")
            args.append(part)
            i += 1
        else:
            parts.append(part.replace("'", "''").replace("{", "{{").replace("}", "}}"))

    assert args

    return "".join(
        [
            "format('",
            *parts,
            "',",
            ",".join(args),
            ")",
        ]
    )


def replace_identiers_in_template_str(
    template_str: str, replacements: Collection[tuple[str, str]]
) -> str:
    """Replace identifiers in template str

    Args:
        template_str: The str to make replacements in
        replacements: A collection of (old, new)

    Returns:
        The replaced template or the same str if no replacements
    """
    replacement_was_made = False
    parts = list[str]()
    for part, is_expression in _split_template(template_str):
        if is_expression:
            for old, new in replacements:
                part, was_replaced = _replace_identier(part, old, new)
                replacement_was_made = replacement_was_made or was_replaced
            part = f"${{{{{part}}}}}"
        parts.append(part)

    if not replacement_was_made:
        return template_str

    return "".join(parts)


def _replace_identier(expression: str, old: str, new: str) -> tuple[str, bool]:
    pattern = rf"('([^']*|'')*'(?!'))|(?<![\w\-\.]){re.escape(old)}"

    replacement_was_made = False

    def repl(match: re.Match[str]) -> str:
        string = match.group(1)
        if string:
            return string

        nonlocal replacement_was_made
        replacement_was_made = True
        return new

    replaced = re.sub(pattern, repl, expression)
    return replaced, replacement_was_made
