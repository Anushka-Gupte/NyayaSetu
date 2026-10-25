import os
from typing import List, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.user import User, UserRole, Lawyer, Litigant
from app.models.case import CourtCase, CaseDocument, DigitalEvidence, CaseHistory, CaseLawyerAssociation
from app.models.hearing import Hearing
from app.schemas.case import (
    CaseCreate,
    CaseUpdate,
    CaseStatusUpdate,
    CourtCaseResponse,
    CourtCaseDetailResponse,
    CaseLawyerResponse,
    CaseHistoryResponse,
    CaseDocumentResponse,
    DigitalEvidenceResponse,
    DuplicateCheckResponse,
    LawyerAssignment
)
from app.api.deps import get_current_active_user, require_roles
from app.services.case_service import CaseService
from app.services.audit_service import AuditService

router = APIRouter()

def build_case_summary(case: CourtCase) -> CourtCaseResponse:
    lawyers_list = []
    if case.lawyers:
        for assoc in case.lawyers:
            lawyer_user = assoc.lawyer
            lawyers_list.append(CaseLawyerResponse(
                lawyer_id=assoc.lawyer_id,
                name=lawyer_user.name if lawyer_user else "Unknown Lawyer",
                email=lawyer_user.email if lawyer_user else "",
                bar_registration_no=lawyer_user.bar_registration_no if lawyer_user else "",
                representing_party=assoc.representing_party
            ))

    litigant_name = case.litigant.name if case.litigant else None

    return CourtCaseResponse(
        case_id=case.case_id,
        case_number=case.case_number,
        title=case.title,
        case_type=case.case_type,
        filing_date=case.filing_date,
        case_status=case.case_status,
        priority=case.priority,
        description=case.description,
        clerk_id=case.clerk_id,
        litigant_id=case.litigant_id,
        litigant_name=litigant_name,
        lawyers=lawyers_list,
        documents_count=len(case.documents) if case.documents else 0,
        evidence_count=len(case.evidence) if case.evidence else 0,
        hearings_count=len(case.hearings) if case.hearings else 0
    )


