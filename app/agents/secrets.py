from ..prompts import SECRETS_PROMPT
from ._base import BaseAgent


class SecretsAgent(BaseAgent):
    SYSTEM_PROMPT = SECRETS_PROMPT
    TOOLS = ("Read", "Bash")
