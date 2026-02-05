from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@dataclass
class PlainRenderer:
    def show_banner(self) -> None:
        print("Puk REPL")
        print("Type /exit to quit.")

    def show_tool_event(self, tool_name: str) -> None:
        print(f"\n[tool] {tool_name}")

    def write_delta(self, chunk: str) -> None:
        print(chunk, end="", flush=True)

    def end_message(self) -> None:
        print()


@dataclass
class FancyRenderer:
    console: Console

    def show_banner(self) -> None:
        title = Text("Puk", style="bold magenta")
        subtitle = "Two modes: plain and fancy • Type /exit to quit"
        self.console.print(Panel(subtitle, title=title, border_style="bright_blue"))

    def show_tool_event(self, tool_name: str) -> None:
        self.console.print(f"[bold cyan]tool[/bold cyan]: [white]{tool_name}[/white]")

    def write_delta(self, chunk: str) -> None:
        self.console.print(chunk, end="", soft_wrap=True)

    def end_message(self) -> None:
        self.console.print()
