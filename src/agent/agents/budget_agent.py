"""Budget and financial planning agent."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import BUDGET_SYSTEM_PROMPT
from src.tools.budget import calculate_budget
from src.tools.currency import convert_currency


class BudgetAgent(SpecializedAgent):
    """Specialized agent for budget tracking and financial planning."""

    name = "BudgetAgent"
    description = "Expert in budget calculation, cost tracking, and currency conversion"

    @property
    def tools(self):
        return [calculate_budget, convert_currency]

    @property
    def system_prompt(self) -> str:
        return BUDGET_SYSTEM_PROMPT