@router.post("/check-duplicate", response_model=DuplicateCheckResponse, summary="Pre-check Potential Duplicate Cases")
def check_duplicate(
    title: str = Query(..., min_length=3),
    case_type: str = Query(...),
    litigant_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Checks for potential duplicate registrations before filing (FR-4.2.3 Case.Duplicate.Check).
    """
    matches = CaseService.check_duplicate_cases(
        db=db, title=title, litigant_id=litigant_id, case_type=case_type
    )
    return DuplicateCheckResponse(
        is_potential_duplicate=len(matches) > 0,
        matches=matches
    )


@router.post("", response_model=CourtCaseResponse, status_code=status.HTTP_201_CREATED, summary="Register New Court Case")
def register_case(
    case_in: CaseCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Registers a new judicial case, generates unique Case ID, and records initial history (FR-4.2.3).
    """
    client_ip = request.client.host if (request and request.client) else None

    # Validate litigant exists
    litigant = db.query(Litigant).filter(Litigant.litigant_id == case_in.litigant_id).first()
    if not litigant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Litigant ID {case_in.litigant_id} not found")

    # Generate unique Case ID
    case_number = CaseService.generate_case_number(db, case_in.case_type)

    new_case = CourtCase(
        case_number=case_number,
        title=case_in.title,
        case_type=case_in.case_type,
        filing_date=date.today(),
        case_status="Registered",
        priority=case_in.priority,
        description=case_in.description,
        clerk_id=current_user.user_id,
        litigant_id=case_in.litigant_id
    )
    db.add(new_case)
    db.flush() # Flush to populate case_id for associations

    # Associate lawyers if provided
    if case_in.lawyer_assignments:
        for la in case_in.lawyer_assignments:
            lawyer = db.query(Lawyer).filter(Lawyer.lawyer_id == la.lawyer_id).first()
            if lawyer:
                assoc = CaseLawyerAssociation(
                    case_id=new_case.case_id,
                    lawyer_id=la.lawyer_id,
                    representing_party=la.representing_party
                )
                db.add(assoc)

    # Initial Case History entry
    history_entry = CaseHistory(
        case_id=new_case.case_id,
        event="CASE_REGISTERED",
        date_time=datetime.utcnow(),
        description=f"Case filed with priority '{new_case.priority}'. Litigant: {litigant.name}.",
        user_id=current_user.user_id
    )
    db.add(history_entry)

    db.commit()
    db.refresh(new_case)

    # Audit Trail
    AuditService.log(
        db=db,
        action="CASE_REGISTERED",
        entity_type="CourtCase",
        entity_id=str(new_case.case_id),
        user_id=current_user.user_id,
        details=f"Case {new_case.case_number} registered by {current_user.username}",
        ip_address=client_ip
    )

    return build_case_summary(new_case)


@router.get("", response_model=List[CourtCaseResponse], summary="Search and Filter Cases")
def search_cases(
    q: Optional[str] = Query(None, description="Search term for case number, title, or party"),
    case_type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Multi-criteria case search and filter with role-based scoping (FR-4.2.3 Case.Search).
    """
    query = db.query(CourtCase)

    # Role-based scoping
    if current_user.role == UserRole.LITIGANT:
        query = query.filter(CourtCase.litigant_id == current_user.user_id)
    elif current_user.role == UserRole.LAWYER:
        assigned_case_ids = db.query(CaseLawyerAssociation.case_id).filter(
            CaseLawyerAssociation.lawyer_id == current_user.user_id
        ).subquery()
        query = query.filter(CourtCase.case_id.in_(assigned_case_ids))

    # Search filters
    if q:
        search_filter = or_(
            CourtCase.case_number.ilike(f"%{q}%"),
            CourtCase.title.ilike(f"%{q}%"),
            CourtCase.description.ilike(f"%{q}%")
        )
        query = query.filter(search_filter)

    if case_type:
        query = query.filter(CourtCase.case_type == case_type)
    if status:
        query = query.filter(CourtCase.case_status == status)
    if priority:
        query = query.filter(CourtCase.priority == priority)

    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    cases = query.order_by(CourtCase.case_id.desc()).offset(offset_val).limit(limit_val).all()
    return [build_case_summary(c) for c in cases]


@router.get("/{case_id}", response_model=CourtCaseDetailResponse, summary="Get Case Details with Documents and History")
def get_case_details(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns complete case dossier, including attached documents, evidence, and historical timeline.
    """
    case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    # Access control
    if current_user.role == UserRole.LITIGANT and case.litigant_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this case record")

    summary = build_case_summary(case)

    # Filter confidential documents for litigants
    documents = []
    for d in case.documents:
        if d.is_confidential and current_user.role == UserRole.LITIGANT:
            continue
        documents.append(CaseDocumentResponse.model_validate(d))

    evidence = [DigitalEvidenceResponse.model_validate(e) for e in case.evidence]
    history = [CaseHistoryResponse.model_validate(h) for h in sorted(case.history, key=lambda x: x.date_time, reverse=True)]

    return CourtCaseDetailResponse(
        **summary.model_dump(),
        documents=documents,
        evidence=evidence,
        history=history
    )


@router.put("/{case_id}", response_model=CourtCaseResponse, summary="Update Case Information")
def update_case(
    case_id: int,
    case_update: CaseUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Updates general case information (FR-4.2.3 Case.Update).
    """
    client_ip = request.client.host if (request and request.client) else None
    case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if case_update.title:
        case.title = case_update.title
    if case_update.case_type:
        case.case_type = case_update.case_type
    if case_update.priority:
        case.priority = case_update.priority
    if case_update.description is not None:
        case.description = case_update.description

    # Log history
    history_entry = CaseHistory(
        case_id=case.case_id,
        event="CASE_MODIFIED",
        date_time=datetime.utcnow(),
        description=f"Case information updated by {current_user.name}.",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(case)

    AuditService.log(
        db=db,
        action="CASE_UPDATED",
        entity_type="CourtCase",
        entity_id=str(case.case_id),
        user_id=current_user.user_id,
        details=f"Case {case.case_number} details updated",
        ip_address=client_ip
    )

    return build_case_summary(case)


@router.put("/{case_id}/status", response_model=CourtCaseResponse, summary="Update Case Lifecycle Status")
def update_case_status(
    case_id: int,
    status_in: CaseStatusUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.JUDGE, UserRole.ADMINISTRATOR))
):
    """
    Updates the judicial case lifecycle state (Registered -> Active -> Pending -> Disposed).
    """
    client_ip = request.client.host if (request and request.client) else None
    case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    valid_statuses = ["Registered", "Active", "Pending", "Disposed"]
    if status_in.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{status_in.status}'. Allowed: {', '.join(valid_statuses)}"
        )

    previous_status = case.case_status
    case.case_status = status_in.status

    reason_desc = f" Status changed from '{previous_status}' to '{status_in.status}'."
    if status_in.reason_or_outcome:
        reason_desc += f" Note: {status_in.reason_or_outcome}"

    history_entry = CaseHistory(
        case_id=case.case_id,
        event="STATUS_CHANGED",
        date_time=datetime.utcnow(),
        description=reason_desc,
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(case)

    AuditService.log(
        db=db,
        action="CASE_STATUS_CHANGED",
        entity_type="CourtCase",
        entity_id=str(case.case_id),
        user_id=current_user.user_id,
        details=f"Case {case.case_number} status set to {status_in.status}",
        ip_address=client_ip
    )

    return build_case_summary(case)


@router.post("/{case_id}/lawyers", response_model=CourtCaseResponse, summary="Assign Lawyer to Case")
def assign_lawyer(
    case_id: int,
    assignment: LawyerAssignment,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.ADMINISTRATOR))
):
    """
    Assigns an authorized lawyer to represent a party in the case.
    """
    client_ip = request.client.host if (request and request.client) else None
    case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    lawyer = db.query(Lawyer).filter(Lawyer.lawyer_id == assignment.lawyer_id).first()
    if not lawyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer not found")

    # Check if already assigned
    existing = db.query(CaseLawyerAssociation).filter(
        CaseLawyerAssociation.case_id == case_id,
        CaseLawyerAssociation.lawyer_id == assignment.lawyer_id
    ).first()

    if existing:
        existing.representing_party = assignment.representing_party
    else:
        assoc = CaseLawyerAssociation(
            case_id=case_id,
            lawyer_id=assignment.lawyer_id,
            representing_party=assignment.representing_party
        )
        db.add(assoc)

    history_entry = CaseHistory(
        case_id=case.case_id,
        event="LAWYER_ASSIGNED",
        date_time=datetime.utcnow(),
        description=f"{lawyer.name} assigned as counsel for {assignment.representing_party}.",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(case)

    AuditService.log(
        db=db,
        action="LAWYER_ASSIGNED",
        entity_type="CourtCase",
        entity_id=str(case.case_id),
        user_id=current_user.user_id,
        details=f"Advocate {lawyer.name} assigned to Case {case.case_number}",
        ip_address=client_ip
    )

    return build_case_summary(case)


# ==============================================================================
# Document & Digital Evidence Endpoints (SRS Section 4.5)
# ==============================================================================

@router.post("/{case_id}/documents", response_model=CaseDocumentResponse, status_code=status.HTTP_201_CREATED, summary="Upload Case Document")
def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    document_type: str = Form("Petition"),
    is_confidential: bool = Form(False),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.LAWYER, UserRole.ADMINISTRATOR))
):
    """
    Uploads a legal document with SHA-256 integrity validation and automatic version control (FR-4.5.3).
    """
    client_ip = request.client.host if (request and request.client) else None
    case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    content = file.file.read()

    try:
        doc = CaseService.store_document(
            db=db,
            case_id=case_id,
            filename=file.filename,
            document_type=document_type,
            content=content,
            uploaded_by_id=current_user.user_id,
            is_confidential=is_confidential
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Record history
    history_entry = CaseHistory(
        case_id=case.case_id,
        event="DOCUMENT_UPLOADED",
        date_time=datetime.utcnow(),
        description=f"Document '{file.filename}' (v{doc.version}, {document_type}) uploaded by {current_user.name}.",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(doc)

    AuditService.log(
        db=db,
        action="DOCUMENT_UPLOADED",
        entity_type="CaseDocument",
        entity_id=str(doc.document_id),
        user_id=current_user.user_id,
        details=f"Uploaded document {file.filename} (v{doc.version}) for Case {case.case_number}",
        ip_address=client_ip
    )

    return CaseDocumentResponse.model_validate(doc)


@router.get("/{case_id}/documents/{document_id}/download", summary="Securely Download Case Document")
def download_document(
    case_id: int,
    document_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Secure download with role-based access validation (FR-4.5.3 Documents.Download).
    """
    client_ip = request.client.host if (request and request.client) else None
    doc = db.query(CaseDocument).filter(
        CaseDocument.document_id == document_id,
        CaseDocument.case_id == case_id
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Confidential check
    if doc.is_confidential and current_user.role == UserRole.LITIGANT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Document marked confidential")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File content not found on server storage")

    AuditService.log(
        db=db,
        action="DOCUMENT_DOWNLOADED",
        entity_type="CaseDocument",
        entity_id=str(doc.document_id),
        user_id=current_user.user_id,
        details=f"Document {doc.document_name} downloaded by {current_user.username}",
        ip_address=client_ip
    )

    return FileResponse(
        path=doc.file_path,
        filename=doc.document_name,
        media_type="application/octet-stream"
    )


@router.post("/{case_id}/evidence", response_model=DigitalEvidenceResponse, status_code=status.HTTP_201_CREATED, summary="Upload Digital Evidence")
def upload_evidence(
    case_id: int,
    file: UploadFile = File(...),
    evidence_type: str = Form("Document"), # Audio, Video, Image, Document, Forensics
    description: Optional[str] = Form(None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.LAWYER, UserRole.ADMINISTRATOR))
):
    """
    Uploads digital evidence with SHA-256 cryptographic verification (FR-4.5.3 Documents.Evidence.Attach).
    """
    client_ip = request.client.host if (request and request.client) else None
    case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    content = file.file.read()

    try:
        evidence = CaseService.store_evidence(
            db=db,
            case_id=case_id,
            filename=file.filename,
            evidence_type=evidence_type,
            content=content,
            submitted_by_id=current_user.user_id,
            description=description
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    history_entry = CaseHistory(
        case_id=case.case_id,
        event="EVIDENCE_SUBMITTED",
        date_time=datetime.utcnow(),
        description=f"Digital evidence '{file.filename}' ({evidence_type}) submitted by {current_user.name}.",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(evidence)

    AuditService.log(
        db=db,
        action="EVIDENCE_SUBMITTED",
        entity_type="DigitalEvidence",
        entity_id=str(evidence.evidence_id),
        user_id=current_user.user_id,
        details=f"Submitted evidence {file.filename} for Case {case.case_number}",
        ip_address=client_ip
    )

    return DigitalEvidenceResponse.model_validate(evidence)


@router.put("/{case_id}/evidence/{evidence_id}/verify", response_model=DigitalEvidenceResponse, summary="Verify Digital Evidence")
def verify_evidence(
    case_id: int,
    evidence_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.COURT_CLERK, UserRole.JUDGE, UserRole.ADMINISTRATOR))
):
    """
    Verifies digital evidence authenticity (DigitalEvidence.verify()).
    """
    client_ip = request.client.host if (request and request.client) else None
    evidence = db.query(DigitalEvidence).filter(
        DigitalEvidence.evidence_id == evidence_id,
        DigitalEvidence.case_id == case_id
    ).first()
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    evidence.is_verified = True

    history_entry = CaseHistory(
        case_id=case_id,
        event="EVIDENCE_VERIFIED",
        date_time=datetime.utcnow(),
        description=f"Evidence #{evidence.evidence_id} verified by {current_user.name}.",
        user_id=current_user.user_id
    )
    db.add(history_entry)
    db.commit()
    db.refresh(evidence)

    AuditService.log(
        db=db,
        action="EVIDENCE_VERIFIED",
        entity_type="DigitalEvidence",
        entity_id=str(evidence.evidence_id),
        user_id=current_user.user_id,
        details=f"Evidence #{evidence.evidence_id} verified",
        ip_address=client_ip
    )

    return DigitalEvidenceResponse.model_validate(evidence)


@router.get("/{case_id}/history", response_model=List[CaseHistoryResponse], summary="Get Case History Timeline")
def get_case_history(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns full chronological judicial history and audit trail of the case (FR-4.7.3 Tracking.Timeline).
    """
    case = db.query(CourtCase).filter(CourtCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    return [CaseHistoryResponse.model_validate(h) for h in sorted(case.history, key=lambda x: x.date_time, reverse=True)]
