from __future__ import annotations

from pydantic import BaseModel, Field
from copilot.tools import define_tool

from ..ui import UserIO


class DisplayMessageParams(BaseModel):
    message: str = Field(description="Message to display to the user")
    level: str = Field(default="info", description="Message level: info, warning, error, success")


class ConfirmActionParams(BaseModel):
    question: str = Field(description="Yes/no question to ask the user")
    default: bool = Field(default=False, description="Default if user just presses enter")


class PromptUserParams(BaseModel):
    question: str = Field(description="Question to ask the user")
    default: str = Field(default="", description="Default value if user provides none")


class SelectOptionParams(BaseModel):
    question: str = Field(description="Question to ask")
    options: list[str] = Field(description="Available options")
    default_index: int = Field(default=0, description="Default option index")


def create_user_io_tools(io: UserIO):
    @define_tool(description="Display a message to the user")
    async def display_message(params: DisplayMessageParams) -> dict:
        await io.display(params.message, params.level)
        return {"displayed": True}

    @define_tool(description="Ask the user for yes/no confirmation")
    async def confirm_action(params: ConfirmActionParams) -> dict:
        confirmed = await io.confirm(params.question, params.default)
        return {"confirmed": confirmed}

    @define_tool(description="Prompt the user for text input")
    async def prompt_user(params: PromptUserParams) -> dict:
        response = await io.prompt(params.question, params.default)
        return {"response": response}

    @define_tool(description="Ask the user to select from a list")
    async def select_option(params: SelectOptionParams) -> dict:
        selected = await io.select(params.question, params.options, params.default_index)
        index = params.options.index(selected) if selected in params.options else params.default_index
        return {"selected": selected, "index": index}

    return [display_message, confirm_action, prompt_user, select_option]
