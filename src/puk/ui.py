from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConsoleRenderer:
    _buffer: str = field(default="", init=False)
    _thinking_visible: bool = field(default=False, init=False)

    def show_banner(self) -> None:
        print("Puk REPL")
        print(
            "Enter for a new line • Ctrl+J to send • Commands: /runs, /run <id>, /tail <id>, /exit to quit"
        )

    def show_tool_event(self, tool_name: str) -> None:
        print(f"[tool] {tool_name}")

    def show_tool_result(self, tool_name: str, success: bool | None, summary: str | None) -> None:
        if success is True:
            status = "ok"
        elif success is False:
            status = "error"
        else:
            status = "done"
        parts = [f"[tool] {tool_name}", status]
        if summary:
            compact = " ".join(summary.strip().split())
            if len(compact) > 180:
                compact = compact[:177] + "..."
            parts.append(compact)
        print(" ".join(parts))

    def show_working(self) -> None:
        if self._thinking_visible:
            return
        self._thinking_visible = True
        print("Puk is thinking...", end="", flush=True)

    def hide_working(self) -> None:
        if not self._thinking_visible:
            return
        self._thinking_visible = False
        print("\r" + (" " * 20) + "\r", end="", flush=True)

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
