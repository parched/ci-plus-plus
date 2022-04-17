from textwrap import dedent

from ruamel.yaml.scalarstring import LiteralScalarString


def multiline(string: str) -> str:
    """Dedents and converts to a multiline string"""
    return LiteralScalarString(dedent(string))
