"""A stored Conversation as plain data, for the sidebar and the JSON export. No FastAPI in here.

The agent's state holds messages, not the `citations` events. A search result reaches the model (and the state) as
`<document>` wrappers (app/tools/delimit.py), which carry title, section, url, licence, score and text but not the
chunk id, so Citations are parsed back out of those and have no `id` (decision 69). The system prompt is passed to the
model on every call and is not part of the state."""
import re

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.streaming import text_of
from app.tools.delimit import TAGS

DOCUMENT = re.compile(
    r'<document source="(?P<source>[^"]*)">\n\[[^\n]*\] url: (?P<url>\S+) \| license: (?P<license>.*?) \| score: (?P<score>[\d.]+)\n(?P<content>.*?)\n</document>',
    re.DOTALL,
)
ESCAPED = re.compile(r"&lt;(\s*/?\s*(?:" + "|".join(TAGS) + r")\b)", re.IGNORECASE)


def citations_of(content: str) -> list[dict]:
    """The Citations in a search result, in order. A result with no wrappers (not found, an error) has none."""
    found = []
    for match in DOCUMENT.finditer(content):
        title, _, section = match["source"].replace("&quot;", '"').partition(" > ")
        found.append(
            {
                "title": title,
                "section": section,
                "url": match["url"],
                "score": float(match["score"]),
                "license": match["license"],
                "content": ESCAPED.sub(r"<\1", match["content"]),
            }
        )
    return found


def conversation_messages(messages: list) -> list[dict]:
    """User and assistant messages in order. A tool call carries its result and, for a search, its Citations."""
    out: list[dict] = []
    calls: dict[str, dict] = {}
    for message in messages:
        if isinstance(message, HumanMessage):
            out.append({"role": "user", "text": text_of(message.content)})
        elif isinstance(message, AIMessage):
            entry = {"role": "assistant", "text": text_of(message.content), "tool_calls": []}
            for call in message.tool_calls:
                tool_call = {"id": call["id"], "name": call["name"], "args": call["args"], "result": None, "citations": []}
                entry["tool_calls"].append(tool_call)
                calls[call["id"]] = tool_call
            out.append(entry)
        elif isinstance(message, ToolMessage) and message.tool_call_id in calls:
            result = text_of(message.content)
            calls[message.tool_call_id]["result"] = result
            calls[message.tool_call_id]["citations"] = citations_of(result)
    return out
