from ..prompts import COMPLIANCE_PROMPT
from ._base import BaseAgent


class ComplianceAgent(BaseAgent):
    SYSTEM_PROMPT = COMPLIANCE_PROMPT
    TOOLS = ("Read", "Bash")
