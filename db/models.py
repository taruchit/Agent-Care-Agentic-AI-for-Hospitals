import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='patient')  # 'patient' or 'admin'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PatientProfile(Base):
    __tablename__ = 'patient_profiles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    date_of_birth = Column(String(20))
    phone = Column(String(20))
    preferred_language = Column(String(20), default='English')
    emergency_contact = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Department(Base):
    __tablename__ = 'departments'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    active = Column(Boolean, default=True)

class Doctor(Base):
    __tablename__ = 'doctors'
    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)

class AppointmentSlot(Base):
    __tablename__ = 'appointment_slots'
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey('doctors.id'), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), default='available')  # 'available', 'booked'

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patient_profiles.id'), nullable=False)
    doctor_id = Column(Integer, ForeignKey('doctors.id'), nullable=False)
    slot_id = Column(Integer, ForeignKey('appointment_slots.id'), nullable=False)
    status = Column(String(20), default='confirmed')  # 'confirmed', 'rescheduled', 'cancelled'
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PatientDocument(Base):
    __tablename__ = 'patient_documents'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patient_profiles.id'), nullable=False)
    document_type = Column(String(50))  # e.g., 'ECG', 'Blood Report'
    file_path = Column(String(255), nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256 for duplicate checking
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class WorkflowRun(Base):
    __tablename__ = 'workflow_runs'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patient_profiles.id'), nullable=False)
    current_step = Column(String(50))
    state = Column(Text)  # JSON-serialized state
    status = Column(String(20), default='in_progress')  # 'in_progress', 'completed', 'escalated'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Escalation(Base):
    __tablename__ = 'escalations'
    id = Column(Integer, primary_key=True)
    workflow_run_id = Column(Integer, ForeignKey('workflow_runs.id'), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), default='pending')  # 'pending', 'approved', 'rejected'
    reviewed_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)