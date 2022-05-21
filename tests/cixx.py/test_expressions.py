import pytest
from pytest import param

from cixx._expressions import replace_identiers_in_template_str

params = [
    param("", [], "", id="empty with no replacements"),
    param("some.thing", [], "some.thing", id="identifier with no replacements"),
    param(
        "some.thing",
        [("some.thing", "another.thing")],
        "some.thing",
        id="identifier is outside of expression",
    ),
    param(
        "${{some.thing}}",
        [("some.thing", "another.thing")],
        "${{another.thing}}",
        id="identifier is whole expression",
    ),
    param(
        "${{ some.thing }}",
        [("some.thing", "another.thing")],
        "${{ another.thing }}",
        id="identifier+whitespace is whole expression",
    ),
    param(
        "${{'some.thing'}}",
        [("some.thing", "another.thing")],
        "${{'some.thing'}}",
        id="identifier is in string",
    ),
    param(
        "${{handsome.thing}}",
        [("some.thing", "another.thing")],
        "${{handsome.thing}}",
        id="identifier is subset of another",
    ),
    param(
        "${{hand-some.thing}}",
        [("some.thing", "another.thing")],
        "${{hand-some.thing}}",
        id="identifier is subset of another",
    ),
]


@pytest.mark.parametrize("template_str, replacements, expected_result", params)
def test_replace_identifiers_in_templace_str_returns_correct_result(
    template_str: str, replacements: list[tuple[str, str]], expected_result: str
):
    result = replace_identiers_in_template_str(template_str, replacements)

    assert result == expected_result
