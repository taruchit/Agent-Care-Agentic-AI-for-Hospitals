import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import AppointmentSlot, Base, Department, Doctor, User

DATABASE_URL = "sqlite:///agentcare.db"


def seed_data():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Clean up existing records to avoid duplicates across runs
    session.query(AppointmentSlot).delete()
    session.query(Doctor).delete()
    session.query(Department).delete()
    session.commit()

    # Seed Admin User
    if not session.query(User).filter_by(email="admin@hospital.com").first():
        admin = User(
            name="Admin Staff",
            email="admin@hospital.com",
            password_hash="hashed_pw",
            role="admin",
        )
        session.add(admin)

    # Seed Departments
    cardio = Department(
        name="Cardiology", description="Heart and cardiovascular care"
    )
    ortho = Department(
        name="Orthopedics",
        description="Bones, joints, and musculoskeletal system",
    )
    gen_med = Department(
        name="General Medicine", description="Primary care and routine checkups"
    )

    session.add_all([cardio, ortho, gen_med])
    session.commit()

    # Seed Doctors (Stored without "Dr." prefix)
    doc1 = Doctor(department_id=cardio.id, name="Sarah Jenkins")
    doc2 = Doctor(department_id=ortho.id, name="Robert Chen")
    session.add_all([doc1, doc2])
    session.commit()

    # Seed Slots across multiple timeframes
    now = datetime.datetime.utcnow()

    slots = [
        # Cardiology (Sarah Jenkins)
        AppointmentSlot(
            doctor_id=doc1.id,
            start_time=now + datetime.timedelta(days=1, hours=2),
            end_time=now + datetime.timedelta(days=1, hours=3),
        ),
        AppointmentSlot(
            doctor_id=doc1.id,
            start_time=now + datetime.timedelta(days=7, hours=2),
            end_time=now + datetime.timedelta(days=7, hours=3),
        ),
        # Orthopedics (Robert Chen) - Next Week
        AppointmentSlot(
            doctor_id=doc2.id,
            start_time=now + datetime.timedelta(days=7, hours=4),
            end_time=now + datetime.timedelta(days=7, hours=5),
        ),
        # Orthopedics (Robert Chen) - Next Month
        AppointmentSlot(
            doctor_id=doc2.id,
            start_time=now + datetime.timedelta(days=30, hours=4),
            end_time=now + datetime.timedelta(days=30, hours=5),
        ),
    ]

    session.add_all(slots)
    session.commit()

    print("Database successfully seeded!")
    session.close()


if __name__ == "__main__":
    seed_data()