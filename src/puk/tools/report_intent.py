from __future__ import annotations

from pydantic import BaseModel, Field
from copilot.tools import define_tool

from ..reports import RunReport


class ReportIntentParams(BaseModel):
    intent: str = Field(description="Short description of the intended action")


def create_report_intent_tool(report: RunReport):
    @define_tool(description="Log the assistant's current intent before acting")
    async def report_intent(params: ReportIntentParams) -> str:
        report.log_tool("report_intent", params.model_dump(), {"logged": True})
        return "Intent logged"

    return report_intent
