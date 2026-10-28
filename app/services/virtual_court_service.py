import os
import uuid
import secrets
from datetime import datetime, date
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.core.config import settings
from app.models.hearing import Hearing, OnlineHearing, Transcript, HearingAttendance
from app.models.case import CourtCase, CaseLawyerAssociation
from app.models.user import User, UserRole, Judge
from app.core.security import create_access_token

class VirtualCourtService:

    @staticmethod
    def generate_room_details(hearing_id: int, case_number: str) -> Tuple[str, str, str]:
        """
        Generates secure virtual hearing room parameters (FR-4.6.3 VirtualHearing.Link.Generate).
        """
        clean_num = case_number.replace("/", "_").replace("-", "_")
        room_token = secrets.token_urlsafe(24)
        room_name = f"NyayaSetu_{clean_num}_{room_token}"
        meeting_link = f"{settings.VIRTUAL_COURT_BASE_URL}/{room_name}"
        passcode = secrets.token_hex(3).upper() # 6-char alphanumeric passcode
        return room_name, meeting_link, passcode

    @staticmethod
    def verify_participant_access(db: Session, user: User, hearing: Hearing) -> bool:
        """
        Enforces strict role-gated access control to virtual court hearings (FR-4.6.3 VirtualHearing.Access.Control & BR-5.9).
        """
        # Admins and Court Clerks have judicial administrative access
        if user.role in (UserRole.ADMINISTRATOR, UserRole.COURT_CLERK):
            return True

        # Presiding Judge
        if user.role == UserRole.JUDGE:
            return hearing.judge_id == user.user_id

        # Case Litigant
        if user.role == UserRole.LITIGANT:
            case = hearing.case
            return case is not None and case.litigant_id == user.user_id

        # Case Lawyer
        if user.role == UserRole.LAWYER:
            assigned = db.query(CaseLawyerAssociation).filter(
                CaseLawyerAssociation.case_id == hearing.case_id,
                CaseLawyerAssociation.lawyer_id == user.user_id
            ).first()
            return assigned is not None

        return False

    @staticmethod
    def record_attendance_join(
        db: Session,
        online_hearing_id: int,
        user: User,
        ip_address: Optional[str] = None
    ) -> HearingAttendance:
        """
        Automatically logs participant arrival (FR-4.6.3 VirtualHearing.Attendance.Track).
        """
        # Close any lingering previous unclosed sessions for this user in this room
        open_session = db.query(HearingAttendance).filter(
            HearingAttendance.online_hearing_id == online_hearing_id,
            HearingAttendance.user_id == user.user_id,
            HearingAttendance.left_at == None
        ).first()

        if open_session:
            return open_session

        record = HearingAttendance(
            online_hearing_id=online_hearing_id,
            user_id=user.user_id,
            user_name=user.name,
            role=user.role.value,
            joined_at=datetime.utcnow(),
            ip_address=ip_address
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def record_attendance_leave(
        db: Session,
        online_hearing_id: int,
        user_id: int
    ) -> Optional[HearingAttendance]:
        """
        Records participant departure when concluding or leaving session.
        """
        record = db.query(HearingAttendance).filter(
            HearingAttendance.online_hearing_id == online_hearing_id,
            HearingAttendance.user_id == user_id,
            HearingAttendance.left_at == None
        ).order_by(HearingAttendance.joined_at.desc()).first()

        if record:
            record.left_at = datetime.utcnow()
            db.commit()
            db.refresh(record)
        return record

    @staticmethod
    def generate_session_record(
        db: Session,
        online_hearing: OnlineHearing,
        notes: Optional[str] = None
    ) -> Transcript:
        """Store a clearly labeled hearing record until a speech service is configured."""
        hearing = online_hearing.hearing
        case = hearing.case if hearing else None
        judge = hearing.judge if hearing else None

        # Do not fabricate spoken dialogue when no audio transcription service is configured.
        start_t = online_hearing.start_time or datetime.utcnow()
        case_num = case.case_number if case else "Case details unavailable"
        case_title = case.title if case else "Case details unavailable"
        judge_name = judge.name if judge else "Judge details unavailable"

        # Compile attendees list
        attendees = db.query(HearingAttendance).filter(
            HearingAttendance.online_hearing_id == online_hearing.online_hearing_id
        ).all()
        roster_str = ", ".join([f"{a.user_name} ({a.role})" for a in attendees]) if attendees else "Attendance details unavailable."

        transcript_body = (
            f"=== HEARING SESSION RECORD ===\n"
            f"TRANSCRIPTION STATUS: Unavailable. No speech-to-text provider is configured.\n"
            f"CASE NUMBER: {case_num}\n"
            f"TITLE: {case_title}\n"
            f"BENCH: {judge_name}\n"
            f"DATE OF PROCEEDING: {start_t.strftime('%Y-%m-%d')} UTC\n"
            f"SESSION COMMENCED: {start_t.strftime('%H:%M:%S')} UTC\n"
            f"RECORDED PARTICIPANTS: {roster_str}\n"
            f"========================================================\n"
        )

        if notes:
            transcript_body += f"\nBENCH NOTES (not a verbatim transcript):\n{notes}\n"

        existing_transcript = db.query(Transcript).filter(
            Transcript.online_hearing_id == online_hearing.online_hearing_id
        ).first()

        if existing_transcript:
            existing_transcript.transcript_text = transcript_body
            existing_transcript.generated_date = datetime.utcnow()
            db.commit()
            db.refresh(existing_transcript)
            return existing_transcript

        new_transcript = Transcript(
            online_hearing_id=online_hearing.online_hearing_id,
            transcript_text=transcript_body,
            generated_date=datetime.utcnow()
        )
        db.add(new_transcript)
        db.commit()
        db.refresh(new_transcript)
        return new_transcript

    @staticmethod
    def generate_transcript_pdf(
        transcript: Transcript,
        online_hearing: OnlineHearing
    ) -> str:
        """
        Exports official transcript to PDF format.
        """
        out_dir = os.path.join(settings.UPLOAD_DIR, "transcripts")
        os.makedirs(out_dir, exist_ok=True)
        pdf_path = os.path.join(out_dir, f"Transcript_Hearing_{online_hearing.hearing_id}.pdf")

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="TranscriptTitle",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            alignment=1,
            textColor=colors.HexColor("#0f172a")
        )
        body_style = ParagraphStyle(
            name="TranscriptBody",
            fontName="Courier",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1e293b")
        )

        story = []
        story.append(Paragraph("<b>DEPARTMENT OF JUSTICE - COURT RECORD OF PROCEEDINGS</b>", title_style))
        story.append(Paragraph("HEARING SESSION RECORD", title_style))
        story.append(Spacer(1, 15))

        # Format transcript lines
        for block in transcript.transcript_text.split("\n\n"):
            clean_block = block.replace("\n", "<br/>")
            story.append(Paragraph(clean_block, body_style))
            story.append(Spacer(1, 6))

        doc.build(story)
        return pdf_path
