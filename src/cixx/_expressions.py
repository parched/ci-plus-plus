import re
from collections.abc import Collection, Iterator


def template_str_to_json(obj: str) -> str:
    """Return the JSON conversion of a template string"""
    if obj.startswith("${{"):
        if not obj.endswith("}}"):
            raise ValueError(f"Expected '}}' at end in: {obj}")
        expression = obj[3:-2]
    # TODO support unpack assignment
    # if obj.startswith("*${{"):
    #     return f"\t${{{{toJson({obj})}}}}\b" # needs post processing in bash
    else:
        expression = _format_split_template(list(_split_template(obj)))
    return f"${{{{toJson({expression})}}}}"


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
