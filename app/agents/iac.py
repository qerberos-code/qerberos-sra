from ..prompts import IAC_PROMPT
from ._base import BaseAgent


class IaCAgent(BaseAgent):
    SYSTEM_PROMPT = IAC_PROMPT
    TOOLS = ("Read", "Bash")
