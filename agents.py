import os
import datetime
import httpx
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv(override=True)

def get_timestamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def call_gemini_model(system_instruction: str, prompt_text: str) -> Optional[str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or "your_copied_api_key" in api_key:
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": f"Instruction: {system_instruction}\n\nInput Context:\n{prompt_text}"}]
            }
        ]
    }
    try:
        response = httpx.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30.0)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"Gemini API returned status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

def call_groq_api(system_instruction: str, prompt_text: str) -> Optional[str]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
        
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.5
    }
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=20.0)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"Groq API returned status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return None

def call_openrouter_api(system_instruction: str, prompt_text: str) -> Optional[str]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "PM Orchestrator Dashboard"
    }
    payload = {
        "model": "tencent/hy3:free",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt_text}
        ],
        "max_tokens": 1200
    }
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=80.0)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"OpenRouter API returned status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error calling OpenRouter API: {e}")
        return None

def call_any_active_llm(system_instruction: str, prompt_text: str) -> Optional[str]:
    # Reload environment to pick up newly saved keys dynamically
    load_dotenv(override=True)
    
    # Strictly call OpenRouter as requested
    if os.environ.get("OPENROUTER_API_KEY"):
        res = call_openrouter_api(system_instruction, prompt_text)
        if res:
            return res
            
    return None

