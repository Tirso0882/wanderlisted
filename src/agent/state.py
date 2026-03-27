from langgraph.graph import MessagesState


class TravelAgentState(MessagesState):
    """State for the travel agent. Extends MessagesState with session tracking."""

    session_id: str = ""
