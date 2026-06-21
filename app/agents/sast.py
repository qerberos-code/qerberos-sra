from ..prompts import SAST_PROMPT
from ._base import BaseAgent


class SASTAgent(BaseAgent):
    SYSTEM_PROMPT = SAST_PROMPT
    TOOLS = ("Read", "Bash")
