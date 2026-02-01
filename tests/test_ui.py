"""Tests for puk.ui module."""
from __future__ import annotations

import pytest

from puk.errors import MissingInfoError
from puk.ui import ConversationBuffer, NonInteractiveIO, PlainIO


class TestConversationBuffer:
    def test_initial_state(self):
        buffer = ConversationBuffer()
        assert buffer.messages == []

    def test_append_message(self):
        buffer = ConversationBuffer()
        buffer.append_message("user", "Hello")
        assert len(buffer.messages) == 1
        assert buffer.messages[0] == {"role": "user", "content": "Hello"}

    def test_append_multiple_messages(self):
        buffer = ConversationBuffer()
        buffer.append_message("user", "Hello")
        buffer.append_message("assistant", "Hi there!")
        assert len(buffer.messages) == 2
        assert buffer.messages[0]["role"] == "user"
        assert buffer.messages[1]["role"] == "assistant"

    def test_append_delta_creates_new_message(self):
        buffer = ConversationBuffer()
        buffer.append_delta("assistant", "Hello")
        assert len(buffer.messages) == 1
        assert buffer.messages[0] == {"role": "assistant", "content": "Hello"}

    def test_append_delta_extends_same_role(self):
        buffer = ConversationBuffer()
        buffer.append_delta("assistant", "Hel")
        buffer.append_delta("assistant", "lo")
        assert len(buffer.messages) == 1
        assert buffer.messages[0]["content"] == "Hello"

    def test_append_delta_creates_new_for_different_role(self):
        buffer = ConversationBuffer()
        buffer.append_delta("user", "Hi")
        buffer.append_delta("assistant", "Hello")
        assert len(buffer.messages) == 2
        assert buffer.messages[0]["role"] == "user"
        assert buffer.messages[1]["role"] == "assistant"

    def test_render_text(self):
        buffer = ConversationBuffer()
        buffer.append_message("user", "Hello")
        buffer.append_message("assistant", "Hi there!")
        text = buffer.render_text()
        assert "USER: Hello" in text
        assert "ASSISTANT: Hi there!" in text

    def test_render_text_limits_to_200_messages(self):
        buffer = ConversationBuffer()
        for i in range(250):
            buffer.append_message("user", f"Message {i}")
        text = buffer.render_text()
        # Should only contain last 200 messages
        assert "Message 50" in text
        assert "Message 249" in text
        # First 50 should be excluded
        lines = text.split("\n")
        assert len(lines) == 200


class TestPlainIO:
    @pytest.fixture
    def io(self) -> PlainIO:
        return PlainIO()

    @pytest.mark.asyncio
    async def test_display(self, io: PlainIO, capsys):
        await io.display("Test message", "info")
        captured = capsys.readouterr()
        assert "[info] Test message" in captured.out

    @pytest.mark.asyncio
    async def test_display_with_different_levels(self, io: PlainIO, capsys):
        await io.display("Warning!", "warning")
        captured = capsys.readouterr()
        assert "[warning] Warning!" in captured.out

    def test_assistant_delta(self, io: PlainIO, capsys):
        io.assistant_delta("Hello")
        captured = capsys.readouterr()
        assert captured.out == "Hello"

    def test_assistant_complete(self, io: PlainIO, capsys):
        io.assistant_complete()
        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_tool_invocation(self, io: PlainIO, capsys):
        io.tool_invocation("test_tool")
        captured = capsys.readouterr()
        assert "[tool] test_tool" in captured.out

    def test_render_diff(self, io: PlainIO, capsys):
        io.render_diff("-old\n+new")
        captured = capsys.readouterr()
        assert "-old" in captured.out
        assert "+new" in captured.out

    def test_render_diff_empty(self, io: PlainIO, capsys):
        io.render_diff("")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_update_context_is_noop(self, io: PlainIO):
        result = io.update_context({"key": "value"})
        assert result is None

    def test_has_buffer(self, io: PlainIO):
        assert isinstance(io.buffer, ConversationBuffer)


