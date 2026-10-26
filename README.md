# NyayaSetu - Court Case Scheduling & Hearing Management System

NyayaSetu is an enterprise-grade judicial management platform that digitizes court case lifecycles, automates hearing scheduling via AI constraint optimization, tracks proceedings in real time, and facilitates secure virtual courtroom hearings with AI-assisted transcription.

Built according to IEEE 830 SRS specifications and the project UML Class Architecture.

---

## 🏛️ System Architecture & Domain Model

The domain architecture directly implements the UML specifications:
- **User Hierarchy (Joined Table Inheritance)**:
  - `User (Abstract)` $\rightarrow$ `Administrator`, `CourtClerk`, `Judge`, `Lawyer`, `Litigant`.
- **Case Lifecycle Management**:
  - `CourtCase`, `CaseDocument`, `DigitalEvidence`, `CaseHistory`, `CaseLawyerAssociation`.
- **Judicial Scheduling & Cause List**:
  - `Courtroom`, `Hearing`, `CauseList`, `Calendar`, `AIScheduler`.
- **Virtual Courtroom & Proceedings**:
  - `OnlineHearing`, `Transcript`.
- **Cross-Cutting Modules**:
  - `Notification`, `AuditLog`.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Virtual environment (`venv`)

### 2. Environment Setup
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Initialize & Seed Database
```powershell
python init_db.py
```
This creates the database schema and, when the database has no administrator, one bootstrap administrator so the system can be configured. It does not add sample users, cases, hearings, notifications, or courtrooms.

Set `BOOTSTRAP_ADMIN_PASSWORD` before initialization to choose a secure administrator password. The default development password is `Password@123`; change it before using the system outside local development. The administrator can create clerk, judge, and advocate accounts and register courtrooms from the dashboard. Litigants can register through the sign-in page.

### 4. Running Database Migrations
```powershell
alembic upgrade head
```

### 5. Start the FastAPI Server
```powershell
uvicorn app.main:app --reload --port 8000
```
- API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)
