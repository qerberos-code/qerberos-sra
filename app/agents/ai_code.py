from ..prompts import AI_CODE_PROMPT
from ._base import BaseAgent


class AICodeAgent(BaseAgent):
    SYSTEM_PROMPT = AI_CODE_PROMPT
    TOOLS = ("Read", "Bash")
