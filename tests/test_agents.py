# tests/test_agents.py
import sys
from pathlib import Path

# Explicitly add root project directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import os
import hashlib
from tools import (
    process_and_dedupe_document, 
    search_department_and_slots, 
    SessionLocal,
)
from db.models import Base, PatientProfile, User
from tools import engine

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Create test user/patient if missing
    user = session.query(User).filter_by(email="test@patient.com").first()
    if not user:
        user = User(name="Test Patient", email="test@patient.com", password_hash="dummy", role="patient")
        session.add(user)
        session.commit()
        profile = PatientProfile(user_id=user.id)
        session.add(profile)
        session.commit()
    session.close()

def test_search_department_and_slots():
    res = search_department_and_slots("Cardiology")
    assert "status" in res
    if res["status"] == "success":
        assert "available_slots" in res

def test_document_deduplication():
    dummy_bytes = b"Sample Medical Report Content"
    patient_id = 1
    
    # First Upload
    res1 = process_and_dedupe_document(patient_id, "ECG", "ecg.pdf", dummy_bytes)
    assert res1["status"] in ["success", "duplicate"]
    
    # Duplicate Upload
    res2 = process_and_dedupe_document(patient_id, "ECG", "ecg_copy.pdf", dummy_bytes)
    assert res2["status"] == "duplicate"