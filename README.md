# AgentCare — Agentic AI for Patient Administration

AgentCare is a proof-of-concept healthcare administration system that uses a LangGraph-based multi-agent workflow to support non-clinical patient tasks such as appointment discovery, booking, cancellation, document upload, and escalation for human review. The system is designed to keep medical decision-making under human oversight while automating routine administrative workflows.

## Architecture Overview

The project is organized into four main layers:

1. User Interface Layer
   - [app.py](app.py) provides a Streamlit-based interface for patients and hospital staff.
   - Patients can submit requests, attach documents, and view appointments.
   - Staff can review escalations and audit logs.

2. Workflow / Agent Layer
   - [agents/graph.py](agents/graph.py) defines the LangGraph workflow and the agent nodes that process a user request.
   - The workflow routes requests through safety screening, intent interpretation, and execution.

3. Tool / Business Logic Layer
   - [tools.py](tools.py) contains the reusable operations that interact with the database and implement domain actions.
   - These tools handle appointments, document deduplication, auditing, and escalation.

4. Data Layer
   - [db/models.py](db/models.py) defines the SQLAlchemy models for patients, departments, doctors, appointments, documents, escalations, and audit events.
   - The application uses SQLite for local persistence.

## How the System Works

A typical request flows through the system as follows:

1. A user enters a request in the Streamlit app.
2. The safety guardrail agent checks whether the request appears medical, emergency-related, or unsafe.
3. If the request is administrative, an intent classifier determines whether the user wants to search, book, cancel, or reschedule.
4. The execution handler calls the appropriate tool to perform the action.
5. Results are stored in the database, and audit or escalation events are recorded for traceability.

## Agents

### Safety & Guardrail Agent
Located in [agents/graph.py](agents/graph.py), this agent evaluates whether a request should be allowed to proceed as an administrative workflow or escalated for human review. It flags medical or emergency-like language and prevents unsafe requests from continuing automatically.

### Intent Classification Agent
Also defined in [agents/graph.py](agents/graph.py), this agent interprets the user’s request and extracts the likely intent. It identifies whether the user is trying to:
- search for available slots,
- book an appointment,
- cancel an existing appointment,
- or reschedule an appointment.

### Execution / Tool Handler Agent
This agent uses the workflow state to invoke the correct business action. It coordinates the interaction between the LangGraph workflow and the underlying tools, turning the parsed intent into a concrete operation such as searching for slots or creating an appointment.

## Tools

The core tool functions in [tools.py](tools.py) encapsulate the application’s operational logic:

- `log_audit_event` writes compliance-oriented audit records.
- `get_or_create_patient` creates or retrieves a patient profile.
- `search_department_and_slots` queries available appointment slots by department.
- `book_appointment_slot` books an available slot and creates an appointment record.
- `cancel_appointment_slot` cancels an appointment and frees the associated slot.
- `reschedule_appointment_slot` moves a patient from one slot to another.
- `process_and_dedupe_document` computes a SHA-256 checksum to prevent duplicate document uploads and stores document metadata.
- `trigger_human_escalation` creates a pending escalation for staff review.

## Data Model Highlights

The schema in [db/models.py](db/models.py) models the main hospital administration entities:

- `User` for patients and administrators
- `PatientProfile` for patient context and contact details
- `Department` and `Doctor` for routing and scheduling
- `AppointmentSlot` and `Appointment` for availability and booking
- `PatientDocument` for uploaded medical files
- `Escalation` and `AuditEvent` for oversight and compliance

## Project Structure

- [app.py](app.py) — Streamlit entry point and UI orchestration
- [agents/graph.py](agents/graph.py) — LangGraph workflow and agent logic
- [tools.py](tools.py) — database-backed business tools and helpers
- [db/models.py](db/models.py) — SQLAlchemy data models
- [db/seed.py](db/seed.py) — seed data for departments, doctors, and slots
- [tests/](tests/) — automated tests for the agent workflow behavior

## Quickstart

### Prerequisites
- Python 3.10 or higher
- A Groq API key (or another supported LLM provider configured in the environment)

### Installation
```bash
git clone https://github.com/taruchit/Agent-Care-Agentic-AI-for-Hospitals.git
cd Agent-Care-Agentic-AI-for-Hospitals
pip install -r requirements.txt
```

### Environment Setup
Create a `.env` file and set your LLM API key, for example:

```bash
GROQ_API_KEY=your_key_here
```

### Initialize the Database
```bash
python db/seed.py
```

### Run the Application
```bash
streamlit run app.py
```

### Run Tests
```bash
pytest tests/
```

## Notes

This repository is intentionally a prototype focused on workflow orchestration, human-in-the-loop oversight, and administrative automation. It is not a clinical decision support system, and sensitive medical requests are routed to human review rather than processed autonomously.