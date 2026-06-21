from ..prompts import AIVBM_PROMPT
from ._base import BaseAgent


class AIVBMAgent(BaseAgent):
    SYSTEM_PROMPT = AIVBM_PROMPT
    TOOLS = ("Read", "Bash")
