---
name: copilot-sdk
description: Use this skill when writing Python code that interacts with the GitHub Copilot SDK — creating clients, sessions, tools, streaming, hooks, or custom providers. Do NOT use it for non-SDK GitHub API work, CLI scripting, or non-Python SDK languages.
---

# GitHub Copilot SDK — Python

Build agents and integrations on top of GitHub Copilot using the Python SDK.
The SDK communicates with the Copilot CLI over JSON-RPC (stdio or TCP) and
is **async-native** (`asyncio`).

## Source of truth

Prefer local paths under `vendor/copilot-sdk/` over web docs.
If code and web disagree, follow the pinned local copy.

The submodule is pinned at commit `a552ae4` — see
`references/00-setup.md` for the full SHA and tag.

## Entrypoint pointers

Start reading here when you need context:

1. **SDK README (quick-start + full API reference)**
   `vendor/copilot-sdk/python/README.md`
2. **Python cookbook recipes (runnable examples)**
   `vendor/copilot-sdk/cookbook/python/` — especially the `recipe/` sub-directory
   which contains copy-pasteable `.py` files for error handling, multiple
   sessions, file management, PR visualization, and session persistence.
3. **Package exports & public surface**
   `vendor/copilot-sdk/python/copilot/__init__.py` — authoritative list of
   every public class, type, and decorator the SDK exposes.

## Gotchas

- The SDK is in **technical preview**; breaking changes are possible.
- Always use `async`/`await`. The cookbook `recipe/*.py` files use a
  synchronous convenience wrapper — convert them to async before copying
  into production code.
- When using `from __future__ import annotations`, define Pydantic models
  at **module level** (not inside functions).
- For Azure endpoints (`*.openai.azure.com`) use `type: "azure"`, **not**
  `type: "openai"`.
- `base_url` for Azure should be just the host — never append
  `/openai/v1`; the SDK builds the path automatically.
- A `model` parameter is **required** when using a custom provider.

## Core workflow (async)

```python
import asyncio
from copilot import CopilotClient

async def main():
    client = CopilotClient()
    await client.start()

    session = await client.create_session({"model": "gpt-5"})

    done = asyncio.Event()

    def on_event(event):
        if event.type.value == "assistant.message":
            print(event.data.content)
        elif event.type.value == "session.idle":
            done.set()

    session.on(on_event)
    await session.send({"prompt": "What is 2+2?"})
    await done.wait()

    await session.destroy()
    await client.stop()

asyncio.run(main())
```

## Defining custom tools (async, Pydantic)

```python
from pydantic import BaseModel, Field
from copilot import CopilotClient, define_tool

class LookupIssueParams(BaseModel):
    id: str = Field(description="Issue identifier")

@define_tool(description="Fetch issue details from our tracker")
async def lookup_issue(params: LookupIssueParams) -> str:
    issue = await fetch_issue(params.id)
    return issue.summary

async def main():
    client = CopilotClient()
    await client.start()

    session = await client.create_session({
        "model": "gpt-5",
        "tools": [lookup_issue],
    })
    # … use session …
```

## Streaming (async)

```python
session = await client.create_session({
    "model": "gpt-5",
    "streaming": True,
})

done = asyncio.Event()

def on_event(event):
    if event.type.value == "assistant.message_delta":
        print(event.data.delta_content or "", end="", flush=True)
    elif event.type.value == "session.idle":
        done.set()

session.on(on_event)
await session.send({"prompt": "Tell me a short story"})
await done.wait()
```

## Session hooks (async)

```python
async def on_pre_tool_use(input, invocation):
    return {
        "permissionDecision": "allow",
        "modifiedArgs": input.get("toolArgs"),
    }

session = await client.create_session({
    "model": "gpt-5",
    "hooks": {
        "on_pre_tool_use": on_pre_tool_use,
    },
})
```

Available hooks: `on_pre_tool_use`, `on_post_tool_use`,
`on_user_prompt_submitted`, `on_session_start`, `on_session_end`,
`on_error_occurred`.

## Decision table — what to reach for

| Task                              | Class / function       | Reference path                                  |
|-----------------------------------|------------------------|-------------------------------------------------|
| Create a client                   | `CopilotClient`       | `vendor/copilot-sdk/python/copilot/client.py`   |
| Open a conversation               | `CopilotSession`      | `vendor/copilot-sdk/python/copilot/session.py`  |
| Expose a tool to the agent        | `@define_tool` / `Tool`| `vendor/copilot-sdk/python/copilot/tools.py`   |
| Type-check events & configs       | `types` module         | `vendor/copilot-sdk/python/copilot/types.py`    |
| See all public exports            | `__init__.py`          | `vendor/copilot-sdk/python/copilot/__init__.py`  |
| Browse runnable examples          | cookbook recipes        | `vendor/copilot-sdk/cookbook/python/recipe/`     |

## Install

```bash
pip install -e "./vendor/copilot-sdk/python[dev]"
```

Requires Python >=3.9, Copilot CLI on `$PATH`.
