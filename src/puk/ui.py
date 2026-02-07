from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConsoleRenderer:
    _buffer: str = field(default="", init=False)

    def show_banner(self) -> None:
        print("Puk REPL")
        print("Enter for a new line • Ctrl+J to send • Type /exit to quit")

    def show_tool_event(self, tool_name: str) -> None:
        print(f"\n[tool] {tool_name}")

    def write_delta(self, chunk: str) -> None:
        self._buffer += chunk
        lines = self._buffer.splitlines(keepends=True)
        if not lines:
            return
        if lines and not lines[-1].endswith("\n"):
            self._buffer = lines.pop()
        else:
            self._buffer = ""
        for line in lines:
            print(line, end="", flush=True)

    def end_message(self) -> None:
        if self._buffer:
            print(self._buffer, end="", flush=True)
            self._buffer = ""
        print()