class TestPlainIOConfirm:
    @pytest.fixture
    def io(self) -> PlainIO:
        return PlainIO()

    @pytest.mark.asyncio
    async def test_confirm_yes(self, io: PlainIO, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        result = await io.confirm("Proceed?", False)
        assert result is True

    @pytest.mark.asyncio
    async def test_confirm_yes_variations(self, io: PlainIO, monkeypatch):
        for response in ["y", "yes", "Y", "YES", "Yes", "true", "1"]:
            monkeypatch.setattr("builtins.input", lambda _, r=response: r)
            result = await io.confirm("Proceed?", False)
            assert result is True

    @pytest.mark.asyncio
    async def test_confirm_no(self, io: PlainIO, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        result = await io.confirm("Proceed?", True)
        assert result is False

    @pytest.mark.asyncio
    async def test_confirm_empty_uses_default_true(self, io: PlainIO, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = await io.confirm("Proceed?", True)
        assert result is True

    @pytest.mark.asyncio
    async def test_confirm_empty_uses_default_false(self, io: PlainIO, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = await io.confirm("Proceed?", False)
        assert result is False


class TestPlainIOPrompt:
    @pytest.fixture
    def io(self) -> PlainIO:
        return PlainIO()

    @pytest.mark.asyncio
    async def test_prompt_with_input(self, io: PlainIO, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "user input")
        result = await io.prompt("Enter value:")
        assert result == "user input"

    @pytest.mark.asyncio
    async def test_prompt_empty_with_default(self, io: PlainIO, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = await io.prompt("Enter value:", "default_value")
        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_prompt_strips_whitespace(self, io: PlainIO, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "  value  ")
        result = await io.prompt("Enter value:")
        assert result == "value"


class TestPlainIOSelect:
    @pytest.fixture
    def io(self) -> PlainIO:
        return PlainIO()

    @pytest.mark.asyncio
    async def test_select_valid_choice(self, io: PlainIO, monkeypatch, capsys):
        inputs = iter(["2"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        result = await io.select("Choose:", ["a", "b", "c"], 0)
        assert result == "b"

    @pytest.mark.asyncio
    async def test_select_empty_uses_default(self, io: PlainIO, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = await io.select("Choose:", ["a", "b", "c"], 1)
        assert result == "b"

    @pytest.mark.asyncio
    async def test_select_invalid_then_valid(self, io: PlainIO, monkeypatch, capsys):
        inputs = iter(["invalid", "5", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        result = await io.select("Choose:", ["a", "b"], 0)
        assert result == "a"
        captured = capsys.readouterr()
        assert "Invalid selection" in captured.out


class TestNonInteractiveIO:
    @pytest.fixture
    def io(self) -> NonInteractiveIO:
        return NonInteractiveIO()

    @pytest.mark.asyncio
    async def test_display_works(self, io: NonInteractiveIO, capsys):
        await io.display("Message", "info")
        captured = capsys.readouterr()
        assert "[info] Message" in captured.out

    @pytest.mark.asyncio
    async def test_confirm_raises(self, io: NonInteractiveIO):
        with pytest.raises(MissingInfoError, match="Confirmation required"):
            await io.confirm("Proceed?", False)

    @pytest.mark.asyncio
    async def test_prompt_raises(self, io: NonInteractiveIO):
        with pytest.raises(MissingInfoError, match="Missing required input"):
            await io.prompt("Enter value:")

    @pytest.mark.asyncio
    async def test_select_raises(self, io: NonInteractiveIO):
        with pytest.raises(MissingInfoError, match="Missing selection"):
            await io.select("Choose:", ["a", "b"], 0)

    def test_assistant_delta_works(self, io: NonInteractiveIO, capsys):
        io.assistant_delta("Hello")
        captured = capsys.readouterr()
        assert captured.out == "Hello"

    def test_tool_invocation_works(self, io: NonInteractiveIO, capsys):
        io.tool_invocation("tool")
        captured = capsys.readouterr()
        assert "[tool] tool" in captured.out
