from typing import TypedDict, Optional, Literal


class AgentResult(TypedDict):
    """
    Standard return contract for all agents.

    This contract is intentionally minimal and stable so that:
    - Streamlit UI
    - LangChain agents
    - LangGraph nodes
    - Error handler
    can all rely on the same shape.
    """

    status: Literal["success", "failed"]
    artifact: Optional[str]          # File path (PDF, DOC, etc.)
    message: str           # Error or info message
