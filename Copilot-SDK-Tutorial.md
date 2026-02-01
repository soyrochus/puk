# GitHub Copilot SDK Tutorial

> A practical guide to building autonomous agents with the GitHub Copilot SDK

---

## Table of Contents

1. [What is the Copilot SDK?](#1-what-is-the-copilot-sdk)
2. [SDK vs Copilot in VS Code](#2-sdk-vs-copilot-in-vs-code)
3. [Use Cases](#3-use-cases)
4. [Getting Started](#4-getting-started)
5. [Core Concepts](#5-core-concepts)
6. [Working with Tools](#6-working-with-tools)
7. [Connecting to MCP Servers](#7-connecting-to-mcp-servers)
8. [Bring Your Own Key (BYOK)](#8-bring-your-own-key-byok)
9. [User Interaction Patterns](#9-user-interaction-patterns)
10. [Putting It Together](#10-putting-it-together)

---

## 1. What is the Copilot SDK?

The GitHub Copilot SDK provides programmatic access to the same agentic runtime that powers Copilot CLI. Instead of interacting with Copilot through a terminal or IDE, you embed it directly into your application.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Application                            │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   Copilot SDK                           │   │
│   │                                                         │   │
│   │  • Session management                                   │   │
│   │  • Tool orchestration                                   │   │
│   │  • Streaming responses                                  │   │
│   │  • Context management                                   │   │
│   └───────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   Copilot CLI                           │   │
│   │              (JSON-RPC server mode)                     │   │
│   └───────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  LLM Backend  │
                    │  (GPT, Claude)│
                    └───────────────┘
```

**Key insight:** The SDK doesn't contain the AI. It's a client library that communicates with the Copilot CLI, which in turn connects to the LLM backend. The SDK handles the orchestration—sessions, tools, streaming—so you don't have to.

---

## 2. SDK vs Copilot in VS Code

| Aspect | Copilot in VS Code | Copilot SDK |
|--------|-------------------|-------------|
| **Interface** | IDE integration, chat panel | Programmatic API |
| **User** | Developer writing code | Application code |
| **Control** | Manual prompts | Automated workflows |
| **Tools** | Built-in (file editing, terminal) | Custom + built-in |
| **Use case** | Interactive assistance | Autonomous agents |
| **Output** | Code suggestions, chat responses | Structured data, actions |

**Copilot in VS Code** is designed for human interaction. You ask questions, it responds. You review suggestions, you accept or reject.

**Copilot SDK** is designed for machine interaction. Your code sends prompts, defines tools, handles responses, and orchestrates multi-step workflows—without human intervention.

### When to use what

**Use Copilot in VS Code when:**
- You're writing code and want assistance
- You need to explore a problem interactively
- You want code completion and suggestions

**Use Copilot SDK when:**
- You're building an application that needs AI capabilities
- You want autonomous, multi-step workflows
- You need custom tools the AI can invoke
- You're creating a product that embeds AI

---

## 3. Use Cases

### 3.1 Autonomous Agents

Build agents that perform complex tasks without human intervention:

- **Code analysis agents**: Analyze codebases, generate documentation
- **DevOps agents**: Monitor systems, respond to incidents
- **Data processing agents**: Transform, validate, report on data
- **Testing agents**: Generate tests, run them, fix failures

### 3.2 Custom Development Tools

Extend your development workflow:

- **PR reviewers**: Automated code review with custom rules
- **Migration assistants**: Help migrate between frameworks/versions
- **Refactoring tools**: Large-scale codebase transformations
- **Documentation generators**: Keep docs in sync with code

### 3.3 Internal Applications

Build internal tools for your team:

- **Onboarding assistants**: Help new developers understand codebases
- **Knowledge bases**: Query internal documentation with AI
- **Workflow automation**: Connect AI to internal APIs and services

### 3.4 Products

Embed AI capabilities in products:

- **AI-powered features**: Add intelligent features to existing products
- **Chatbots with tools**: Bots that can take actions, not just respond
- **Automation platforms**: Let users define AI-powered workflows

---

## 4. Getting Started

### 4.1 Prerequisites

1. **GitHub Copilot subscription** (or BYOK with supported providers)

2. **Copilot CLI installed:**
   ```bash
   npm install -g @github/copilot
   ```

3. **Python 3.11+** (for Python SDK)

### 4.2 Installation

```bash
pip install github-copilot-sdk
```

### 4.3 Verify Setup

```python
import asyncio
from copilot import CopilotClient

async def main():
    client = CopilotClient()
    await client.start()
    
    # Check available models
    models = await client.list_models()
    print("Available models:", models)
    
    await client.stop()

asyncio.run(main())
```

If this prints a list of models, you're ready to go.

---

## 5. Core Concepts

### 5.1 Client

The `CopilotClient` manages the connection to the Copilot CLI:

```python
from copilot import CopilotClient

# Create client
client = CopilotClient()

# Start the connection (launches Copilot CLI in server mode)
await client.start()

# ... use the client ...

# Clean up
await client.stop()
```

**Best practice:** Use async context manager:

```python
async with CopilotClient() as client:
    # Client is started
    session = await client.create_session({"model": "gpt-5"})
    # ... use session ...
# Client is automatically stopped
```

### 5.2 Session

A session represents a conversation with the AI. It maintains context across multiple messages:

```python
session = await client.create_session({
    "model": "gpt-5",
    "streaming": True,
})

# Send a message
await session.send({"prompt": "What is Python?"})

# Send another message (context is maintained)
await session.send({"prompt": "How does it compare to Java?"})
```

**Session configuration options:**

```python
session = await client.create_session({
    # Required: which model to use
    "model": "gpt-5",
    
    # Enable streaming responses
    "streaming": True,
    
    # Custom tools the AI can invoke
    "tools": [my_tool_1, my_tool_2],
    
    # System prompt customization
    "systemMessage": {
        "content": "You are a helpful assistant.",
    },
    
    # Infinite sessions (context management)
    "infiniteSessions": {
        "enabled": True,
        "backgroundCompactionThreshold": 0.80,
    },
    
    # MCP servers for external tools
    "mcpServers": {
        "github": {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
        },
    },
})
```

### 5.3 Messages

Send messages and receive responses:

```python
# Simple send (fire and forget with streaming)
await session.send({"prompt": "Explain recursion"})

# Send and wait for complete response
response = await session.send_and_wait({"prompt": "Explain recursion"})
print(response)
```

### 5.4 Events

Handle streaming events to see responses as they arrive:

```python
from copilot.generated.session_events import SessionEventType

def handle_event(event):
    match event.type:
        case SessionEventType.ASSISTANT_MESSAGE_DELTA:
            # Token-by-token response
            print(event.delta, end="", flush=True)
        
        case SessionEventType.ASSISTANT_MESSAGE_COMPLETE:
            # Full response complete
            print("\n--- Complete ---")
        
        case SessionEventType.TOOL_INVOCATION_START:
            # AI is calling a tool
            print(f"Calling tool: {event.tool_name}")
        
        case SessionEventType.TOOL_INVOCATION_END:
            # Tool finished
            print(f"Tool result: {event.result}")
        
        case SessionEventType.ERROR:
            # Something went wrong
            print(f"Error: {event.error}")

session.on(handle_event)
```

---

## 6. Working with Tools

Tools are the key to building useful agents. They allow the AI to take actions, not just generate text.

### 6.1 What is a Tool?

A tool is a function that:
1. Has a **name** and **description** (so the AI knows when to use it)
2. Has **parameters** with a schema (so the AI knows what arguments to pass)
3. Has a **handler** that executes when the AI invokes it

```
┌─────────────────────────────────────────────────────────────────┐
│                        Tool Lifecycle                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. You define the tool                                         │
│     ┌─────────────────────────────────────────────────────┐     │
│     │ name: "get_weather"                                 │     │
│     │ description: "Get current weather for a city"       │     │
│     │ parameters: { city: string }                        │     │
│     │ handler: async (params) => fetch_weather(params)    │     │
│     └─────────────────────────────────────────────────────┘     │
│                           │                                     │
│                           ▼                                     │
│  2. You register it with the session                            │
│     session = await client.create_session({ tools: [tool] })    │
│                           │                                     │
│                           ▼                                     │
│  3. AI decides to use it based on the conversation              │
│     User: "What's the weather in Paris?"                        │
│     AI thinks: "I should call get_weather with city='Paris'"    │
│                           │                                     │
│                           ▼                                     │
│  4. SDK invokes your handler automatically                      │
│     handler({ city: "Paris" }) → { temp: "18°C", ... }          │
│                           │                                     │
│                           ▼                                     │
│  5. Result is sent back to the AI                               │
│     AI: "The weather in Paris is 18°C and sunny."               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Defining a Tool

Use the `@define_tool` decorator with Pydantic for type-safe parameters:

```python
from copilot.tools import define_tool
from pydantic import BaseModel, Field

# Define parameters with Pydantic
class GetWeatherParams(BaseModel):
    city: str = Field(description="The city name")
    units: str = Field(default="celsius", description="Temperature units")

# Define the tool
@define_tool(description="Get the current weather for a city")
async def get_weather(params: GetWeatherParams) -> dict:
    # Your implementation here
    # In reality, you'd call a weather API
    return {
        "city": params.city,
        "temperature": "18°C",
        "condition": "sunny",
    }
```

**Key points:**
- The **description** helps the AI understand when to use the tool
- **Field descriptions** help the AI understand what values to pass
- The **return value** is sent back to the AI as context

### 6.3 Tool Parameters

Parameters are defined using Pydantic models with JSON Schema semantics:

```python
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class CreateTaskParams(BaseModel):
    # Required string
    title: str = Field(description="Task title")
    
    # Optional string with default
    description: str = Field(default="", description="Task description")
    
    # Enum for constrained values
    priority: Priority = Field(default=Priority.MEDIUM, description="Task priority")
    
    # List of strings
    tags: list[str] = Field(default_factory=list, description="Tags for the task")
    
    # Nested object
    assignee: dict | None = Field(default=None, description="Person to assign")
```

The SDK converts this to JSON Schema automatically:

```json
{
  "type": "object",
  "properties": {
    "title": { "type": "string", "description": "Task title" },
    "description": { "type": "string", "description": "Task description" },
    "priority": { "enum": ["low", "medium", "high"], "description": "Task priority" },
    "tags": { "type": "array", "items": { "type": "string" }, "description": "Tags for the task" },
    "assignee": { "type": "object", "description": "Person to assign" }
  },
  "required": ["title"]
}
```

### 6.4 Tool Return Values

Tools can return various types:

```python
# Return a dict (most common)
@define_tool(description="Get user info")
async def get_user(params: GetUserParams) -> dict:
    return {"name": "Alice", "email": "alice@example.com"}

# Return a string
@define_tool(description="Read a file")
async def read_file(params: ReadFileParams) -> str:
    with open(params.path) as f:
        return f.read()

# Return a list
@define_tool(description="List files")
async def list_files(params: ListFilesParams) -> list:
    return ["file1.py", "file2.py", "file3.py"]

# Return structured result with metadata
from copilot.tools import ToolResultObject

@define_tool(description="Search code")
async def search_code(params: SearchParams) -> ToolResultObject:
    results = do_search(params.query)
    return ToolResultObject(
        content=results,
        metadata={"total": len(results), "truncated": False},
    )
```

### 6.5 Error Handling in Tools

Tools should handle errors gracefully:

```python
@define_tool(description="Fetch data from API")
async def fetch_data(params: FetchParams) -> dict:
    try:
        response = await http_client.get(params.url)
        return {"status": "success", "data": response.json()}
    except TimeoutError:
        return {"status": "error", "message": "Request timed out"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

The AI receives the error information and can decide how to proceed (retry, ask user, try alternative approach).

### 6.6 Tool Invocation Context

Sometimes you need additional context in your tool handler:

```python
from copilot.tools import define_tool, ToolInvocation

@define_tool(description="Log an action")
async def log_action(params: LogParams, invocation: ToolInvocation) -> dict:
    # Access invocation metadata
    print(f"Tool ID: {invocation.id}")
    print(f"Session ID: {invocation.session_id}")
    
    # Your implementation
    return {"logged": True}
```

### 6.7 Registering Multiple Tools

Pass all tools when creating the session:

```python
session = await client.create_session({
    "model": "gpt-5",
    "tools": [
        get_weather,
        create_task,
        read_file,
        write_file,
        search_code,
        run_command,
    ],
})
```

The AI will choose which tools to use based on the conversation and task.

---

## 7. Connecting to MCP Servers

### 7.1 What is MCP?

The **Model Context Protocol (MCP)** is an open standard for connecting AI models to external tools and data sources. Instead of building every tool yourself, you can connect to MCP servers that provide pre-built capabilities.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Application                            │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   Copilot SDK                           │   │
│   │                                                         │   │
│   │  Custom Tools          MCP Servers                      │   │
│   │  ┌─────────┐          ┌─────────────────────────┐       │   │
│   │  │ my_tool │          │ github    (repos, PRs)  │       │   │
│   │  └─────────┘          │ postgres  (queries)     │       │   │
│   │  ┌─────────┐          │ slack     (messages)    │       │   │
│   │  │ my_tool │          │ sentry    (errors)      │       │   │
│   │  └─────────┘          │ ...                     │       │   │
│   │                       └─────────────────────────┘       │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- **Pre-built integrations**: GitHub, Slack, databases, cloud providers
- **Standard protocol**: Same configuration pattern for all servers
- **Community ecosystem**: Growing library of available servers

### 7.2 Configuring MCP Servers

Add MCP servers when creating a session:

```python
session = await client.create_session({
    "model": "gpt-5",
    "mcpServers": {
        # HTTP-based MCP server
        "github": {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
        },
        
        # Server-Sent Events (SSE) based server
        "cloudflare": {
            "type": "sse",
            "url": "https://docs.mcp.cloudflare.com/sse",
            "tools": ["*"],  # Enable all tools
        },
        
        # Local process-based server
        "postgres": {
            "type": "local",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres"],
            "env": {
                "DATABASE_URL": "postgresql://localhost/mydb",
            },
            "tools": ["query", "list_tables"],  # Enable specific tools
        },
    },
})
```

### 7.3 MCP Server Types

| Type | Description | Use Case |
|------|-------------|----------|
| `http` | HTTP REST endpoint | Hosted services, APIs |
| `sse` | Server-Sent Events | Real-time streaming servers |
| `local` | Local process (stdio) | CLI tools, local services |

### 7.4 Local MCP Server Configuration

For local servers, you spawn a process that communicates via stdin/stdout:

```python
"mcpServers": {
    "sentry": {
        "type": "local",
        "command": "npx",
        "args": ["@sentry/mcp-server@latest", "--host=https://sentry.io"],
        "env": {
            "SENTRY_ACCESS_TOKEN": os.environ["SENTRY_TOKEN"],
        },
        "tools": ["get_issue_details", "get_issue_summary"],
    },
}
```

**Configuration options:**

| Option | Type | Description |
|--------|------|-------------|
| `command` | string | Executable to run |
| `args` | list[string] | Command-line arguments |
| `env` | dict | Environment variables |
| `tools` | list[string] | Which tools to enable (`["*"]` for all) |
| `cwd` | string | Working directory |

### 7.5 Available MCP Servers

Common MCP servers you can use:

| Server | Package | Capabilities |
|--------|---------|--------------|
| **GitHub** | Built-in | Repos, issues, PRs, code search |
| **PostgreSQL** | `@modelcontextprotocol/server-postgres` | SQL queries, schema inspection |
| **Slack** | `@anthropic/mcp-server-slack` | Send messages, read channels |
| **Sentry** | `@sentry/mcp-server` | Error tracking, issue details |
| **Cloudflare** | Hosted | Workers, KV, D1, R2 |
| **Azure** | `@azure/mcp` | Azure services integration |
| **Filesystem** | `@modelcontextprotocol/server-filesystem` | File operations (sandboxed) |
| **Memory** | `@modelcontextprotocol/server-memory` | Persistent key-value store |

### 7.6 Combining Custom Tools with MCP

You can use both custom tools and MCP servers:

```python
session = await client.create_session({
    "model": "gpt-5",
    "tools": [my_custom_tool, another_tool],  # Your tools
    "mcpServers": {
        "github": {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
        },
    },
})
```

The AI can seamlessly use both your custom tools and MCP-provided tools in the same conversation.

### 7.7 MCP Tool Namespacing

MCP tools are namespaced by server name to avoid collisions:

```
github/create_issue       # From GitHub MCP
postgres/query            # From PostgreSQL MCP
my_custom_tool            # Your custom tool (no namespace)
```

When the AI invokes an MCP tool, the SDK routes it to the correct server automatically.

---

## 8. Bring Your Own Key (BYOK)

### 8.1 Why BYOK?

By default, the Copilot SDK uses your GitHub Copilot subscription. BYOK allows you to:

- **Avoid quota limits**: Use your own API quota instead of shared subscription
- **Choose providers**: Use OpenAI, Azure, Anthropic directly
- **Control costs**: Pay per token, track usage separately
- **Access specific models**: Use models not available through Copilot

### 8.2 Supported Providers

| Provider | Models | Configuration |
|----------|--------|---------------|
| **OpenAI** | GPT-4, GPT-4 Turbo, GPT-5 | API key |
| **Azure OpenAI** | GPT-4, GPT-4 Turbo | Endpoint + API key |
| **Anthropic** | Claude Sonnet, Claude Opus | API key |

### 8.3 Configuring BYOK

#### OpenAI

```python
client = CopilotClient({
    "provider": "openai",
    "apiKey": os.environ["OPENAI_API_KEY"],
})

await client.start()

session = await client.create_session({
    "model": "gpt-4-turbo",  # Or "gpt-5", "gpt-4", etc.
})
```

#### Azure OpenAI

```python
client = CopilotClient({
    "provider": "azure",
    "apiKey": os.environ["AZURE_OPENAI_API_KEY"],
    "endpoint": "https://your-resource.openai.azure.com/",
    "apiVersion": "2024-02-15-preview",
})

await client.start()

session = await client.create_session({
    "model": "gpt-4",  # Your deployment name
})
```

#### Anthropic

```python
client = CopilotClient({
    "provider": "anthropic",
    "apiKey": os.environ["ANTHROPIC_API_KEY"],
})

await client.start()

session = await client.create_session({
    "model": "claude-sonnet-4.5",
})
```

### 8.4 Environment Variables

For security, use environment variables instead of hardcoding keys:

```bash
# .env file (don't commit this!)
OPENAI_API_KEY=sk-...
AZURE_OPENAI_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
```

```python
from dotenv import load_dotenv
import os

load_dotenv()

client = CopilotClient({
    "provider": "openai",
    "apiKey": os.environ["OPENAI_API_KEY"],
})
```

### 8.5 Fallback Configuration

Configure fallback providers for resilience:

```python
client = CopilotClient({
    "provider": "openai",
    "apiKey": os.environ["OPENAI_API_KEY"],
    "fallback": {
        "provider": "anthropic",
        "apiKey": os.environ["ANTHROPIC_API_KEY"],
    },
})
```

If the primary provider fails, the SDK automatically retries with the fallback.

### 8.6 Model Selection with BYOK

When using BYOK, specify models supported by your provider:

```python
# OpenAI
session = await client.create_session({"model": "gpt-5"})
session = await client.create_session({"model": "gpt-4-turbo"})

# Anthropic
session = await client.create_session({"model": "claude-sonnet-4.5"})
session = await client.create_session({"model": "claude-opus-4.5"})

# Azure (use your deployment names)
session = await client.create_session({"model": "my-gpt4-deployment"})
```

### 8.7 Cost Considerations

BYOK means you pay per token. Estimate costs:

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| GPT-4 Turbo | ~$10 | ~$30 |
| GPT-5 | ~$15 | ~$60 |
| Claude Sonnet | ~$3 | ~$15 |
| Claude Opus | ~$15 | ~$75 |

*Prices are approximate and change frequently. Check provider pricing pages.*

**Tips to control costs:**
- Use smaller context windows when possible
- Enable `infiniteSessions` for automatic compaction
- Choose appropriate models (don't use Opus for simple tasks)
- Set `max_tokens` limits in session config

---

## 9. User Interaction Patterns

Agents often need to interact with users—for confirmation, input, or progress updates. This section covers patterns for building interactive agents.

### 9.1 The Challenge

The Copilot SDK is designed for autonomous operation, but real-world agents need user interaction:

- **Confirmation**: "I'm about to delete 50 files. Continue?"
- **Input**: "Which branch should I deploy?"
- **Progress**: "Analyzing file 3 of 100..."
- **Clarification**: "Did you mean X or Y?"

### 9.2 Architecture for User I/O

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                           │
│                  (CLI, Web, Desktop, Slack)                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     I/O Abstraction Layer                       │
│                                                                 │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│   │   display()   │  │   confirm()   │  │   prompt()    │      │
│   └───────────────┘  └───────────────┘  └───────────────┘      │
│                                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Core                               │
│                    (Copilot SDK Session)                        │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight**: Expose user I/O as tools. The AI can then request user interaction when needed.

### 9.3 Basic I/O Tools

Define tools that the AI can invoke to interact with the user:

```python
from copilot.tools import define_tool
from pydantic import BaseModel, Field


class DisplayMessageParams(BaseModel):
    message: str = Field(description="Message to display to the user")
    level: str = Field(
        default="info",
        description="Message level: info, warning, error, success"
    )

@define_tool(description="Display a message to the user")
async def display_message(params: DisplayMessageParams) -> dict:
    """Show a message to the user."""
    prefix = {
        "info": "ℹ️ ",
        "warning": "⚠️ ",
        "error": "❌ ",
        "success": "✅ ",
    }.get(params.level, "")
    
    print(f"{prefix}{params.message}")
    return {"displayed": True}


class ConfirmActionParams(BaseModel):
    question: str = Field(description="Yes/no question to ask the user")
    default: bool = Field(default=False, description="Default if user just presses enter")

@define_tool(description="Ask the user for yes/no confirmation")
async def confirm_action(params: ConfirmActionParams) -> dict:
    """Ask the user to confirm an action."""
    default_hint = "[Y/n]" if params.default else "[y/N]"
    response = input(f"{params.question} {default_hint}: ").strip().lower()
    
    if response == "":
        confirmed = params.default
    else:
        confirmed = response in ("y", "yes", "true", "1")
    
    return {"confirmed": confirmed}


class PromptUserParams(BaseModel):
    question: str = Field(description="Question to ask the user")
    default: str = Field(default="", description="Default value if user provides none")

@define_tool(description="Prompt the user for text input")
async def prompt_user(params: PromptUserParams) -> dict:
    """Ask the user for text input."""
    if params.default:
        response = input(f"{params.question} [{params.default}]: ").strip()
        response = response or params.default
    else:
        response = input(f"{params.question}: ").strip()
    
    return {"response": response}


class SelectOptionParams(BaseModel):
    question: str = Field(description="Question to ask")
    options: list[str] = Field(description="Available options")
    default: int = Field(default=0, description="Default option index")

@define_tool(description="Ask the user to select from a list of options")
async def select_option(params: SelectOptionParams) -> dict:
    """Present options and let the user choose."""
    print(f"\n{params.question}")
    for i, option in enumerate(params.options):
        marker = "→" if i == params.default else " "
        print(f"  {marker} {i + 1}. {option}")
    
    while True:
        response = input(f"Enter number [1-{len(params.options)}]: ").strip()
        if response == "":
            return {"selected": params.options[params.default], "index": params.default}
        try:
            index = int(response) - 1
            if 0 <= index < len(params.options):
                return {"selected": params.options[index], "index": index}
        except ValueError:
            pass
        print("Invalid selection. Try again.")
```

### 9.4 Progress Reporting

For long-running operations, provide progress feedback:

```python
from rich.progress import Progress, SpinnerColumn, TextColumn
import asyncio

# Global progress context (or pass via tool invocation context)
_progress_context = {}

class StartProgressParams(BaseModel):
    task_id: str = Field(description="Unique identifier for this progress tracker")
    description: str = Field(description="What operation is in progress")
    total: int = Field(default=0, description="Total steps (0 for indeterminate)")

@define_tool(description="Start a progress indicator for a long-running task")
async def start_progress(params: StartProgressParams) -> dict:
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    )
    progress.start()
    task = progress.add_task(params.description, total=params.total or None)
    
    _progress_context[params.task_id] = {"progress": progress, "task": task}
    return {"started": True, "task_id": params.task_id}


class UpdateProgressParams(BaseModel):
    task_id: str = Field(description="Progress tracker ID")
    advance: int = Field(default=1, description="Steps to advance")
    description: str = Field(default="", description="Update description")

@define_tool(description="Update progress on a long-running task")
async def update_progress(params: UpdateProgressParams) -> dict:
    ctx = _progress_context.get(params.task_id)
    if not ctx:
        return {"error": "Unknown task_id"}
    
    if params.description:
        ctx["progress"].update(ctx["task"], description=params.description)
    ctx["progress"].advance(ctx["task"], params.advance)
    return {"updated": True}


class EndProgressParams(BaseModel):
    task_id: str = Field(description="Progress tracker ID")
    message: str = Field(default="Done", description="Completion message")

@define_tool(description="Complete and remove a progress indicator")
async def end_progress(params: EndProgressParams) -> dict:
    ctx = _progress_context.pop(params.task_id, None)
    if not ctx:
        return {"error": "Unknown task_id"}
    
    ctx["progress"].stop()
    print(f"✅ {params.message}")
    return {"ended": True}
```

### 9.5 Rich Terminal Output

Use the `rich` library for better terminal UX:

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

console = Console()

class DisplayCodeParams(BaseModel):
    code: str = Field(description="Code to display")
    language: str = Field(default="python", description="Programming language")
    title: str = Field(default="", description="Optional title")

@define_tool(description="Display formatted code to the user")
async def display_code(params: DisplayCodeParams) -> dict:
    syntax = Syntax(params.code, params.language, theme="monokai", line_numbers=True)
    if params.title:
        console.print(Panel(syntax, title=params.title))
    else:
        console.print(syntax)
    return {"displayed": True}


class DisplayTableParams(BaseModel):
    title: str = Field(description="Table title")
    columns: list[str] = Field(description="Column headers")
    rows: list[list[str]] = Field(description="Table rows")

@define_tool(description="Display a formatted table to the user")
async def display_table(params: DisplayTableParams) -> dict:
    table = Table(title=params.title)
    for col in params.columns:
        table.add_column(col)
    for row in params.rows:
        table.add_row(*row)
    console.print(table)
    return {"displayed": True}
```

### 9.6 Abstracting the I/O Layer

For portability across interfaces (CLI, web, etc.), abstract the I/O:

```python
from abc import ABC, abstractmethod
from typing import Protocol


class UserIO(Protocol):
    """Protocol for user interaction."""
    
    async def display(self, message: str, level: str = "info") -> None:
        """Display a message to the user."""
        ...
    
    async def confirm(self, question: str, default: bool = False) -> bool:
        """Ask for yes/no confirmation."""
        ...
    
    async def prompt(self, question: str, default: str = "") -> str:
        """Ask for text input."""
        ...
    
    async def select(self, question: str, options: list[str], default: int = 0) -> str:
        """Ask user to select from options."""
        ...


class TerminalIO:
    """Terminal-based implementation."""
    
    async def display(self, message: str, level: str = "info") -> None:
        print(message)
    
    async def confirm(self, question: str, default: bool = False) -> bool:
        response = input(f"{question} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
        return response in ("y", "yes") if response else default
    
    async def prompt(self, question: str, default: str = "") -> str:
        response = input(f"{question}: ").strip()
        return response or default
    
    async def select(self, question: str, options: list[str], default: int = 0) -> str:
        print(question)
        for i, opt in enumerate(options):
            print(f"  {i + 1}. {opt}")
        choice = int(input("Select: ") or str(default + 1)) - 1
        return options[choice]


class WebIO:
    """Web-based implementation (example skeleton)."""
    
    def __init__(self, websocket):
        self.ws = websocket
    
    async def display(self, message: str, level: str = "info") -> None:
        await self.ws.send_json({"type": "display", "message": message, "level": level})
    
    async def confirm(self, question: str, default: bool = False) -> bool:
        await self.ws.send_json({"type": "confirm", "question": question})
        response = await self.ws.receive_json()
        return response.get("confirmed", default)
    
    # ... etc


def create_io_tools(io: UserIO) -> list:
    """Create tools bound to a specific I/O implementation."""
    
    @define_tool(description="Display a message to the user")
    async def display_message(params: DisplayMessageParams) -> dict:
        await io.display(params.message, params.level)
        return {"displayed": True}
    
    @define_tool(description="Ask the user for confirmation")
    async def confirm_action(params: ConfirmActionParams) -> dict:
        confirmed = await io.confirm(params.question, params.default)
        return {"confirmed": confirmed}
    
    @define_tool(description="Prompt the user for input")
    async def prompt_user(params: PromptUserParams) -> dict:
        response = await io.prompt(params.question, params.default)
        return {"response": response}
    
    return [display_message, confirm_action, prompt_user]
```

### 9.7 Instructing the AI to Use I/O Tools

Add guidance in your system prompt:

```python
system_prompt = """You are an assistant that helps users manage their files.

## User Interaction Guidelines

1. **Before destructive operations** (delete, overwrite, modify), always use 
   `confirm_action` to get explicit user approval.

2. **For progress on long tasks** (>5 seconds), use `start_progress`, 
   `update_progress`, and `end_progress` to keep the user informed.

3. **When you need clarification**, use `prompt_user` to ask specific questions.
   Don't guess—ask.

4. **When presenting options**, use `select_option` instead of asking the user 
   to type out their choice.

5. **For important information**, use `display_message` with appropriate levels:
   - "info": General information
   - "warning": Potential issues
   - "error": Problems that occurred
   - "success": Completed actions

## Example Flow

User: "Clean up old log files"

1. Use `list_directory` to find log files
2. Use `display_table` to show what was found
3. Use `confirm_action`: "Delete 47 log files older than 30 days?"
4. If confirmed, use `start_progress` with total=47
5. Delete files, calling `update_progress` periodically
6. Use `end_progress` with success message
"""
```

### 9.8 Handling Timeouts and Interrupts

Users may want to cancel long-running operations:

```python
import asyncio
import signal

class InterruptibleAgent:
    def __init__(self):
        self.cancelled = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        def handler(signum, frame):
            self.cancelled = True
            print("\n⚠️  Interrupt received. Finishing current operation...")
        
        signal.signal(signal.SIGINT, handler)
    
    async def run_with_timeout(self, coro, timeout: float = 300):
        """Run with timeout and interrupt support."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            print("❌ Operation timed out")
            return None
    
    def check_cancelled(self):
        """Call this in long loops to respect user interrupts."""
        if self.cancelled:
            raise KeyboardInterrupt("User cancelled operation")
```

---

## 10. Putting It Together

Here's a complete example of a simple agent that can read files and answer questions about them:

```python
import asyncio
from pathlib import Path
from copilot import CopilotClient
from copilot.tools import define_tool
from copilot.generated.session_events import SessionEventType
from pydantic import BaseModel, Field


# =============================================================================
# Tool Definitions
# =============================================================================

class ReadFileParams(BaseModel):
    path: str = Field(description="Path to the file to read")

@define_tool(description="Read the contents of a file")
async def read_file(params: ReadFileParams) -> dict:
    try:
        path = Path(params.path)
        if not path.exists():
            return {"error": f"File not found: {params.path}"}
        if not path.is_file():
            return {"error": f"Not a file: {params.path}"}
        
        content = path.read_text()
        return {
            "path": params.path,
            "content": content,
            "size": len(content),
            "lines": len(content.splitlines()),
        }
    except Exception as e:
        return {"error": str(e)}


class ListDirectoryParams(BaseModel):
    path: str = Field(default=".", description="Directory to list")
    pattern: str = Field(default="*", description="Glob pattern to filter files")

@define_tool(description="List files in a directory")
async def list_directory(params: ListDirectoryParams) -> dict:
    try:
        path = Path(params.path)
        if not path.exists():
            return {"error": f"Directory not found: {params.path}"}
        if not path.is_dir():
            return {"error": f"Not a directory: {params.path}"}
        
        files = list(path.glob(params.pattern))
        return {
            "path": params.path,
            "pattern": params.pattern,
            "files": [
                {
                    "name": f.name,
                    "is_dir": f.is_dir(),
                    "size": f.stat().st_size if f.is_file() else None,
                }
                for f in sorted(files)[:50]  # Limit to 50 entries
            ],
            "total": len(files),
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Agent Implementation
# =============================================================================

class FileAnalysisAgent:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.client = CopilotClient()
        self.session = None
    
    async def start(self):
        await self.client.start()
        
        self.session = await self.client.create_session({
            "model": "gpt-5",
            "streaming": True,
            "tools": [read_file, list_directory],
            "systemMessage": {
                "content": f"""You are a helpful assistant that analyzes files.
                
The user is working in: {self.project_path}

When asked about files or code:
1. Use list_directory to explore the project structure
2. Use read_file to examine specific files
3. Provide clear, concise answers based on what you find

Always reference specific files and line numbers when discussing code.""",
            },
        })
        
        # Set up event handler for streaming output
        def handle_event(event):
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                print(event.delta, end="", flush=True)
            elif event.type == SessionEventType.ASSISTANT_MESSAGE_COMPLETE:
                print()  # Newline after complete response
            elif event.type == SessionEventType.TOOL_INVOCATION_START:
                print(f"\n[Tool: {event.tool_name}]", flush=True)
        
        self.session.on(handle_event)
    
    async def ask(self, question: str):
        print(f"\n> {question}\n")
        await self.session.send_and_wait({"prompt": question})
    
    async def stop(self):
        if self.session:
            await self.session.close()
        await self.client.stop()


# =============================================================================
# Main
# =============================================================================

async def main():
    agent = FileAnalysisAgent(".")
    
    try:
        await agent.start()
        
        # Interactive loop
        print("File Analysis Agent")
        print("Type 'quit' to exit\n")
        
        while True:
            question = input("> ").strip()
            if question.lower() in ("quit", "exit", "q"):
                break
            if question:
                await agent.ask(question)
    
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

### Running the Example

```bash
python file_agent.py
```

```
File Analysis Agent
Type 'quit' to exit

> What files are in this directory?

[Tool: list_directory]
Based on the directory listing, I can see the following files:
- file_agent.py (this script, 2.3KB)
- README.md (documentation)
- pyproject.toml (Python project configuration)
...

> What does the README say?

[Tool: read_file]
The README contains:
...

> quit
```

---

## Next Steps

Now that you understand the basics:

1. **Read the SDK source** for advanced patterns (`vendor/copilot-sdk/python/`)
2. **Explore MCP servers** for pre-built tool integrations
3. **Build custom agents** for your specific use cases
4. **Check the cookbook** in the SDK repo for more examples

---

*End of Tutorial*