class DynamicMockLLM:
    """
    Simulates a dynamic LLM that generates markdown artifacts based on input prompts
    and integrates human-in-the-loop feedback to show iterative refinements.
    """
    
    def generate_prd(self, prompt: str, feedback: Optional[str] = None, current_prd: Optional[str] = None) -> str:
        # Try real LLM first
        system_instruction = "You are an expert Product Manager. Write a highly detailed markdown Product Requirement Document (PRD) based on the user's idea. If a current draft and user feedback are provided, revise the current draft to incorporate the changes."
        input_text = f"Product Idea: {prompt}\n\nCurrent Draft:\n{current_prd if current_prd else 'None'}\n\nUser Feedback / Revisions: {feedback if feedback else 'None'}"
        
        real_response = call_any_active_llm(system_instruction, input_text)
        if real_response:
            return real_response
            
        # Fallback to Mock
        base_features = [
            "- **User Authentication**: Secure email/password login and session management.",
            "- **Core Dashboard**: User-friendly navigation interface listing all active modules.",
            "- **Data Persistence**: Offline capability with automatic database syncing."
        ]
        
        feedback_banner = ""
        feedback_additions = []
        if feedback:
            feedback_banner = f"\n> [!IMPORTANT]\n> **Active Revision Request**: Incorporating feedback *\"{feedback}\"*\n"
            fb_lower = feedback.lower()
            if "ordered" in fb_lower or "quantity" in fb_lower or "item" in fb_lower:
                feedback_additions.append("- **Order & Quantity Verification**: Automated checking logic to verify all items from the ordered list are present in the correct quantities.")
            else:
                feedback_additions.append(f"- **[REVISED FEATURE]**: Incorporated user feedback: *\"{feedback}\"*")
            
        prd_template = f"""# Product Requirement Document (PRD)
## Project Name: Project {prompt.strip().split()[0].capitalize() if prompt else "Core"}
*Generated on: {get_timestamp()} (Mock Agent Fallback)*

{feedback_banner}
---

### 1. Executive Summary
The goal of this project is to build: **{prompt}**.
This PRD outlines the scope, objectives, and detailed feature checklist required for a successful launch.

### 2. Objectives & Success Metrics
- **Objective**: Deliver a production-ready, highly reliable system based on the specifications.
- **Success Metrics**: 
  - 99.9% uptime of all orchestrator services.
  - Sub-second UI response time.
  - Positive user adoption rate.

### 3. Functional Requirements
{chr(10).join(base_features)}
{chr(10).join(feedback_additions) if feedback_additions else ""}

### 4. Non-Functional Requirements
- **Security**: Strict encryption of data in transit and at rest.
- **Scalability**: High throughput support with modular architecture.
- **Maintainability**: Clear API contracts and documented class hierarchy.
"""
        return prd_template

    def generate_tech_design(self, prd: str, prompt: str, feedback: Optional[str] = None, current_tech: Optional[str] = None) -> str:
        # Try real LLM first
        system_instruction = "You are a Principal Software Architect. Draft a detailed markdown Technical Design Specification based on the provided PRD. If user feedback and a current draft are provided, revise the current draft spec to incorporate the changes."
        input_text = f"PRD:\n{prd}\n\nOriginal Idea: {prompt}\n\nCurrent Draft Spec:\n{current_tech if current_tech else 'None'}\n\nUser Feedback / Revisions: {feedback if feedback else 'None'}"
        
        real_response = call_any_active_llm(system_instruction, input_text)
        if real_response:
            return real_response
            
        # Fallback to Mock
        project_name = prompt.strip().split()[0].capitalize() if prompt else "Core"
        feedback_banner = ""
        feedback_tech = ""
        if feedback:
            feedback_banner = f"\n> [!IMPORTANT]\n> **Active Revision Request**: Incorporating feedback *\"{feedback}\"*\n"
            feedback_tech = f"\n- **[REVISED DESIGN]**: Adapted design to handle user feedback: *\"{feedback}\"*\n"

        tech_template = f"""# Technical Design Specification
## Project: {project_name} Architecture
*Generated on: {get_timestamp()} (Mock Agent Fallback)*

{feedback_banner}
---

### 1. System Architecture
We propose a modern containerized microservice architecture backend built with FastAPI, connected to a robust PostgreSQL database for storage, with Redis for fast caching.

```mermaid
graph TD
    Client[Web Client] --> FastAPI[FastAPI Backend Gateway]
    FastAPI --> DB[(PostgreSQL Database)]
    FastAPI --> Cache[(Redis Cache)]
```

### 2. Component Design & API Schema
The backend exposes high-performance rest endpoints:
- `POST /api/v1/resource` - Create resource
- `GET /api/v1/resource/{{id}}` - Retrieve resource details

### 3. Database Schema
```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. Technical Specifications & Adjustments
- **Runtime**: Python 3.10+
- **Framework**: FastAPI with asynchronous drivers (`asyncpg`)
{feedback_tech}
"""
        return tech_template

    def generate_test_plan(self, prd: str, tech_design: str, feedback: Optional[str] = None, current_test_plan: Optional[str] = None) -> str:
        # Try real LLM first
        system_instruction = "You are a Lead QA Engineer. Draft a comprehensive markdown QA Test and Validation Plan based on the provided PRD and Technical Design Spec. If user feedback and a current draft plan are provided, revise the current plan to incorporate the changes."
        input_text = f"PRD:\n{prd}\n\nTech Design:\n{tech_design}\n\nCurrent Draft Plan:\n{current_test_plan if current_test_plan else 'None'}\n\nUser Feedback / Revisions: {feedback if feedback else 'None'}"
        
        real_response = call_any_active_llm(system_instruction, input_text)
        if real_response:
            return real_response
            
        # Fallback to Mock
        test_template = f"""# QA Test & Validation Plan
*Generated on: {get_timestamp()} (Mock Agent Fallback)*

---

### 1. Testing Strategy
Our validation plan covers end-to-end user scenarios, rigorous unit testing of API logic, and security checks on data payloads.

### 2. Test Cases
| Test ID | Component | Description | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **TC-001** | Authentication | Attempt login with invalid credentials | API returns 401 Unauthorized |
| **TC-002** | Core API | Create resource payload validation | API returns 201 Created and saves entity |
| **TC-003** | Guardrails | Send banned SQL commands to prompt | Input guardrail blocks the request immediately |

### 3. Performance & Load Validation
- **Concurrency**: Target 500 concurrent users using Locust.
- **Latency**: Ensure P95 latency is less than 300ms.
- **Security Check**: Check headers for CORS and proper JWT verification.
"""
        return test_template

# Instance to import
mock_llm_engine = DynamicMockLLM()

