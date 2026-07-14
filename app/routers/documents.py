from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.document_processing import DocumentProcessingEngine

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Compliance Document Capture Pipeline"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post(
    "/{credential_id}/upload-pdf",
    status_code=status.HTTP_201_CREATED,
    summary="Accept and track a PDF certification document for an active profile"
)
async def upload_compliance_document(credential_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Ingests official compliance documentation via safe multi-part form parameters,
    persists the document, and attaches the tracking details directly to the worker record.
    """
    engine = DocumentProcessingEngine(db)
    result = await engine.processed_uploaded_pdf(credential_id=credential_id, file=file)
    
    if not result["success"]:
        # Match explicit processing failure modes to proper HTTP statuses
        if result["error"] in ["INVALID_MIME_TYPE", "FILE_TOO_LARGE"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["detail"])
        elif result["error"] == "CREDENTIAL_NOT_FOUND":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["detail"])
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["detail"])

    return result
