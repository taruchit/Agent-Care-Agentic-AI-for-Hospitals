import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models import Base, Department, Doctor, AppointmentSlot, User

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, Department, Doctor, AppointmentSlot, User
import datetime

DATABASE_URL = "sqlite:///agentcare.db"

def seed_data():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed Admin User
    if not session.query(User).filter_by(email="admin@hospital.com").first():
        admin = User(name="Admin Staff", email="admin@hospital.com", password_hash="hashed_pw", role="admin")
        session.add(admin)

    # Seed Departments
    cardio = Department(name="Cardiology", description="Heart and cardiovascular care")
    ortho = Department(name="Orthopedics", description="Bones, joints, and musculoskeletal system")
    gen_med = Department(name="General Medicine", description="Primary care and routine checkups")
    
    session.add_all([cardio, ortho, gen_med])
    session.commit()

    # Seed Doctors
    doc1 = Doctor(department_id=cardio.id, name="Dr. Sarah Jenkins")
    doc2 = Doctor(department_id=ortho.id, name="Dr. Robert Chen")
    session.add_all([doc1, doc2])
    session.commit()

    # Seed Slots
    now = datetime.datetime.utcnow()
    slot1 = AppointmentSlot(doctor_id=doc1.id, start_time=now + datetime.timedelta(days=1, hours=2), end_time=now + datetime.timedelta(days=1, hours=3))
    slot2 = AppointmentSlot(doctor_id=doc1.id, start_time=now + datetime.timedelta(days=2, hours=4), end_time=now + datetime.timedelta(days=2, hours=5))
    session.add_all([slot1, slot2])

    session.commit()
    print("Database successfully seeded!")
    session.close()

if __name__ == "__main__":
    seed_data()