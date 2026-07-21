# agents/graph.py
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
import os
from dotenv import load_dotenv

# Load environment variables before initializing LangChain / Groq components
load_dotenv()

from langchain_groq import ChatGroq
import os
import json

from tools import (
    search_department_and_slots, 
    book_appointment_slot, 
    trigger_human_escalation
)

# Define LangGraph State
class AgentState(TypedDict):
    patient_id: int
    user_input: str
    is_emergency_or_medical: bool
    target_department: Optional[str]
    slot_id: Optional[int]
    doctor_id: Optional[int]
    escalated: bool
    response_summary: str

# Initialize LLM (Ensure GROQ_API_KEY is set in .env)
llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

# Agent 1: Safety & Guardrail Node
def safety_guardrail_agent(state: AgentState) -> AgentState:
    prompt = f"""You are a Healthcare Safety Guardrail Agent.
    Evaluate the user request: "{state['user_input']}"
    
    CRITICAL RULE: The system CANNOT diagnose conditions, prescribe drugs, or give medical advice.
    Also detect emergency situations (e.g. severe chest pain, extreme bleeding).
    
    Respond in raw JSON only:
    {{"is_medical_or_emergency": true/false, "reason": "brief explanation"}}
    """
    res = llm.invoke([SystemMessage(content=prompt)])
    try:
        data = json.loads(res.content.strip())
        if data.get("is_medical_or_emergency"):
            state["is_emergency_or_medical"] = True
            state["escalated"] = True
            state["response_summary"] = "Request flagged for safety review or emergency handling. Escalated to hospital staff."
            trigger_human_escalation(workflow_run_id=1, reason=data.get("reason", "Non-administrative query"))
    except Exception:
        pass
    return state

# Agent 2: Department Routing Agent
def department_routing_agent(state: AgentState) -> AgentState:
    if state.get("escalated"):
        return state
        
    prompt = f"""You are a Department Routing Agent.
    Identify which hospital department best fits this request: "{state['user_input']}"
    Available options: "Cardiology", "Orthopedics", "General Medicine".
    
    Respond in raw JSON:
    {{"department": "Department Name"}}
    """
    res = llm.invoke([SystemMessage(content=prompt)])
    try:
        data = json.loads(res.content.strip())
        state["target_department"] = data.get("department", "General Medicine")
    except Exception:
        state["target_department"] = "General Medicine"
    return state

# Agent 3: Appointment Booking Agent
def appointment_agent(state: AgentState) -> AgentState:
    if state.get("escalated"):
        return state
        
    dept = state.get("target_department", "General Medicine")
    slots_data = search_department_and_slots(dept)
    
    if slots_data.get("status") == "success" and slots_data.get("available_slots"):
        selected_slot = slots_data["available_slots"][0]
        booking_res = book_appointment_slot(
            patient_id=state["patient_id"],
            doctor_id=selected_slot["doctor_id"],
            slot_id=selected_slot["slot_id"],
            reason=state["user_input"]
        )
        if booking_res.get("status") == "success":
            state["response_summary"] = f"Appointment successfully booked in {dept} for slot starting at {selected_slot['start']}."
        else:
            state["response_summary"] = "Could not complete booking."
    else:
        state["response_summary"] = f"No available slots found for {dept}."
        
    return state

# Conditional Router
def route_after_safety(state: AgentState) -> str:
    if state.get("escalated"):
        return "end"
    return "route_department"

# Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("safety_check", safety_guardrail_agent)
workflow.add_node("route_department", department_routing_agent)
workflow.add_node("appointment_booking", appointment_agent)

workflow.set_entry_point("safety_check")

workflow.add_conditional_edges(
    "safety_check",
    route_after_safety,
    {
        "end": END,
        "route_department": "route_department"
    }
)

workflow.add_edge("route_department", "appointment_booking")
workflow.add_edge("appointment_booking", END)

agent_care_app = workflow.compile()