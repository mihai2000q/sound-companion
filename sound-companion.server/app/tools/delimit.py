"""Delimiters around text the model reads as reference material (prompt-injection defence, see docs/SECURITY.md).
Retrieved chunks go in `<document>`, music tool results in `<tool_result>`. Look-alikes of either tag inside the
text are escaped, so text cannot close its own wrapper."""
import json
import re
from collections.abc import Callable
from functools import wraps

TAGS = ("document", "tool_result")
LOOKALIKE = re.compile(r"<(\s*/?\s*(?:" + "|".join(TAGS) + r")\b)", re.IGNORECASE)


def escape(text: str) -> str:
    """Turn the `<` of any opening or closing wrapper tag (any case, extra spaces) into `&lt;`."""
    return LOOKALIKE.sub(r"&lt;\1", text)


def attr(value: str) -> str:
    return escape(value).replace('"', "&quot;").replace("\n", " ")


def wrap_document(source: str, text: str) -> str:
    return f'<document source="{attr(source)}">\n{escape(text)}\n</document>'


def wrap_tool_result(tool: str, result: dict | str) -> str:
    body = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    return f'<tool_result tool="{attr(tool)}">\n{escape(body)}\n</tool_result>'


def delimited(tool: str, func: Callable[..., dict]) -> Callable[..., str]:
    """Wrap a music tool function so the model gets its result inside `<tool_result>`."""

    @wraps(func)
    def run(*args, **kwargs) -> str:
        return wrap_tool_result(tool, func(*args, **kwargs))

    return run


def unwrap_tool_result(content: str) -> str:
    """The body of a `<tool_result>` wrapper, or the content unchanged."""
    match = re.fullmatch(r'<tool_result tool="[^"]*">\n(.*)\n</tool_result>', content, re.DOTALL)
    return match.group(1) if match else content


def parse_tool_result(content: str | dict) -> dict:
    """A music tool's result as a dict, from the wrapped string the model sees (or the dict a validation error returns)."""
    return content if isinstance(content, dict) else json.loads(unwrap_tool_result(content))
