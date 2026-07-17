from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.state import AgentState, LogEntry
from app.agents import mock_llm_engine, get_timestamp
from app.guardrails import validate_input_prompt, validate_output_content
from typing import Dict, Any

# Nodes
def input_guardrail_node(state: AgentState) -> Dict[str, Any]:
    prompt = state.get("initial_prompt", "")
    is_safe, error_msg = validate_input_prompt(prompt)
    
    logs = list(state.get("history", []))
    logs.append({
        "sender": "Input Guardrail",
        "message": "Validating user input prompt..." if is_safe else f"Rejected input: {error_msg}",
        "timestamp": get_timestamp()
    })
    
    if not is_safe:
        return {
            "status": "rejected",
            "history": logs,
            "current_agent": "System"
        }
    
    return {
        "status": "starting",
        "history": logs,
        "current_agent": "Product Manager"
    }

def pm_node(state: AgentState) -> Dict[str, Any]:
    prompt = state.get("initial_prompt", "")
    feedback = state.get("user_feedback")
    
    logs = list(state.get("history", []))
    action_desc = "Drafting initial Product Requirement Document (PRD)..." if not feedback else f"Revising PRD with user feedback: \"{feedback}\""
    
    logs.append({
        "sender": "Product Manager",
        "message": action_desc,
        "timestamp": get_timestamp()
    })
    
    # Generate PRD using Mock engine (or real LLM client in a production run)
    prd_content = mock_llm_engine.generate_prd(prompt, feedback, state.get("prd"))
    
    logs.append({
        "sender": "Product Manager",
        "message": "PRD generation draft complete. Awaiting human PM review approval.",
        "timestamp": get_timestamp()
    })
    
    return {
        "prd": prd_content,
        "status": "pm_review",
        "current_agent": "Human PM Reviewer",
        "user_feedback": None,  # Reset feedback after consumption
        "history": logs
    }

def human_pm_review_node(state: AgentState) -> Dict[str, Any]:
    # Placeholder node. Workflow pauses here via interrupt.
    return {"status": state.get("status")}

def tech_lead_node(state: AgentState) -> Dict[str, Any]:
    prd = state.get("prd", "")
    prompt = state.get("initial_prompt", "")
    feedback = state.get("user_feedback")
    
    logs = list(state.get("history", []))
    action_desc = "Analyzing PRD and drafting Technical Specification spec..." if not feedback else f"Revising Tech Spec with user feedback: \"{feedback}\""
    
    logs.append({
        "sender": "Tech Lead",
        "message": action_desc,
        "timestamp": get_timestamp()
    })
    
    tech_content = mock_llm_engine.generate_tech_design(prd, prompt, feedback, state.get("tech_design"))
    
    logs.append({
        "sender": "Tech Lead",
        "message": "Technical design specification complete. Awaiting human Architect approval.",
        "timestamp": get_timestamp()
    })
    
    return {
        "tech_design": tech_content,
        "status": "tech_review",
        "current_agent": "Human Architect Reviewer",
        "user_feedback": None,  # Reset feedback after consumption
        "history": logs
    }

def human_tech_review_node(state: AgentState) -> Dict[str, Any]:
    # Placeholder node. Workflow pauses here via interrupt.
    return {"status": state.get("status")}

def qa_node(state: AgentState) -> Dict[str, Any]:
    prd = state.get("prd", "")
    tech_design = state.get("tech_design", "")
    feedback = state.get("user_feedback")
    
    logs = list(state.get("history", []))
    logs.append({
        "sender": "QA Engineer",
        "message": "Creating comprehensive QA test suite based on PRD and Technical Design...",
        "timestamp": get_timestamp()
    })
    
    test_plan = mock_llm_engine.generate_test_plan(prd, tech_design, feedback, state.get("test_plan"))
    
    logs.append({
        "sender": "QA Engineer",
        "message": "QA validation test suite draft finalized.",
        "timestamp": get_timestamp()
    })
    
    return {
        "test_plan": test_plan,
        "current_agent": "Output Guardrail",
        "status": "qa_drafting",
        "history": logs
    }

def output_guardrail_node(state: AgentState) -> Dict[str, Any]:
    prd = state.get("prd", "")
    tech_design = state.get("tech_design", "")
    test_plan = state.get("test_plan", "")
    
    logs = list(state.get("history", []))
    logs.append({
        "sender": "Output Guardrail",
        "message": "Validating finalized package formatting and security metrics...",
        "timestamp": get_timestamp()
    })
    
    for doc, name in [(prd, "PRD"), (tech_design, "Tech Spec"), (test_plan, "Test Plan")]:
        is_safe, error_msg = validate_output_content(doc)
        if not is_safe:
            logs.append({
                "sender": "Output Guardrail",
                "message": f"Validation failed for {name}: {error_msg}",
                "timestamp": get_timestamp()
            })
            return {
                "status": "rejected",
                "current_agent": "System",
                "history": logs
            }
            
    logs.append({
        "sender": "System Orchestrator",
        "message": "All items passed guardrail validation. Project package successfully completed!",
        "timestamp": get_timestamp()
    })
    
    return {
        "status": "completed",
        "current_agent": "Completed",
        "history": logs
    }

# Conditional routing edges
def route_after_input_guardrail(state: AgentState) -> str:
    if state.get("status") == "rejected":
        return END
    return "pm_node"

def route_after_pm_review(state: AgentState) -> str:
    # If there is active feedback, rerun PM node
    if state.get("user_feedback"):
        return "pm_node"
    return "tech_lead_node"

def route_after_tech_review(state: AgentState) -> str:
    # If there is active feedback, rerun Tech Lead node
    if state.get("user_feedback"):
        return "tech_lead_node"
    return "qa_node"

# Building the LangGraph state graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("input_guardrail_node", input_guardrail_node)
workflow.add_node("pm_node", pm_node)
workflow.add_node("human_pm_review_node", human_pm_review_node)
workflow.add_node("tech_lead_node", tech_lead_node)
workflow.add_node("human_tech_review_node", human_tech_review_node)
workflow.add_node("qa_node", qa_node)
workflow.add_node("output_guardrail_node", output_guardrail_node)

# Set Entry Point
workflow.set_entry_point("input_guardrail_node")

# Define Transitions & Routes
workflow.add_conditional_edges(
    "input_guardrail_node",
    route_after_input_guardrail,
    {
        END: END,
        "pm_node": "pm_node"
    }
)

# Flow moves: pm_node -> human_pm_review_node (where it will interrupt before entering)
workflow.add_edge("pm_node", "human_pm_review_node")

workflow.add_conditional_edges(
    "human_pm_review_node",
    route_after_pm_review,
    {
        "pm_node": "pm_node",
        "tech_lead_node": "tech_lead_node"
    }
)

# Flow moves: tech_lead_node -> human_tech_review_node (where it will interrupt before entering)
workflow.add_edge("tech_lead_node", "human_tech_review_node")

workflow.add_conditional_edges(
    "human_tech_review_node",
    route_after_tech_review,
    {
        "tech_lead_node": "tech_lead_node",
        "qa_node": "qa_node"
    }
)

# Flow moves: qa_node -> output_guardrail_node -> END
workflow.add_edge("qa_node", "output_guardrail_node")
workflow.add_edge("output_guardrail_node", END)

# In-memory checkpoint database
memory_saver = MemorySaver()

# Compile graph with human review interrupts
compiled_graph = workflow.compile(
    checkpointer=memory_saver,
    interrupt_before=["human_pm_review_node", "human_tech_review_node"]
)
