# Agent-Care-Agentic-AI-for-Hospitals
# AgentCare — Agentic AI for Patient Administration and Care Coordination

AgentCare is an agentic AI system designed to streamline non-clinical healthcare administration tasks—including patient registration, department routing, appointment scheduling, document classification with deduplication, and follow-up reminders—while keeping all clinical decisions under human supervision.

---

## 🤖 Multi-Agent Network Roles

1. **Safety & Guardrail Agent**: Intercepts requests to block diagnostic/prescriptive language and routes emergencies or medical queries to the Human Escalation Queue.
2. **Department Routing Agent**: Analyzes administrative intent and maps requests to active departments (Cardiology, Orthopedics, General Medicine).
3. **Appointment Agent**: Queries doctor availability, resolves schedule conflicts, and persists confirmed bookings.
4. **Document Agent**: Processes medical files, computes SHA-256 checksums to block duplicate uploads, and links file metadata to the patient profile.

---

## 🚀 Quickstart & Setup Instructions

### 1. Prerequisites
- Python 3.10 or higher
- A Groq API Key (or OpenAI key)

### 2. Installation
```bash
# Clone repository
git clone [https://github.com/taruchit/Agent-Care-Agentic-AI-for-Hospitals.git](https://github.com/taruchit/Agent-Care-Agentic-AI-for-Hospitals.git)
cd Agent-Care-Agentic-AI-for-Hospitals

# Install dependencies
pip install -r requirements.txt

# Environment Setup
cp .env.example .env
# Edit .env and set your GROQ_API_KEY

### 3. Initialize & Seed Database
python db/seed.py

### 4. Run Application
streamlit run app.py

### 5. Run Test Suite
pytest tests/

---

## Step 3: Local Verification Checklist

Run these quick commands locally before pushing to GitHub:

```bash
# 1. Run tests to confirm compilation and DB logic
pytest tests/

# 2. Verify gitignore hides local environment files
echo ".env" >> .gitignore
echo "agentcare.db" >> .gitignore