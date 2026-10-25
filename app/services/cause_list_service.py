import os
from datetime import datetime, date, timedelta
from typing import List
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.core.config import settings
from app.models.hearing import Hearing, Courtroom
from app.models.case import CourtCase
from app.models.user import Judge
from app.schemas.cause_list import CauseListEntry
from app.services.ai_scheduler_service import AISchedulerService

class CauseListService:

    @staticmethod
    def get_cause_list_entries(db: Session, target_date: date) -> List[CauseListEntry]:
        """
        Retrieves and organizes scheduled hearings for the cause list (FR-4.4.3 CauseList.Sort).
        Sorted by courtroom, hearing time, and judge.
        """
        hearings = db.query(Hearing).filter(
            Hearing.hearing_date == target_date,
            Hearing.hearing_status != "Cancelled"
        ).order_by(
            Hearing.courtroom_id.asc(),
            Hearing.hearing_time.asc()
        ).all()

        entries: List[CauseListEntry] = []
        for h in hearings:
            c = h.case
            j = h.judge
            cr = h.courtroom

            entries.append(CauseListEntry(
                hearing_id=h.hearing_id,
                case_id=h.case_id,
                case_number=c.case_number if c else f"Case #{h.case_id}",
                case_title=c.title if c else "N/A",
                case_type=c.case_type if c else "General",
                priority=c.priority if c else "Medium",
                hearing_time=AISchedulerService.format_time_obj(h.hearing_time),
                judge_name=j.name if j else "Unassigned",
                courtroom_name=cr.courtroom_name if cr else "Unallocated",
                courtroom_location=cr.location if cr else "",
                hearing_type=h.hearing_type,
                hearing_status=h.hearing_status
            ))

        return entries

    @staticmethod
    def generate_pdf(
        cause_list_id: int,
        target_date: date,
        court_name: str,
        entries: List[CauseListEntry]
    ) -> str:
        """
        Generates a formal judicial Daily Cause List PDF document (FR-4.4.3 CauseList.Download).
        """
        out_dir = os.path.join(settings.UPLOAD_DIR, "causelists")
        os.makedirs(out_dir, exist_ok=True)
        pdf_filename = f"CauseList_{target_date.strftime('%Y%m%d')}_{cause_list_id}.pdf"
        pdf_path = os.path.join(out_dir, pdf_filename)

        # Build PDF using landscape for wide cause list table
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=landscape(letter),
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="TitleStyle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            alignment=1, # Center
            textColor=colors.HexColor("#1e293b")
        )
        subtitle_style = ParagraphStyle(
            name="SubTitleStyle",
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            alignment=1, # Center
            textColor=colors.HexColor("#475569")
        )
        cell_style = ParagraphStyle(
            name="CellStyle",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0f172a")
        )
        cell_header_style = ParagraphStyle(
            name="CellHeaderStyle",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white
        )

        story = []

        # Header
        story.append(Paragraph(court_name.upper(), title_style))
        story.append(Paragraph(f"DAILY CAUSE LIST FOR PROCEEDINGS ON: <b>{target_date.strftime('%A, %d %B %Y')}</b>", subtitle_style))
        story.append(Paragraph(f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Total Scheduled Matters: {len(entries)}", subtitle_style))
        story.append(Spacer(1, 15))

        # Table Header
        headers = [
            Paragraph("<b>Sr. No.</b>", cell_header_style),
            Paragraph("<b>Time</b>", cell_header_style),
            Paragraph("<b>Case Number & Title</b>", cell_header_style),
            Paragraph("<b>Type / Priority</b>", cell_header_style),
            Paragraph("<b>Bench / Presiding Judge</b>", cell_header_style),
            Paragraph("<b>Courtroom / Location</b>", cell_header_style),
            Paragraph("<b>Mode</b>", cell_header_style),
            Paragraph("<b>Status</b>", cell_header_style),
        ]

        table_data = [headers]

        if not entries:
            empty_row = [Paragraph("No matters scheduled for this date.", cell_style)] + [Paragraph("", cell_style)] * 7
            table_data.append(empty_row)
        else:
            for idx, e in enumerate(entries, start=1):
                case_info = f"<b>{e.case_number}</b><br/>{e.case_title}"
                type_priority = f"{e.case_type}<br/><i>[{e.priority}]</i>"
                bench_info = f"{e.judge_name}"
                courtroom_info = f"{e.courtroom_name}<br/>{e.courtroom_location}"

                row = [
                    Paragraph(str(idx), cell_style),
                    Paragraph(f"<b>{e.hearing_time}</b>", cell_style),
                    Paragraph(case_info, cell_style),
                    Paragraph(type_priority, cell_style),
                    Paragraph(bench_info, cell_style),
                    Paragraph(courtroom_info, cell_style),
                    Paragraph(e.hearing_type, cell_style),
                    Paragraph(e.hearing_status, cell_style),
                ]
                table_data.append(row)

        col_widths = [35, 45, 230, 90, 140, 120, 50, 50]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")), # Deep judicial navy
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e3a8a")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        story.append(table)
        doc.build(story)
        return pdf_path

    @staticmethod
    def generate_ics_feed(hearings: List[Hearing], court_name: str = "Court") -> str:
        """
        Generates RFC 5545 compliant iCalendar content for Google & Outlook calendar sync (FR-4.4.3 Calendar.Sync).
        """
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//NyayaSetu Judicial Management//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{court_name} Hearings",
            "X-WR-TIMEZONE:Asia/Kolkata"
        ]

        now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        for h in hearings:
            if h.hearing_status == "Cancelled":
                continue

            dt_start = datetime.combine(h.hearing_date, h.hearing_time)
            dt_end = dt_start + timedelta(minutes=45)

            dt_start_str = dt_start.strftime("%Y%m%dT%H%M%S")
            dt_end_str = dt_end.strftime("%Y%m%dT%H%M%S")
            uid = f"hearing-{h.hearing_id}-case-{h.case_id}@nyayasetu.gov.in"

            case_num = h.case.case_number if h.case else f"Case #{h.case_id}"
            case_title = h.case.title if h.case else "Court Hearing"
            summary = f"Court Hearing: {case_num} - {case_title}"

            judge_name = h.judge.name if h.judge else "Presiding Judge"
            cr_name = h.courtroom.courtroom_name if h.courtroom else "Courtroom"
            location = f"{cr_name}, {h.courtroom.location if h.courtroom else ''}"
            desc = f"Bench: {judge_name}\\nMode: {h.hearing_type}\\nStatus: {h.hearing_status}"

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_utc}",
                f"DTSTART:{dt_start_str}",
                f"DTEND:{dt_end_str}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{desc}",
                f"LOCATION:{location}",
                f"STATUS:CONFIRMED" if h.hearing_status != "Adjourned" else "STATUS:TENTATIVE",
                "END:VEVENT"
            ])

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)
