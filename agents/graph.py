# agents/graph.py
import json
import os
from typing import Optional, TypedDict
from dotenv import load_dotenv

# Load environment variables before initializing LangChain / Groq components
load_dotenv()

from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from tools import (
    book_appointment_slot,
    cancel_appointment_slot,
    process_and_dedupe_document,
    reschedule_appointment_slot,
    search_department_and_slots,
    trigger_human_escalation,
)

# Define LangGraph State
class AgentState(TypedDict):
    patient_id: int
    user_input: str
    is_emergency_or_medical: bool
    intent: Optional[str]            # 'search', 'book', 'cancel', 'reschedule', 'document'
    target_department: Optional[str]
    slot_id: Optional[int]
    old_slot_id: Optional[int]
    new_slot_id: Optional[int]
    escalated: bool
    response_summary: str

# Initialize LLM
llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

# -------------------------------------------------------------------------
# Node 1: Safety & Guardrail Agent
# -------------------------------------------------------------------------
def safety_guardrail_agent(state: AgentState) -> AgentState:
    prompt = f"""You are a Healthcare Safety Guardrail Agent.
Evaluate the user request: "{state['user_input']}"

SAFETY CRITERIA:
- FLAG TRUE ONLY IF: The user describes active, severe physical medical symptoms (e.g. chest pain, extreme bleeding, shortness of breath, severe pain, self-harm) or asks for direct medical diagnosis/prescriptions.
- DO NOT FLAG (FLAG FALSE): Administrative queries like searching for available slots, booking appointments, listing doctors, or asking about departments.

Respond in RAW JSON ONLY:
{{"is_medical_or_emergency": false, "reason": "Administrative scheduling query"}}
"""
    res = llm.invoke([SystemMessage(content=prompt)])
    try:
        content = res.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        
        if data.get("is_medical_or_emergency") is True:
            state["is_emergency_or_medical"] = True
            state["escalated"] = True
            state["response_summary"] = "⚠️ Request flagged for safety review or emergency handling. Escalated to hospital staff."
            trigger_human_escalation(workflow_run_id=1, reason=data.get("reason", "Medical query flagged by guardrail"))
    except Exception as e:
        # In case of JSON parse error, allow administrative flow to continue
        pass
    return state

# -------------------------------------------------------------------------
# Node 2: Intent Classification & Entity Extraction Agent
# -------------------------------------------------------------------------
def intent_classifier_agent(state: AgentState) -> AgentState:
    if state.get("escalated"):
        return state

    prompt = f"""You are an Intent Classification Agent for a hospital platform.
Analyze the user request: "{state['user_input']}"

RULES:
1. "search": User wants to find, list, or check available slots/doctors/departments.
2. "book": User explicitly mentions "book", "reserve", or provides a slot ID to confirm.
3. "cancel": User wants to cancel an appointment or slot ID.
4. "reschedule": User wants to move or reschedule from one slot to another.

Return RAW JSON ONLY (no markdown code blocks):
{{
  "intent": "search" | "book" | "cancel" | "reschedule",
  "department": "Cardiology" | "Orthopedics" | "General Medicine" | null,
  "slot_id": 3,
  "patient_id": 1
}}

Note: Parse digits carefully. If user says "slot ID 3", set slot_id = 3. If user says "Patient ID 1", set patient_id = 1.
"""
    res = llm.invoke([SystemMessage(content=prompt)])
    try:
        content = res.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        
        state["intent"] = data.get("intent", "search")
        state["target_department"] = data.get("department")
        
        if data.get("slot_id") is not None:
            state["slot_id"] = int(data.get("slot_id"))
        if data.get("patient_id") is not None:
            state["patient_id"] = int(data.get("patient_id"))
            
    except Exception:
        # Simple regex fallback if LLM JSON parsing fails
        import re
        text = state["user_input"].lower()
        if "book" in text:
            state["intent"] = "book"
            slot_match = re.search(r"slot\s*(?:id)?\s*(\d+)", text)
            if slot_match:
                state["slot_id"] = int(slot_match.group(1))
        else:
            state["intent"] = "search"
            if "cardiology" in text:
                state["target_department"] = "Cardiology"

    return state


