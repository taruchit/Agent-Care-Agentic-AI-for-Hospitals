# tools.py
import hashlib
import json
import datetime
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import (
    PatientProfile, User, Department, Doctor, 
    AppointmentSlot, Appointment, PatientDocument, 
    Escalation, AuditEvent
)

DATABASE_URL = "sqlite:///agentcare.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def log_audit_event(actor_id: int, action: str, entity_type: str, entity_id: int, metadata: dict = None):
    """Writes an explicit audit log for compliance and tracking."""
    session = SessionLocal()
    try:
        audit = AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=json.dumps(metadata or {})
        )
        session.add(audit)
        session.commit()
    finally:
        session.close()

def get_or_create_patient(user_id: int, name: str = "", email: str = "") -> dict:
    """Finds existing patient profile or creates a new one."""
    session = SessionLocal()
    try:
        profile = session.query(PatientProfile).filter_by(user_id=user_id).first()
        if not profile:
            profile = PatientProfile(user_id=user_id)
            session.add(profile)
            session.commit()
            log_audit_event(actor_id=user_id, action="CREATE_PATIENT_PROFILE", entity_type="PatientProfile", entity_id=profile.id)
        
        return {"patient_id": profile.id, "user_id": user_id}
    finally:
        session.close()

def search_department_and_slots(dept_name: Optional[str] = None) -> str:
    """
    Retrieves available appointment slots cleanly formatted.
    """
    session = SessionLocal()
    try:
        query = (
            session.query(AppointmentSlot, Doctor, Department)
            .join(Doctor, AppointmentSlot.doctor_id == Doctor.id)
            .join(Department, Doctor.department_id == Department.id)
            .filter(AppointmentSlot.status == 'available')
        )
        
        if dept_name and dept_name.strip():
            query = query.filter(Department.name.ilike(f"%{dept_name.strip()}%"))
        
        results = query.all()
        if not results:
            target = f"for department '{dept_name}'" if dept_name else "across all departments"
            return {"status": "error", "message": f"No available slots found {target}."}
        
        slot_list = []
        for slot, doctor, department in results:
            # Fix duplicate "Dr." prefix
            doc_name = doctor.name.strip() if hasattr(doctor, "name") and doctor.name else f"Doctor #{doctor.id}"
            if not doc_name.startswith("Dr."):
                doc_name = f"Dr. {doc_name}"
                
            # Safe datetime formatting
            st = slot.start_time
            if isinstance(st, datetime.datetime):
                formatted_time = st.strftime("%Y-%m-%d %I:%M %p")
            elif isinstance(st, datetime.date):
                formatted_time = st.strftime("%Y-%m-%d")
            else:
                formatted_time = str(st)

            slot_list.append({
                "slot_id": slot.id,
                "doctor_id": doctor.id,
                "doctor_name": doc_name,
                "department": department.name if hasattr(department, "name") else "General Medicine",
                "start": formatted_time
            })
            
        return {
            "status": "success", 
            "total_available": len(slot_list), 
            "available_slots": slot_list
        }
    finally:
        session.close()

def book_appointment_slot(patient_id: int, slot_id: int, doctor_id: Optional[int] = None, reason: str = "General Consultation") -> dict:
    """
    Books a specific appointment slot by slot_id for a patient.
    If doctor_id is not passed, it automatically looks it up from the slot record.
    """
    session = SessionLocal()
    try:
        slot = session.query(AppointmentSlot).filter_by(id=slot_id, status='available').first()
        if not slot:
            return {"status": "error", "message": f"Slot ID #{slot_id} is no longer available or does not exist."}
        
        # Auto-resolve doctor_id if omitted by LLM
        assigned_doctor_id = doctor_id if doctor_id else slot.doctor_id

        # Mark slot as booked
        slot.status = 'booked'
        
        # Create appointment record
        appt = Appointment(patient_id=patient_id, doctor_id=assigned_doctor_id, slot_id=slot_id, reason=reason)
        session.add(appt)
        session.commit()
        
        log_audit_event(actor_id=patient_id, action="BOOK_APPOINTMENT", entity_type="Appointment", entity_id=appt.id, metadata={"slot_id": slot_id})
        return {
            "status": "success", 
            "appointment_id": appt.id, 
            "slot_id": slot_id,
            "message": f"Appointment successfully booked for slot #{slot_id}."
        }
    finally:
        session.close()

