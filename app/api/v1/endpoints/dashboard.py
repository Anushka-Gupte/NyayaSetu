from datetime import date, datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.user import User, UserRole, Judge, Lawyer, Litigant
from app.models.case import CourtCase, CaseDocument, DigitalEvidence, CaseLawyerAssociation
from app.models.hearing import Hearing, OnlineHearing, Courtroom
from app.models.cause_list import CauseList
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.api.deps import get_current_active_user

router = APIRouter()

@router.get("/overview", summary="Role-Based Dashboard Overview")
def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Returns role-tailored dashboard metrics and summaries corresponding to SRS Section 3.1.
    """
    today = date.today()
    role = current_user.role

    # Base common data
    unread_notifications = db.query(Notification).filter(
        Notification.recipient_id == current_user.user_id,
        Notification.is_read == False
    ).count()

    base_response = {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "role": role.value,
        "unread_notifications": unread_notifications,
        "server_date": today.isoformat()
    }

    if role == UserRole.ADMINISTRATOR:
        total_users = db.query(User).count()
        total_cases = db.query(CourtCase).count()
        active_cases = db.query(CourtCase).filter(CourtCase.case_status == "Active").count()
        disposed_cases = db.query(CourtCase).filter(CourtCase.case_status == "Disposed").count()
        total_courtrooms = db.query(Courtroom).count()
        recent_audits = db.query(AuditLog).order_by(AuditLog.date_time.desc()).limit(5).all()

        base_response["metrics"] = {
            "total_users": total_users,
            "total_cases": total_cases,
            "active_cases": active_cases,
            "disposed_cases": disposed_cases,
            "total_courtrooms": total_courtrooms,
            "recent_audit_activities": [
                {
                    "action": a.action,
                    "entity_type": a.entity_type,
                    "date_time": a.date_time.isoformat(),
                    "details": a.details
                }
                for a in recent_audits
            ]
        }

    elif role == UserRole.COURT_CLERK:
        cases_registered_today = db.query(CourtCase).filter(CourtCase.filing_date == today).count()
        total_cases = db.query(CourtCase).count()
        hearings_today = db.query(Hearing).filter(Hearing.hearing_date == today).count()
        pending_cause_lists = db.query(CauseList).filter(CauseList.is_published == False).count()

        base_response["metrics"] = {
            "cases_registered_today": cases_registered_today,
            "total_cases": total_cases,
            "hearings_today": hearings_today,
            "pending_cause_lists": pending_cause_lists
        }

    elif role == UserRole.JUDGE:
        assigned_case_ids = [row[0] for row in db.query(Hearing.case_id).filter(Hearing.judge_id == current_user.user_id).distinct().all()]
        today_hearings = db.query(Hearing).filter(
            Hearing.judge_id == current_user.user_id,
            Hearing.hearing_date == today
        ).all()
        pending_judgments = db.query(CourtCase).filter(
            CourtCase.case_id.in_(assigned_case_ids) if assigned_case_ids else False,
            CourtCase.case_status == "Pending"
        ).count()
        judge_record = db.query(Judge).filter(Judge.judge_id == current_user.user_id).first()

        base_response["metrics"] = {
            "assigned_cases_count": len(assigned_case_ids),
            "today_hearings_count": len(today_hearings),
            "pending_judgments": pending_judgments,
            "judge_availability": judge_record.availability if judge_record else None,
            "today_schedule": [
                {
                    "hearing_id": h.hearing_id,
                    "case_id": h.case_id,
                    "time": h.hearing_time.isoformat(),
                    "status": h.hearing_status,
                    "type": h.hearing_type
                }
                for h in today_hearings
            ]
        }

    elif role == UserRole.LAWYER:
        assigned_cases = db.query(CaseLawyerAssociation).filter(
            CaseLawyerAssociation.lawyer_id == current_user.user_id
        ).all()
        case_ids = [a.case_id for a in assigned_cases]
        assigned_documents = db.query(CaseDocument).filter(CaseDocument.case_id.in_(case_ids)).count() if case_ids else 0
        active_assigned_cases = db.query(CourtCase).filter(
            CourtCase.case_id.in_(case_ids),
            CourtCase.case_status == "Active"
        ).count() if case_ids else 0
        
        upcoming_hearings = db.query(Hearing).filter(
            Hearing.case_id.in_(case_ids) if case_ids else False,
            Hearing.hearing_date >= today
        ).order_by(Hearing.hearing_date.asc()).limit(5).all()

        base_response["metrics"] = {
            "total_assigned_cases": len(assigned_cases),
            "upcoming_hearings_count": len(upcoming_hearings),
            "active_assigned_cases_count": active_assigned_cases,
            "assigned_case_documents_count": assigned_documents,
            "upcoming_hearings": [
                {
                    "hearing_id": h.hearing_id,
                    "case_id": h.case_id,
                    "date": h.hearing_date.isoformat(),
                    "time": h.hearing_time.isoformat(),
                    "type": h.hearing_type,
                    "status": h.hearing_status
                }
                for h in upcoming_hearings
            ]
        }

    elif role == UserRole.LITIGANT:
        litigant_cases = db.query(CourtCase).filter(
            CourtCase.litigant_id == current_user.user_id
        ).all()
        case_ids = [c.case_id for c in litigant_cases]
        upcoming_hearings = db.query(Hearing).filter(
            Hearing.case_id.in_(case_ids) if case_ids else False,
            Hearing.hearing_date >= today,
            Hearing.hearing_status.notin_(["Cancelled", "Completed", "Postponed"])
        ).order_by(Hearing.hearing_date.asc()).limit(3).all()
        case_documents_count = db.query(CaseDocument).filter(CaseDocument.case_id.in_(case_ids)).count() if case_ids else 0
        assigned_advocates_count = db.query(CaseLawyerAssociation).filter(
            CaseLawyerAssociation.case_id.in_(case_ids)
        ).count() if case_ids else 0

        base_response["metrics"] = {
            "my_cases_count": len(litigant_cases),
            "upcoming_hearings_count": len(upcoming_hearings),
            "my_case_documents_count": case_documents_count,
            "assigned_advocates_count": assigned_advocates_count,
            "my_cases": [
                {
                    "case_id": c.case_id,
                    "case_number": c.case_number,
                    "title": c.title,
                    "status": c.case_status,
                    "filing_date": c.filing_date.isoformat()
                }
                for c in litigant_cases
            ],
            "upcoming_hearings": [
                {
                    "hearing_id": h.hearing_id,
                    "case_id": h.case_id,
                    "date": h.hearing_date.isoformat(),
                    "time": h.hearing_time.isoformat(),
                    "type": h.hearing_type
                }
                for h in upcoming_hearings
            ]
        }

    return base_response