# -------------------------------------------------------------------------
# Node 3: Tool Handler Agent
# -------------------------------------------------------------------------
def execution_handler_agent(state: AgentState) -> AgentState:
    if state.get("escalated"):
        return state

    intent = state.get("intent", "search")
    patient_id = state.get("patient_id", 1)

    # 1. DISCOVERY / SEARCH
    if intent == "search":
        dept = state.get("target_department")
        res = search_department_and_slots(dept)
        if res.get("status") == "success" and res.get("available_slots"):
            slot_info = [
                f"Slot #{s['slot_id']}: Dr. {s['doctor_name']} ({s['department']}) at {s['start']}"
                for s in res["available_slots"]
            ]
            state["response_summary"] = "Available Slots Found:\n" + "\n".join(slot_info)
        else:
            dept_str = f"for department '{dept}'" if dept else "across all departments"
            state["response_summary"] = f"No available slots found {dept_str}."

    # 2. BOOK APPOINTMENT
    elif intent == "book":
        slot_id = state.get("slot_id")
        if not slot_id:
            state["response_summary"] = "Please specify a slot ID to book (e.g., 'Book slot ID 3')."
        else:
            res = book_appointment_slot(patient_id=patient_id, slot_id=slot_id, reason=state["user_input"])
            if res.get("status") == "success":
                state["response_summary"] = f"✅ Appointment successfully booked for slot #{slot_id}!"
            else:
                state["response_summary"] = f"❌ {res.get('message', 'Booking failed.')}"

    # 3. CANCEL APPOINTMENT
    elif intent == "cancel":
        slot_id = state.get("slot_id")
        if not slot_id:
            state["response_summary"] = "Please specify the slot ID you want to cancel."
        else:
            res = cancel_appointment_slot(patient_id=patient_id, slot_id=slot_id)
            if res.get("status") == "success":
                state["response_summary"] = f"❌ Appointment for slot #{slot_id} has been cancelled."
            else:
                state["response_summary"] = f"⚠️ {res.get('message', 'Cancellation failed.')}"

    # 4. RESCHEDULE APPOINTMENT
    elif intent == "reschedule":
        old_id = state.get("old_slot_id") or state.get("slot_id")
        new_id = state.get("new_slot_id")
        if not old_id or not new_id:
            state["response_summary"] = "Please specify both the old slot ID and new slot ID to reschedule."
        else:
            res = reschedule_appointment_slot(patient_id=patient_id, old_slot_id=old_id, new_slot_id=new_id)
            if res.get("status") == "success":
                state["response_summary"] = f"🔄 Rescheduled successfully from slot #{old_id} to slot #{new_id}."
            else:
                state["response_summary"] = f"⚠️ {res.get('message', 'Reschedule failed.')}"

    # DEFAULT FALLBACK
    else:
        state["response_summary"] = "I can help you search doctors, book/cancel slots, or process medical documents."

    return state


# -------------------------------------------------------------------------
# Conditional Router
# -------------------------------------------------------------------------
def route_after_safety(state: AgentState) -> str:
    if state.get("escalated"):
        return "end"
    return "classify_intent"


# -------------------------------------------------------------------------
# Build LangGraph
# -------------------------------------------------------------------------
workflow = StateGraph(AgentState)

workflow.add_node("safety_check", safety_guardrail_agent)
workflow.add_node("classify_intent", intent_classifier_agent)
workflow.add_node("execution_handler", execution_handler_agent)

workflow.set_entry_point("safety_check")

workflow.add_conditional_edges(
    "safety_check",
    route_after_safety,
    {
        "end": END,
        "classify_intent": "classify_intent"
    }
)

workflow.add_edge("classify_intent", "execution_handler")
workflow.add_edge("execution_handler", END)

agent_care_app = workflow.compile()