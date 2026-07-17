import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.graph import compiled_graph
from app.state import LogEntry

app = FastAPI(title="Multi-Agent PM Orchestrator API")

# Enable CORS for local development compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database of active sessions just to store session keys
sessions_db: Dict[str, Dict[str, Any]] = {}

# Pydantic schemas
class StartRequest(BaseModel):
    prompt: str

class FeedbackRequest(BaseModel):
    feedback: Optional[str] = None  # None indicates approval/proceed
    approve: bool = False           # True indicates approval

class SessionStatusResponse(BaseModel):
    session_id: str
    initial_prompt: str
    current_agent: str
    status: str
    prd: Optional[str]
    tech_design: Optional[str]
    test_plan: Optional[str]
    history: List[Dict[str, Any]]
    feedback_requested: bool
    is_processing: bool

# Backend task helper to run the graph asynchronously
def run_graph_async(session_id: str, state_update: Optional[Dict[str, Any]] = None, as_node: Optional[str] = None):
    config = {"configurable": {"thread_id": session_id}}
    try:
        if session_id in sessions_db:
            sessions_db[session_id]["is_processing"] = True
            
        if state_update:
            compiled_graph.update_state(config, state_update, as_node=as_node)
            compiled_graph.invoke(None, config=config)
        else:
            # First execution
            initial_state = {
                "initial_prompt": sessions_db[session_id]["prompt"],
                "prd": None,
                "tech_design": None,
                "test_plan": None,
                "current_agent": "Input Guardrail",
                "status": "starting",
                "user_feedback": None,
                "history": [],
                "mode": "mock",
                "model_name": "MockLLM"
            }
            compiled_graph.invoke(initial_state, config=config)
    except Exception as e:
        print(f"Error during graph execution for thread {session_id}: {e}")
    finally:
        if session_id in sessions_db:
            sessions_db[session_id]["is_processing"] = False

@app.post("/api/orchestrate/start", response_model=Dict[str, str])
def start_session(req: StartRequest, background_tasks: BackgroundTasks):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
    session_id = str(uuid.uuid4())
    sessions_db[session_id] = {
        "id": session_id,
        "prompt": req.prompt,
        "is_processing": True
    }
    
    # Start the LangGraph workflow in the background
    background_tasks.add_task(run_graph_async, session_id)
    
    return {"session_id": session_id}

@app.get("/api/orchestrate/status/{session_id}", response_model=SessionStatusResponse)
def get_session_status(session_id: str):
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
        
    config = {"configurable": {"thread_id": session_id}}
    state_snapshot = compiled_graph.get_state(config)
    is_processing = sessions_db[session_id].get("is_processing", False)
    
    if not state_snapshot or not state_snapshot.values:
        # It might still be setting up the initial state in the background thread
        return SessionStatusResponse(
            session_id=session_id,
            initial_prompt=sessions_db[session_id]["prompt"],
            current_agent="System",
            status="starting",
            prd=None,
            tech_design=None,
            test_plan=None,
            history=[],
            feedback_requested=False,
            is_processing=True
        )
        
    values = state_snapshot.values
    
    # Determine if we are currently paused waiting for human feedback
    # We are only paused if the next nodes contain human and the backend is NOT actively processing
    is_paused = (
        not is_processing
        and len(state_snapshot.next) > 0 
        and any("human" in node for node in state_snapshot.next)
    )
    
    return SessionStatusResponse(
        session_id=session_id,
        initial_prompt=values.get("initial_prompt", ""),
        current_agent=values.get("current_agent", "System"),
        status=values.get("status", "starting"),
        prd=values.get("prd"),
        tech_design=values.get("tech_design"),
        test_plan=values.get("test_plan"),
        history=values.get("history", []),
        feedback_requested=is_paused,
        is_processing=is_processing
    )

@app.post("/api/orchestrate/feedback/{session_id}")
def submit_feedback(session_id: str, req: FeedbackRequest, background_tasks: BackgroundTasks):
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
        
    config = {"configurable": {"thread_id": session_id}}
    state_snapshot = compiled_graph.get_state(config)
    
    if not state_snapshot or not state_snapshot.next:
        raise HTTPException(status_code=400, detail="Session is not currently awaiting feedback or is completed")
        
    # Prepare state update parameters
    state_update = {}
    if req.approve:
        state_update["user_feedback"] = None
        # We also manually record a history entry for approval
        history = list(state_snapshot.values.get("history", []))
        history.append({
            "sender": "Human Reviewer",
            "message": "Approved. Advancing workflow to next agent stage.",
            "timestamp": "Now"
        })
        state_update["history"] = history
    else:
        if not req.feedback or not req.feedback.strip():
            raise HTTPException(status_code=400, detail="Feedback content cannot be empty if not approving")
        state_update["user_feedback"] = req.feedback.strip()
        history = list(state_snapshot.values.get("history", []))
        history.append({
            "sender": "Human Reviewer",
            "message": f"Submitted feedback: \"{req.feedback}\". Returning draft to agent for revision.",
            "timestamp": "Now"
        })
        state_update["history"] = history

    # Determine which node we are acting on behalf of
    status = state_snapshot.values.get("status")
    as_node = "pm_node" if status == "pm_review" else "tech_lead_node"

    # Mark as processing before starting background task to avoid instant polling race condition
    sessions_db[session_id]["is_processing"] = True

    # Resume graph execution in the background
    background_tasks.add_task(run_graph_async, session_id, state_update, as_node)
    
    return {"status": "resumed"}

# UI Static files and root route
@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")

# Mount Static Files (index.css, app.js, etc.)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