def cancel_appointment_slot(patient_id: int, slot_id: int) -> dict:
    """Cancels a booked appointment slot and frees it up for other patients."""
    session = SessionLocal()
    try:
        appt = session.query(Appointment).filter_by(patient_id=patient_id, slot_id=slot_id).first()
        if not appt:
            return {"status": "error", "message": f"No active appointment found for slot ID #{slot_id}."}
        
        # Free up the slot
        slot = session.query(AppointmentSlot).filter_by(id=slot_id).first()
        if slot:
            slot.status = 'available'
            
        session.delete(appt)
        session.commit()
        
        log_audit_event(actor_id=patient_id, action="CANCEL_APPOINTMENT", entity_type="Appointment", entity_id=slot_id)
        return {"status": "success", "message": f"Appointment for slot #{slot_id} cancelled successfully."}
    finally:
        session.close()

def reschedule_appointment_slot(patient_id: int, old_slot_id: int, new_slot_id: int, reason: str = "Rescheduled") -> dict:
    """Atomically reschedules an appointment from an existing slot to a new slot."""
    cancel_res = cancel_appointment_slot(patient_id=patient_id, slot_id=old_slot_id)
    if cancel_res["status"] == "error":
        return cancel_res
    
    book_res = book_appointment_slot(patient_id=patient_id, slot_id=new_slot_id, reason=reason)
    if book_res["status"] == "error":
        # Re-lock the old slot if booking the new one fails
        book_appointment_slot(patient_id=patient_id, slot_id=old_slot_id, reason="Rollback")
        return {"status": "error", "message": f"Could not reserve new slot #{new_slot_id}. Retained old slot #{old_slot_id}."}
    
    return {"status": "success", "message": f"Rescheduled successfully from slot #{old_slot_id} to slot #{new_slot_id}."}

def process_and_dedupe_document(patient_id: int, doc_type: str, file_path: str, file_bytes: bytes) -> dict:
    """Calculates SHA-256 checksum to block duplicate files and records document metadata."""
    session = SessionLocal()
    try:
        checksum = hashlib.sha256(file_bytes).hexdigest()
        
        # Check duplicate
        existing = session.query(PatientDocument).filter_by(patient_id=patient_id, checksum=checksum).first()
        if existing:
            return {"status": "duplicate", "message": f"Document already exists in database (Document ID: {existing.id})."}
        
        doc = PatientDocument(patient_id=patient_id, document_type=doc_type, file_path=file_path, checksum=checksum)
        session.add(doc)
        session.commit()
        
        log_audit_event(actor_id=patient_id, action="UPLOAD_DOCUMENT", entity_type="PatientDocument", entity_id=doc.id)
        return {"status": "success", "doc_id": doc.id, "checksum": checksum, "message": "Document uploaded and deduplicated successfully."}
    finally:
        session.close()

def trigger_human_escalation(workflow_run_id: int, reason: str) -> dict:
    """Flags sensitive/unsafe/emergency requests for human review."""
    session = SessionLocal()
    try:
        escalation = Escalation(workflow_run_id=workflow_run_id, reason=reason, status="pending")
        session.add(escalation)
        session.commit()
        
        log_audit_event(actor_id=0, action="TRIGGER_ESCALATION", entity_type="Escalation", entity_id=escalation.id, metadata={"reason": reason})
        return {"status": "escalated", "escalation_id": escalation.id, "reason": reason}
    finally:
        session.close()