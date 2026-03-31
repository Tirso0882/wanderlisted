"""Base class for specialized agents."""

from abc import ABC, abstractmethod
from typing import ClassVar, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool


class SpecializedAgent(ABC):
    """Base class for specialized sub-agents in multi-agent architecture."""

    name: ClassVar[str] = "BaseAgent"
    description: ClassVar[str] = "A specialized agent"

    def __init__(self, llm: Optional[BaseChatModel] = None):
        """Initialize agent with LLM and tools.

        Args:
            llm: Any LangChain chat model. If None, created via get_llm().
        """
        if llm is None:
            from src.agent.llm import get_llm
            llm = get_llm()
        self.llm = llm

    @property
    @abstractmethod
    def tools(self) -> list[BaseTool]:
        """Return list of tools available to this agent."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return system prompt for this agent."""
        pass

    def __repr__(self) -> str:
        return f"{self.name}(tools={len(self.tools)})"
