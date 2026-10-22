"""Chat with the agent from the command line, with memory per thread. Run from the server folder:

    uv run python -m scripts.chat                 # a new thread
    uv run python -m scripts.chat --thread ID     # continue a thread
    uv run python -m scripts.chat --history ID    # print a thread's messages and exit

Type an empty line or Ctrl-D to leave. The thread id is printed on start.
"""

import argparse
import asyncio
import uuid

from app.agent.agent import build_agent, make_chat_model
from app.agent.memory import open_checkpointer
from app.rag.retriever import VectorRetriever


def show_tool_calls(messages: list) -> None:
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            print(f"[tool call] {call['name']}({call['args']})")


async def print_history(agent, config: dict) -> None:
    state = await agent.aget_state(config)
    for message in state.values.get("messages", []):
        calls = [call["name"] for call in getattr(message, "tool_calls", None) or []]
        print(f"{message.type:>5}: {str(message.content)[:100]!r}" + (f" tool_calls={calls}" if calls else ""))


async def main(args: argparse.Namespace) -> None:
    thread_id = args.history or args.thread or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with open_checkpointer() as saver:
        agent = build_agent(make_chat_model(), VectorRetriever.from_settings(), saver)
        if args.history:
            return await print_history(agent, config)
        print(f"thread {thread_id}")
        while True:
            try:
                question = input("\nyou> ").strip()
            except EOFError:
                break
            if not question:
                break
            before = len((await agent.aget_state(config)).values.get("messages", []))
            result = await agent.ainvoke({"messages": [{"role": "user", "content": question}]}, config)
            show_tool_calls(result["messages"][before:])
            print("\n" + result["messages"][-1].content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--thread")
    parser.add_argument("--history")
    asyncio.run(main(parser.parse_args()))
