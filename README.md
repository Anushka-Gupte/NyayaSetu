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
This sets up SQLite/PostgreSQL schemas and seeds default accounts:
- **Admin**: `admin` / `admin@court.gov.in` (Password: `Password@123`)
- **Court Clerk**: `clerk1` / `clerk1@court.gov.in` (Password: `Password@123`)
- **Judge 1**: `judge_sharma` / `judge.sharma@court.gov.in` (Password: `Password@123`)
- **Judge 2**: `judge_patel` / `judge.patel@court.gov.in` (Password: `Password@123`)
- **Lawyer 1**: `adv_verma` / `adv.verma@barcouncil.in` (Password: `Password@123`)
- **Lawyer 2**: `adv_rao` / `adv.rao@barcouncil.in` (Password: `Password@123`)
- **Litigant 1**: `rajesh_k` / `rajesh.kumar@gmail.com` (Password: `Password@123`)
- **Litigant 2**: `sunita_d` / `sunita.deshmukh@gmail.com` (Password: `Password@123`)

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
