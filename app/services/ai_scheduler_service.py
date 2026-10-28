from datetime import date, time, datetime, timedelta
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.hearing import Hearing, Courtroom
from app.models.case import CourtCase, CaseLawyerAssociation
from app.models.user import Judge
from app.schemas.hearing import HearingSlotRecommendation

COURT_SLOTS = ["10:30", "11:30", "12:30", "14:00", "15:00", "16:00"]

class AISchedulerService:

    @staticmethod
    def parse_time_str(time_str: str) -> time:
        parts = time_str.split(":")
        return time(hour=int(parts[0]), minute=int(parts[1]))

    @staticmethod
    def format_time_obj(t: time) -> str:
        return t.strftime("%H:%M")

    @staticmethod
    def detect_conflicts(
        db: Session,
        case_id: int,
        judge_id: int,
        courtroom_id: int,
        hearing_date: date,
        hearing_time_str: str,
        exclude_hearing_id: Optional[int] = None
    ) -> List[str]:
        """
        Detects scheduling conflicts involving judges, courtrooms, hearing times,
        advocates, or duplicate case schedules (FR-4.3.3 Scheduling.Conflict.Detect).
        """
        conflicts = []
        parsed_time = AISchedulerService.parse_time_str(hearing_time_str)

        # 1. Non-working day checks (Saturdays and Sundays)
        if hearing_date.weekday() in (5, 6):
            conflicts.append(f"Court is closed on {hearing_date.strftime('%A')} ({hearing_date}).")

        # 2. Check if date is in the past
        if hearing_date < date.today():
            conflicts.append("Cannot schedule hearings in the past.")

        # 3. Courtroom conflict
        courtroom_query = db.query(Hearing).filter(
            Hearing.courtroom_id == courtroom_id,
            Hearing.hearing_date == hearing_date,
            Hearing.hearing_time == parsed_time,
            Hearing.hearing_status.in_(["Scheduled", "In Progress"])
        )
        if exclude_hearing_id:
            courtroom_query = courtroom_query.filter(Hearing.hearing_id != exclude_hearing_id)

        existing_courtroom_hearing = courtroom_query.first()
        if existing_courtroom_hearing:
            courtroom = db.query(Courtroom).filter(Courtroom.courtroom_id == courtroom_id).first()
            c_name = courtroom.courtroom_name if courtroom else f"ID {courtroom_id}"
            conflicts.append(f"Courtroom '{c_name}' is already booked for Case #{existing_courtroom_hearing.case_id} at {hearing_time_str}.")

        # 4. Judge conflict
        judge_query = db.query(Hearing).filter(
            Hearing.judge_id == judge_id,
            Hearing.hearing_date == hearing_date,
            Hearing.hearing_time == parsed_time,
            Hearing.hearing_status.in_(["Scheduled", "In Progress"])
        )
        if exclude_hearing_id:
            judge_query = judge_query.filter(Hearing.hearing_id != exclude_hearing_id)

        existing_judge_hearing = judge_query.first()
        if existing_judge_hearing:
            judge = db.query(Judge).filter(Judge.judge_id == judge_id).first()
            j_name = judge.name if judge else f"Judge #{judge_id}"
            conflicts.append(f"Honorable Judge '{j_name}' is already presiding over Case #{existing_judge_hearing.case_id} at {hearing_time_str}.")

        # 5. Advocate conflict (Check if case lawyers are booked elsewhere)
        lawyer_assocs = db.query(CaseLawyerAssociation).filter(CaseLawyerAssociation.case_id == case_id).all()
        lawyer_ids = [la.lawyer_id for la in lawyer_assocs]

        if lawyer_ids:
            conflicting_lawyer_cases = db.query(Hearing).join(
                CaseLawyerAssociation, Hearing.case_id == CaseLawyerAssociation.case_id
            ).filter(
                CaseLawyerAssociation.lawyer_id.in_(lawyer_ids),
                Hearing.hearing_date == hearing_date,
                Hearing.hearing_time == parsed_time,
                Hearing.case_id != case_id,
                Hearing.hearing_status.in_(["Scheduled", "In Progress"])
            ).first()

            if conflicting_lawyer_cases:
                conflicts.append(f"Assigned advocate has a conflicting hearing in Case #{conflicting_lawyer_cases.case_id} at {hearing_time_str}.")

        return conflicts

    @staticmethod
    def generate_recommendations(
        db: Session,
        case_id: int,
        days_ahead_start: Optional[int] = None,
        days_ahead_end: Optional[int] = None,
        max_recommendations: int = 5
    ) -> List[HearingSlotRecommendation]:
        """
        AI-Powered constraint satisfaction scheduler (FR-4.3.3 Scheduling.AI.Recommend).
        Analyzes judge specialization, workload, courtroom availability, case priority,
        and court calendars.
        """
        case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
        if not case:
            return []

        # Determine scheduling window based on priority
        priority = (case.priority or "Medium").capitalize()
        if days_ahead_start is None or days_ahead_end is None:
            if priority == "Urgent":
                start_days = 1
                end_days = 3
            elif priority == "High":
                start_days = 2
                end_days = 5
            elif priority == "Low":
                start_days = 7
                end_days = 16
            else: # Medium
                start_days = 3
                end_days = 10
        else:
            start_days = days_ahead_start
            end_days = days_ahead_end

        # Retrieve active judges and courtrooms
        judges = db.query(Judge).filter(Judge.is_active == True).all()
        courtrooms = db.query(Courtroom).filter(Courtroom.availability == True).all()

        if not judges or not courtrooms:
            return []

        recommendations: List[HearingSlotRecommendation] = []
        today = date.today()

        # Iterate over calendar days within window
        for offset in range(start_days, end_days + 1):
            candidate_date = today + timedelta(days=offset)
            # Skip Saturday and Sunday
            if candidate_date.weekday() in (5, 6):
                continue

            for slot_time_str in COURT_SLOTS:
                if len(recommendations) >= max_recommendations:
                    break

                # 0. Check if assigned advocate(s) are already booked in another hearing at this slot
                lawyer_assocs = db.query(CaseLawyerAssociation).filter(CaseLawyerAssociation.case_id == case_id).all()
                lawyer_ids = [la.lawyer_id for la in lawyer_assocs]
                if lawyer_ids:
                    slot_parsed_time = AISchedulerService.parse_time_str(slot_time_str)
                    conflicting_lawyer = db.query(Hearing).join(
                        CaseLawyerAssociation, Hearing.case_id == CaseLawyerAssociation.case_id
                    ).filter(
                        CaseLawyerAssociation.lawyer_id.in_(lawyer_ids),
                        Hearing.hearing_date == candidate_date,
                        Hearing.hearing_time == slot_parsed_time,
                        Hearing.case_id != case_id,
                        Hearing.hearing_status.in_(["Scheduled", "In Progress"])
                    ).first()
                    if conflicting_lawyer:
                        # Skip this time slot entirely because the advocate has a hearing elsewhere
                        continue

                # Score each (judge, courtroom) pair for this slot
                for judge in judges:
                    # Check judge conflicts
                    j_conflicts = AISchedulerService.detect_conflicts(
                        db=db,
                        case_id=case_id,
                        judge_id=judge.judge_id,
                        courtroom_id=courtrooms[0].courtroom_id, # Temporary probe
                        hearing_date=candidate_date,
                        hearing_time_str=slot_time_str
                    )
                    # If judge or advocate has conflict, skip
                    if any("Honorable Judge" in c or "Assigned advocate" in c for c in j_conflicts):
                        continue

                    # Count judge's total hearings on this day (workload balancing)
                    day_parsed_time = AISchedulerService.parse_time_str(slot_time_str)
                    daily_hearings_count = db.query(Hearing).filter(
                        Hearing.judge_id == judge.judge_id,
                        Hearing.hearing_date == candidate_date,
                        Hearing.hearing_status.in_(["Scheduled", "In Progress"])
                    ).count()

                    if daily_hearings_count >= 6: # Max judge daily capacity
                        continue

                    # Find an available courtroom
                    selected_courtroom = None
                    for c_room in courtrooms:
                        cr_conflict = db.query(Hearing).filter(
                            Hearing.courtroom_id == c_room.courtroom_id,
                            Hearing.hearing_date == candidate_date,
                            Hearing.hearing_time == day_parsed_time,
                            Hearing.hearing_status.in_(["Scheduled", "In Progress"])
                        ).first()
                        if not cr_conflict:
                            selected_courtroom = c_room
                            break

                    if not selected_courtroom:
                        continue

                    # Calculate recommendation confidence score & explainability reasons
                    score = 0.70
                    reasons = ["Conflict-free judicial slot verified"]

                    # Specialization match bonus
                    case_type_lower = (case.case_type or "").lower()
                    judge_spec_lower = (judge.specialization or "").lower()
                    if ("criminal" in case_type_lower and "criminal" in judge_spec_lower) or \
                       ("civil" in case_type_lower and "civil" in judge_spec_lower) or \
                       ("commercial" in case_type_lower and "commercial" in judge_spec_lower):
                        score += 0.20
                        reasons.append(f"Judicial specialization match: {judge.specialization}")

                    # Workload balancing bonus
                    if daily_hearings_count <= 2:
                        score += 0.08
                        reasons.append(f"Low judge caseload for day ({daily_hearings_count} hearings)")
                    else:
                        reasons.append(f"Moderate judge caseload ({daily_hearings_count} hearings)")

                    # Priority alignment note
                    reasons.append(f"Optimal for '{priority}' priority (Day +{offset})")

                    score = min(0.99, round(score, 2))

                    recommendations.append(HearingSlotRecommendation(
                        hearing_date=candidate_date,
                        hearing_time=slot_time_str,
                        judge_id=judge.judge_id,
                        judge_name=judge.name,
                        judge_specialization=judge.specialization,
                        courtroom_id=selected_courtroom.courtroom_id,
                        courtroom_name=selected_courtroom.courtroom_name,
                        courtroom_location=selected_courtroom.location,
                        confidence_score=score,
                        reasons=reasons
                    ))

                    if len(recommendations) >= max_recommendations:
                        break

            if len(recommendations) >= max_recommendations:
                break

        # Sort recommendations by confidence score descending
        recommendations.sort(key=lambda r: r.confidence_score, reverse=True)
        return recommendations
