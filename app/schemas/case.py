from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime

class LawyerAssignment(BaseModel):
    lawyer_id: int
    representing_party: str = "Petitioner" # Petitioner, Respondent, Intervenor

class CaseCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    case_type: str = Field(..., min_length=2, max_length=100) # Civil, Criminal, Family, Commercial, Constitutional
    priority: str = Field(default="Medium") # Low, Medium, High, Urgent
    description: Optional[str] = None
    litigant_id: int
    lawyer_assignments: Optional[List[LawyerAssignment]] = []

class CaseUpdate(BaseModel):
    title: Optional[str] = None
    case_type: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None

class CaseStatusUpdate(BaseModel):
    status: str # Registered, Active, Pending, Disposed
    reason_or_outcome: Optional[str] = None

class CaseLawyerResponse(BaseModel):
    lawyer_id: int
    name: str
    email: str
    bar_registration_no: str
    representing_party: str

    class Config:
        from_attributes = True

class CaseHistoryResponse(BaseModel):
    history_id: int
    event: str
    date_time: datetime
    description: str
    user_id: Optional[int]

    class Config:
        from_attributes = True

class CaseDocumentResponse(BaseModel):
    document_id: int
    document_name: str
    document_type: str
    file_size_bytes: int
    file_hash: str
    version: int
    is_confidential: bool
    upload_date: datetime
    uploaded_by_id: Optional[int]

    class Config:
        from_attributes = True

class DigitalEvidenceResponse(BaseModel):
    evidence_id: int
    evidence_type: str
    description: Optional[str]
    file_hash: str
    submission_date: datetime
    submitted_by_id: Optional[int]
    is_verified: bool

    class Config:
        from_attributes = True

class CourtCaseResponse(BaseModel):
    case_id: int
    case_number: str
    title: str
    case_type: str
    filing_date: date
    case_status: str
    priority: str
    description: Optional[str]
    clerk_id: Optional[int]
    litigant_id: Optional[int]
    litigant_name: Optional[str] = None
    lawyers: List[CaseLawyerResponse] = []
    documents_count: int = 0
    evidence_count: int = 0
    hearings_count: int = 0

    class Config:
        from_attributes = True

class CourtCaseDetailResponse(CourtCaseResponse):
    documents: List[CaseDocumentResponse] = []
    evidence: List[DigitalEvidenceResponse] = []
    history: List[CaseHistoryResponse] = []

class DuplicateMatch(BaseModel):
    case_id: int
    case_number: str
    title: str
    similarity_score: float
    reason: str

class DuplicateCheckResponse(BaseModel):
    is_potential_duplicate: bool
    matches: List[DuplicateMatch]
