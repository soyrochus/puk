from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from .errors import MissingInfoError


class UserIO(Protocol):
    async def display(self, message: str, level: str = "info") -> None:
        ...

    async def confirm(self, question: str, default: bool = False) -> bool:
        ...

    async def prompt(self, question: str, default: str = "") -> str:
        ...

    async def select(self, question: str, options: list[str], default: int = 0) -> str:
        ...

    def assistant_delta(self, delta: str) -> None:
        ...

    def assistant_complete(self) -> None:
        ...

    def tool_invocation(self, tool_name: str) -> None:
        ...

    def render_diff(self, diff_text: str) -> None:
        ...

    def update_context(self, context: dict[str, str]) -> None:
        ...


@dataclass
class ConversationBuffer:
    messages: list[dict[str, str]] = field(default_factory=list)

    def append_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def append_delta(self, role: str, delta: str) -> None:
        if self.messages and self.messages[-1]["role"] == role:
            self.messages[-1]["content"] += delta
        else:
            self.append_message(role, delta)

    def render_text(self) -> str:
        lines: list[str] = []
        for msg in self.messages[-200:]:
            role = msg["role"].upper()
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)


class PlainIO:
    def __init__(self) -> None:
        self.buffer = ConversationBuffer()

    async def display(self, message: str, level: str = "info") -> None:
        print(f"[{level}] {message}")

    async def confirm(self, question: str, default: bool = False) -> bool:
        hint = "[Y/n]" if default else "[y/N]"
        response = input(f"{question} {hint}: ").strip().lower()
        if not response:
            return default
        return response in ("y", "yes", "true", "1")

    async def prompt(self, question: str, default: str = "") -> str:
        if default:
            response = input(f"{question} [{default}]: ").strip()
            return response or default
        return input(f"{question}: ").strip()

    async def select(self, question: str, options: list[str], default: int = 0) -> str:
        print(question)
        for index, option in enumerate(options):
            marker = "*" if index == default else " "
            print(f"{marker} {index + 1}. {option}")
        while True:
            response = input(f"Select [1-{len(options)}]: ").strip()
            if not response:
                return options[default]
            try:
                choice = int(response) - 1
            except ValueError:
                print("Invalid selection.")
                continue
            if 0 <= choice < len(options):
                return options[choice]
            print("Invalid selection.")

    def assistant_delta(self, delta: str) -> None:
        print(delta, end="", flush=True)

    def assistant_complete(self) -> None:
        print("")

    def tool_invocation(self, tool_name: str) -> None:
        print(f"[tool] {tool_name}")

    def render_diff(self, diff_text: str) -> None:
        if diff_text:
            print(diff_text)

    def update_context(self, context: dict[str, str]) -> None:
        return None


class NonInteractiveIO(PlainIO):
    async def confirm(self, question: str, default: bool = False) -> bool:
        raise MissingInfoError(f"Confirmation required: {question}")

    async def prompt(self, question: str, default: str = "") -> str:
        raise MissingInfoError(f"Missing required input: {question}")

    async def select(self, question: str, options: list[str], default: int = 0) -> str:
        raise MissingInfoError(f"Missing selection required: {question}")


class TuiIO(PlainIO):
    def __init__(self) -> None:
        super().__init__()
        self.console = Console()
        self.context: dict[str, str] = {}

    def update_context(self, context: dict[str, str]) -> None:
        self.context = context
        self._render()

    def assistant_delta(self, delta: str) -> None:
        self.buffer.append_delta("assistant", delta)
        self._render()

    def assistant_complete(self) -> None:
        self._render()
        print("")

    def tool_invocation(self, tool_name: str) -> None:
        self.buffer.append_message("system", f"tool invoked: {tool_name}")
        self._render()

    def render_diff(self, diff_text: str) -> None:
        if diff_text:
            self.buffer.append_message("system", diff_text)
            self._render()

    async def display(self, message: str, level: str = "info") -> None:
        self.buffer.append_message(level, message)
        self._render()

    def _render(self) -> None:
        layout = Layout()
        layout.split_row(Layout(name="left", ratio=3), Layout(name="right", ratio=1))

        conversation = Text(self.buffer.render_text())
        layout["left"].update(Panel(conversation, title="Conversation"))

        context_lines = "\n".join(f"{k}: {v}" for k, v in self.context.items())
        layout["right"].update(Panel(Text(context_lines), title="Context"))

        self.console.clear()
        self.console.print(layout)
