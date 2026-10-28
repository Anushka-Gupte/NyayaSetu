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

Set a private `SECRET_KEY` in `.env` before starting the app. Set `APP_BASE_URL` to the public HTTPS application URL so password reset emails link back to the correct site. Use `CORS_ORIGINS` to list the exact browser origins that should be allowed, encoded as a JSON array, for example `CORS_ORIGINS=["http://localhost:8000"]`. Set `SESSION_IDLE_TIMEOUT_MINUTES` to change the browser inactivity timeout. The built-in local origins are for development only.

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

### Notification delivery providers

In-app notifications work without additional provider credentials. To enable outbound email, configure these environment variables before starting the server:

```text
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=court@example.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

For Twilio SMS delivery, configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER`. Indian 10-digit mobile numbers are sent with the `+91` country code. If a provider is not configured or rejects a message, the notification is recorded as `Failed` and remains eligible for an administrator retry; it is not reported as delivered.

### Google Meet virtual hearings

The virtual hearing provider can be selected with `VIRTUAL_COURT_PROVIDER`. The default is `jitsi`; set it to `google_meet` to create restricted Google Meet spaces through the Meet REST API. Google Meet sessions open in a new browser tab because the REST API provisions and manages a conference but does not embed its live audio/video UI in NyayaSetu.

To configure Google Meet:

1. In Google Cloud Console, create/select a project, enable the **Google Meet REST API**, and configure the OAuth consent screen for the users who will administer hearings.
2. Create an OAuth client ID of type **Web application** (or another client type appropriate to your deployment) and obtain an **offline refresh token** for the Google Workspace account that should own the hearing spaces. Authorize the `https://www.googleapis.com/auth/meetings.space.created` scope. A service account alone is not supported by this integration.
3. Add these values to the root `.env` file. Keep the client secret and refresh token private; do not commit `.env`.

```text
VIRTUAL_COURT_PROVIDER=google_meet
GOOGLE_MEET_CLIENT_ID=your-oauth-client-id
GOOGLE_MEET_CLIENT_SECRET=your-oauth-client-secret
GOOGLE_MEET_REFRESH_TOKEN=your-offline-refresh-token
```

4. Apply the schema migration and restart the application:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

5. As a clerk or administrator, create/join a virtual session for a hearing. The service obtains an access token from the refresh token, creates a restricted Meet space, and saves its meeting URL and provider resource name. Participants use the **Join video conference** link to open Google Meet. Because NyayaSetu does not yet invite Google identities as Meet members, the Meet host may need to admit participants. Google controls admission; NyayaSetu's attendance log records when an authorized user clicks its join/leave actions and is not a live feed of actual Meet attendance.

The configured OAuth user must have access to Google Meet and the Meet API scope. Workspace policies and OAuth consent-screen status can affect authorization and refresh-token lifetime. Google Meet recordings, transcripts, live participant synchronization, invitations, and Meet Embed SDK are not connected by this initial integration. Existing sessions keep their stored provider and link if the configured provider later changes.
