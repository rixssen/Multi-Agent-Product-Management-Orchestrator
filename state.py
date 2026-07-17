from typing import TypedDict, List, Dict, Any, Optional

class LogEntry(TypedDict):
    sender: str
    message: str
    timestamp: str

class AgentState(TypedDict):
    """
    State tracking dictionary passed between nodes in the LangGraph workflow.
    """
    initial_prompt: str
    prd: Optional[str]
    tech_design: Optional[str]
    test_plan: Optional[str]
    
    current_agent: str
    status: str  # "starting", "pm_review", "tech_review", "qa_drafting", "completed", "rejected"
    user_feedback: Optional[str]
    history: List[LogEntry]
    
    # Configuration controls
    mode: str  # "mock" or "real"
    model_name: str
