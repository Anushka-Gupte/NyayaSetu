# NyayaSetu API Documentation & Frontend Integration Reference

This document provides the complete API specification for binding frontend templates to the **NyayaSetu** backend platform.

- **Base URL**: `http://localhost:8000/api/v1`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **ReDoc Interactive Reference**: `http://localhost:8000/redoc`
- **OpenAPI Schema (JSON)**: `openapi.json`

---

## 🔐 1. Authentication & Role-Based Access Control (RBAC)

All protected endpoints require the HTTP Header:
`Authorization: Bearer <access_token>`

### User Roles
- `ADMINISTRATOR`
- `COURT_CLERK`
- `JUDGE`
- `LAWYER`
- `LITIGANT`

### Endpoints
| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | Login with username/email & password; returns JWT token + role. | Public |
| `POST` | `/auth/token` | OAuth2 password flow for Swagger UI interactive login. | Public |
| `GET` | `/auth/me` | Current user profile with role-specific judicial details. | Authenticated |
| `POST` | `/auth/logout` | Terminates active session and records audit event. | Authenticated |
| `POST` | `/auth/password-reset-request` | Requests password reset instructions. | Public |
| `POST` | `/auth/password-reset-confirm` | Confirms password reset with new password. | Public |
| `POST` | `/users` | Administrator onboards new clerks, judges, lawyers, litigants. | Administrator |
| `GET` | `/users` | Lists users with optional `?role=` filter. | Admin, Clerk |
| `PUT` | `/users/{user_id}/status` | Activates or deactivates user accounts. | Administrator |
| `GET` | `/users/judges/available` | Lists active judges and their availability. | Authenticated |

---

## 📊 2. Dynamic Role Dashboards (SRS Section 3.1)

| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/dashboard/overview` | Dynamically returns tailored operational metrics based on caller role. | All Roles |

- **Admin**: `total_users`, `total_cases`, `active_cases`, `disposed_cases`, `total_courtrooms`, `recent_audit_activities`.
- **Clerk**: `cases_registered_today`, `total_cases`, `hearings_today`, `pending_cause_lists`.
- **Judge**: `assigned_cases_count`, `today_hearings_count`, `pending_judgments`, `today_schedule`.
- **Lawyer**: `total_assigned_cases`, `upcoming_hearings_count`, `upcoming_hearings`.
- **Litigant**: `my_cases_count`, `my_cases`, `upcoming_hearings`.

---

## 📁 3. Case Registration & Digital Evidence Repository

| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `POST` | `/cases` | Registers case, generates unique Case ID (`CC/YYYY/SEQ_NO`). | Clerk, Admin |
| `POST` | `/cases/check-duplicate` | Pre-filing check detecting potential duplicate filings. | Authenticated |
| `GET` | `/cases` | Multi-criteria search (`q`, `case_type`, `status`, `priority`). Role scoped. | All Roles |
| `GET` | `/cases/{case_id}` | Complete case dossier with documents, evidence, and lawyers. | All Roles |
| `PUT` | `/cases/{case_id}` | Updates general case information. | Clerk, Admin |
| `PUT` | `/cases/{case_id}/status` | Lifecycle transition (`Registered` $\rightarrow$ `Active` $\rightarrow$ `Pending` $\rightarrow$ `Disposed`). | Clerk, Judge, Admin |
| `POST` | `/cases/{case_id}/lawyers` | Assigns counsel representing Petitioner or Respondent. | Clerk, Admin |
| `POST` | `/cases/{case_id}/documents` | Multipart document upload with SHA-256 integrity and versioning. | Clerk, Lawyer, Admin |
| `GET` | `/cases/{case_id}/documents/{id}/download` | Secure file download with confidentiality guards. | Authenticated |
| `POST` | `/cases/{case_id}/evidence` | Multipart digital evidence submission (Video, Audio, Forensics). | Clerk, Lawyer, Admin |
| `PUT` | `/cases/{case_id}/evidence/{id}/verify` | Marks digital evidence as verified. | Clerk, Judge, Admin |
| `GET` | `/cases/{case_id}/history` | Chronological case history and timeline. | All Roles |

---

## 🤖 4. AI-Powered Hearing Scheduling

| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `POST` | `/hearings/recommend` | AI constraint optimization: recommends ranked conflict-free slots. | Clerk, Admin |
| `POST` | `/hearings/check-conflict` | Evaluates judge, courtroom, counsel, and calendar conflicts. | Authenticated |
| `POST` | `/hearings` | Schedules hearing; enforces double-booking prevention (HTTP 409). | Clerk, Admin |
| `GET` | `/hearings` | Lists hearings with filtering by date, courtroom, judge, and status. | All Roles |
| `GET` | `/hearings/{hearing_id}` | Returns proceeding details. | All Roles |
| `PUT` | `/hearings/{id}/reschedule` | Reschedules hearing to new slot with judicial reason. | Clerk, Admin |
| `PUT` | `/hearings/{id}/cancel` | Cancels hearing and frees courtroom and judge resources. | Clerk, Admin |
| `PUT` | `/hearings/{id}/adjourn` | Adjourns hearing with reason and optional next listing date. | Judge, Clerk, Admin |
| `PUT` | `/hearings/{id}/complete` | Concludes hearing and records judicial order/outcome. | Judge, Clerk, Admin |
| `GET` | `/hearings/courtrooms/available` | Lists active courtrooms, locations, and capacity. | Authenticated |

---

## 📜 5. Daily Cause List & Court Calendar Sync

| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `POST` | `/cause-lists/generate` | Compiles daily cause list sorted by courtroom, time, and bench. | Clerk, Admin |
| `GET` | `/cause-lists` | Lists cause lists with date range filtering. | All Roles |
| `GET` | `/cause-lists/{id}` | Detailed breakdown of scheduled proceedings on date. | All Roles |
| `PUT` | `/cause-lists/{id}/publish` | Publishes draft cause list, locking schedules and allowing public access. | Clerk, Admin |
| `GET` | `/cause-lists/{id}/pdf` | Downloads official judicial Daily Cause List PDF document. | All Roles |
| `GET` | `/cause-lists/calendar/events` | Calendar feed for interactive frontend UI calendars. | All Roles |
| `GET` | `/cause-lists/calendar/export.ics` | Standard RFC 5545 iCalendar feed for Google / Outlook Calendar sync. | All Roles |

---

## ⚖️ 6. AI-Enabled Virtual Courtroom & Transcription

| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `POST` | `/virtual-court/sessions` | Generates secure virtual hearing session link and passcode. | Clerk, Admin |
| `POST` | `/virtual-court/sessions/{id}/join` | Role-gated join access; rejects unauthorized parties (403); logs arrival. | Authorized Roles |
| `POST` | `/virtual-court/sessions/{id}/leave` | Records departure timestamp in attendance tracking log. | Authenticated |
| `POST` | `/virtual-court/sessions/{id}/start` | Judge commences online proceeding; updates hearing to `In Progress`. | Judge, Clerk, Admin |
| `POST` | `/virtual-court/sessions/{id}/recording` | Toggles official audio/video proceeding recording. | Judge, Admin |
| `POST` | `/virtual-court/sessions/{id}/end` | Concludes proceeding and triggers automated AI verbatim transcription. | Judge, Clerk, Admin |
| `GET` | `/virtual-court/sessions/{id}/attendees` | Retrieves proceeding attendance roster. | Authenticated |
| `GET` | `/virtual-court/sessions/{id}/transcript` | Retrieves AI verbatim proceeding transcript. | Authenticated |
| `GET` | `/virtual-court/sessions/{id}/transcript/pdf` | Downloads authenticated proceeding transcript PDF. | Authenticated |

---

## 📡 7. Real-Time Tracking & WebSocket Gateway

| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/tracking/courtrooms/display-board` | Public digital display board showing active bench status across all rooms. | Public |
| `GET` | `/tracking/courtrooms/{id}/display` | Single courtroom entrance display board. | Public |
| `PUT` | `/tracking/hearings/{id}/start` | Commences hearing; updates board to `IN_SESSION`; broadcasts WebSocket event. | Judge, Clerk, Admin |
| `PUT` | `/tracking/hearings/{id}/postpone` | Postpones hearing with reason; broadcasts update. | Clerk, Admin |
| `GET` | `/tracking/cases/{case_id}/timeline` | Visual milestone progression timeline with actor attribution. | All Roles |
| `WebSocket` | `/tracking/ws` | Live WebSocket stream (subscribes to `court:all`, `courtroom:{id}`, `case:{id}`). | Real-Time Clients |

---

## 🔔 8. Smart Notifications & Reminders

| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/notifications` | Retrieves authenticated user's notification drawer with unread filter. | All Roles |
| `PUT` | `/notifications/{id}/read` | Marks individual notification as read. | Authenticated |
| `PUT` | `/notifications/read-all` | Clears unread badge count by marking all notifications as read. | Authenticated |
| `POST` | `/notifications/send` | Manual court notice dispatch. | Clerk, Admin |
| `POST` | `/notifications/trigger-reminders` | Background automated 24h hearing reminder scanner. | Clerk, Admin |
| `POST` | `/notifications/retry-failed` | Retries failed or pending email/SMS deliveries. | Administrator |
| `GET` | `/notifications/stats` | Delivery analytics (Sent, Delivered, Failed, Pending, Unread). | Admin, Clerk |

---

## 🛡️ 9. Audit Trail Logging

| Method | Endpoint | Description | Role Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/audit-logs` | Immutable audit trail query with action, entity, user, and date filtering. | Administrator |
