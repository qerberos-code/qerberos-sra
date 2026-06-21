from ..prompts import DEPENDENCY_PROMPT
from ._base import BaseAgent


class DependencyAgent(BaseAgent):
    SYSTEM_PROMPT = DEPENDENCY_PROMPT
    TOOLS = ("Read", "Bash")
