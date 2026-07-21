# tools.py
import hashlib
import json
import datetime
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

def get_or_create_patient(user_id: int, name: str, email: str) -> dict:
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

def search_department_and_slots(dept_name: str) -> dict:
    """Retrieves department details and available appointment slots."""
    session = SessionLocal()
    try:
        dept = session.query(Department).filter(Department.name.ilike(f"%{dept_name}%")).first()
        if not dept:
            return {"status": "error", "message": f"Department '{dept_name}' not found."}
        
        doctors = session.query(Doctor).filter_by(department_id=dept.id, active=True).all()
        doc_ids = [d.id for d in doctors]
        
        slots = session.query(AppointmentSlot).filter(
            AppointmentSlot.doctor_id.in_(doc_ids),
            AppointmentSlot.status == 'available'
        ).all()
        
        slot_list = [
            {"slot_id": s.id, "doctor_id": s.doctor_id, "start": s.start_time.isoformat()} 
            for s in slots
        ]
        return {"status": "success", "department": dept.name, "dept_id": dept.id, "available_slots": slot_list}
    finally:
        session.close()

def book_appointment_slot(patient_id: int, doctor_id: int, slot_id: int, reason: str) -> dict:
    """Books a specific doctor slot and updates availability status."""
    session = SessionLocal()
    try:
        slot = session.query(AppointmentSlot).filter_by(id=slot_id, status='available').first()
        if not slot:
            return {"status": "error", "message": "Selected slot is no longer available."}
        
        # Mark slot booked
        slot.status = 'booked'
        
        # Create appointment record
        appt = Appointment(patient_id=patient_id, doctor_id=doctor_id, slot_id=slot_id, reason=reason)
        session.add(appt)
        session.commit()
        
        log_audit_event(actor_id=patient_id, action="BOOK_APPOINTMENT", entity_type="Appointment", entity_id=appt.id, metadata={"slot_id": slot_id})
        return {"status": "success", "appointment_id": appt.id, "message": "Appointment successfully booked."}
    finally:
        session.close()

def process_and_dedupe_document(patient_id: int, doc_type: str, file_path: str, file_bytes: bytes) -> dict:
    """Calculates SHA-256 checksum to block duplicate files and records document metadata."""
    session = SessionLocal()
    try:
        checksum = hashlib.sha256(file_bytes).hexdigest()
        
        # Check duplicate
        existing = session.query(PatientDocument).filter_by(patient_id=patient_id, checksum=checksum).first()
        if existing:
            return {"status": "duplicate", "message": f"Document already exists (ID: {existing.id})."}
        
        doc = PatientDocument(patient_id=patient_id, document_type=doc_type, file_path=file_path, checksum=checksum)
        session.add(doc)
        session.commit()
        
        log_audit_event(actor_id=patient_id, action="UPLOAD_DOCUMENT", entity_type="PatientDocument", entity_id=doc.id)
        return {"status": "success", "doc_id": doc.id, "checksum": checksum}
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