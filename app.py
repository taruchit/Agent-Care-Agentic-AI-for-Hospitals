# app.py
import streamlit as st
from db.seed import seed_data
from db.models import Base, User, Appointment, PatientDocument, Escalation, AuditEvent, PatientProfile
from tools import process_and_dedupe_document, SessionLocal, engine
from agents.graph import agent_care_app
import json

# Ensure DB schema and seed data exist
Base.metadata.create_all(engine)
seed_data()

st.set_page_config(page_title="AgentCare — Patient Administration", layout="wide")

st.title("🏥 AgentCare — Healthcare Administration System")
st.caption("Agentic AI for non-clinical patient workflows with human oversight")

# Sidebar - Role Selection & Backend RBAC Simulation
st.sidebar.header("Role Switcher (RBAC)")
current_role = st.sidebar.selectbox("Select Active Role", ["Patient", "Hospital Staff / Admin"])

session = SessionLocal()

if current_role == "Patient":
    st.header("👤 Patient Portal")
    
    # Get or default patient ID
    patient = session.query(PatientProfile).first()
    patient_id = patient.id if patient else 1
    
    tab1, tab2 = st.tabs(["Submit Request", "My Records & Documents"])
    
    with tab1:
        st.subheader("Submit Administrative Request")
        user_input = st.text_area("How can we help you today?", placeholder="e.g., I need a cardiology appointment next week and want to attach my previous ECG.")
        
        uploaded_file = st.file_uploader("Attach Medical Document (PDF/JPG/PNG)", type=["pdf", "png", "jpg"])
        
        if st.button("Submit Request", type="primary"):
            if not user_input.strip():
                st.warning("Please enter a request.")
            else:
                doc_msg = ""
                if uploaded_file:
                    bytes_data = uploaded_file.read()
                    doc_res = process_and_dedupe_document(
                        patient_id=patient_id,
                        doc_type="Uploaded Report",
                        file_path=uploaded_file.name,
                        file_bytes=bytes_data
                    )
                    if doc_res["status"] == "duplicate":
                        st.info(f"📄 Document note: {doc_res['message']}")
                    else:
                        st.success("📄 Document uploaded and verified.")

                # Run LangGraph Workflow
                initial_state = {
                    "patient_id": patient_id,
                    "user_input": user_input,
                    "is_emergency_or_medical": False,
                    "target_department": None,
                    "slot_id": None,
                    "doctor_id": None,
                    "escalated": False,
                    "response_summary": ""
                }
                
                with st.spinner("Processing workflow across agent network..."):
                    final_state = agent_care_app.invoke(initial_state)
                
                if final_state.get("escalated"):
                    st.error(f"⚠️ {final_state['response_summary']}")
                else:
                    st.success(f"✅ {final_state['response_summary']}")

    with tab2:
        st.subheader("My Appointments")
        appts = session.query(Appointment).filter_by(patient_id=patient_id).all()
        if appts:
            for a in appts:
                st.write(f"• **Appointment ID:** {a.id} | **Doctor ID:** {a.doctor_id} | **Status:** {a.status} | **Reason:** {a.reason}")
        else:
            st.info("No appointments scheduled.")
            
        st.subheader("My Uploaded Documents")
        docs = session.query(PatientDocument).filter_by(patient_id=patient_id).all()
        if docs:
            for d in docs:
                st.write(f"• **{d.document_type}** | File: `{d.file_path}` | Checksum: `{d.checksum[:10]}...` | Uploaded: {d.created_at}")
        else:
            st.info("No documents uploaded.")

elif current_role == "Hospital Staff / Admin":
    st.header("👨‍⚕️ Hospital Staff & Escalation Dashboard")
    
    st.subheader("⚠️ Pending Human Escalations & Review Queue")
    pending_escalations = session.query(Escalation).filter_by(status="pending").all()
    
    if pending_escalations:
        for esc in pending_escalations:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**Escalation ID #{esc.id}** — Reason: *{esc.reason}*")
            with col2:
                if st.button("Approve", key=f"app_{esc.id}"):
                    esc.status = "approved"
                    session.commit()
                    st.success("Approved!")
                    st.rerun()
            with col3:
                if st.button("Reject", key=f"rej_{esc.id}"):
                    esc.status = "rejected"
                    session.commit()
                    st.error("Rejected!")
                    st.rerun()
    else:
        st.success("No pending escalations in queue.")

    st.markdown("---")
    st.subheader("📜 Audit Log Trail")
    logs = session.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(10).all()
    for log in logs:
        st.text(f"[{log.created_at}] Action: {log.action} | Entity: {log.entity_type}#{log.entity_id} | Actor: {log.actor_id}")

session.close()