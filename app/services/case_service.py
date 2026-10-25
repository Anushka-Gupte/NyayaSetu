import os
import hashlib
import shutil
from difflib import SequenceMatcher
from datetime import datetime, date
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.models.case import CourtCase, CaseDocument, DigitalEvidence, CaseHistory, CaseLawyerAssociation
from app.models.user import User, Lawyer, Litigant
from app.schemas.case import DuplicateMatch

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
ALLOWED_EVIDENCE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".mp3", ".mp4", ".wav", ".avi", ".mov", ".zip"}

class CaseService:

    @staticmethod
    def generate_case_number(db: Session, case_type: str) -> str:
        """
        Generates a standardized judicial Case ID (FR-4.2.3 Case.Register.CaseID).
        Format: CC/{YEAR}/{SEQUENCE_NUMBER} e.g. CC/2026/00001
        """
        current_year = date.today().year
        # Count cases registered in the current year
        year_prefix = f"CC/{current_year}/%"
        cases_this_year = db.query(CourtCase).filter(CourtCase.case_number.like(year_prefix)).count()
        sequence_num = cases_this_year + 1
        return f"CC/{current_year}/{sequence_num:05d}"

    @staticmethod
    def check_duplicate_cases(
        db: Session,
        title: str,
        litigant_id: int,
        case_type: str,
        threshold: float = 0.65
    ) -> List[DuplicateMatch]:
        """
        Detects potential duplicate cases based on litigant association and title similarity.
        Fulfills FR-4.2.3 Case.Duplicate.Check.
        """
        # Query active cases for the same litigant or same case type
        candidates = db.query(CourtCase).filter(
            CourtCase.case_status.in_(["Registered", "Active", "Pending"])
        ).all()

        matches: List[DuplicateMatch] = []
        normalized_new_title = title.lower().strip()

        for c in candidates:
            # Title similarity
            ratio = SequenceMatcher(None, normalized_new_title, c.title.lower().strip()).ratio()
            
            reasons = []
            if c.litigant_id == litigant_id:
                reasons.append("Identical Litigant")
                ratio = min(1.0, ratio + 0.20) # Boost similarity score if same party

            if c.case_type.lower() == case_type.lower():
                reasons.append("Matching Case Type")

            if ratio >= threshold:
                reasons.append(f"Title Similarity ({int(ratio * 100)}%)")
                matches.append(DuplicateMatch(
                    case_id=c.case_id,
                    case_number=c.case_number,
                    title=c.title,
                    similarity_score=round(ratio, 2),
                    reason=", ".join(reasons)
                ))

        # Sort by highest similarity
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        """
        Computes SHA-256 hash for document integrity validation (NFR-5.2.2 & Documents.Integrity).
        """
        sha = hashlib.sha256()
        sha.update(content)
        return sha.hexdigest()

    @staticmethod
    def store_document(
        db: Session,
        case_id: int,
        filename: str,
        document_type: str,
        content: bytes,
        uploaded_by_id: int,
        is_confidential: bool = False
    ) -> CaseDocument:
        """
        Securely stores case document with SHA-256 hash and version control.
        """
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise ValueError(f"File format '{ext}' is not supported. Permissible formats: {', '.join(ALLOWED_DOCUMENT_EXTENSIONS)}")

        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(f"File exceeds maximum permissible size of {settings.MAX_FILE_SIZE_MB}MB.")

        file_hash = CaseService.compute_sha256(content)

        # Check existing version for this document in this case
        existing_doc = db.query(CaseDocument).filter(
            CaseDocument.case_id == case_id,
            CaseDocument.document_name == filename
        ).order_by(CaseDocument.version.desc()).first()

        new_version = (existing_doc.version + 1) if existing_doc else 1

        # Target directory: uploads/cases/{case_id}/documents/
        case_doc_dir = os.path.join(settings.UPLOAD_DIR, "cases", str(case_id), "documents")
        os.makedirs(case_doc_dir, exist_ok=True)

        storage_filename = f"v{new_version}_{filename}"
        target_path = os.path.join(case_doc_dir, storage_filename)

        with open(target_path, "wb") as f:
            f.write(content)

        doc_record = CaseDocument(
            case_id=case_id,
            document_name=filename,
            document_type=document_type,
            file_path=target_path,
            file_size_bytes=len(content),
            file_hash=file_hash,
            version=new_version,
            is_confidential=is_confidential,
            upload_date=datetime.utcnow(),
            uploaded_by_id=uploaded_by_id
        )
        db.add(doc_record)
        return doc_record

    @staticmethod
    def store_evidence(
        db: Session,
        case_id: int,
        filename: str,
        evidence_type: str,
        content: bytes,
        submitted_by_id: int,
        description: Optional[str] = None
    ) -> DigitalEvidence:
        """
        Securely stores digital evidence with SHA-256 forensic validation.
        """
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EVIDENCE_EXTENSIONS:
            raise ValueError(f"Evidence file format '{ext}' not supported.")

        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(f"Evidence file exceeds {settings.MAX_FILE_SIZE_MB}MB.")

        file_hash = CaseService.compute_sha256(content)

        case_evidence_dir = os.path.join(settings.UPLOAD_DIR, "cases", str(case_id), "evidence")
        os.makedirs(case_evidence_dir, exist_ok=True)

        timestamp = int(datetime.utcnow().timestamp())
        storage_filename = f"ev_{timestamp}_{filename}"
        target_path = os.path.join(case_evidence_dir, storage_filename)

        with open(target_path, "wb") as f:
            f.write(content)

        evidence_record = DigitalEvidence(
            case_id=case_id,
            evidence_type=evidence_type,
            description=description,
            file_path=target_path,
            file_hash=file_hash,
            submission_date=datetime.utcnow(),
            submitted_by_id=submitted_by_id,
            is_verified=False
        )
        db.add(evidence_record)
        return evidence_record
