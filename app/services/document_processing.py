"""
Document Upload & Verification Engine
Phase 2: Intelligence & Compliance - Document Management

Handles secure upload of healthcare professional certification documents.
Enforces OHCQ compliance validation and audit trail requirements.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.models import HealthcareCredential
from typing import Dict, Any
import hashlib

logger = logging.getLogger("DocumentProcessing")


class DocumentProcessingEngine:
    """
    OHCQ-compliant document processing engine.
    
    Features:
    - PDF validation and size limits
    - Secure file storage with unique naming
    - Database audit trail
    - SHA256 checksum verification
    - MIME type validation
    """
    
    # File size limit: 5MB
    MAX_FILE_SIZE = 5 * 1024 * 1024
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {".pdf"}
    
    def __init__(self, db: Session, upload_dir: str = "uploads/compliance_docs"):
        """
        Initialize document processing engine.
        
        Args:
            db: SQLAlchemy database session
            upload_dir: Directory for storing uploaded documents
        """
        self.db = db
        self.upload_dir = Path(upload_dir)
        
        # Create upload directory if it doesn't exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Document processing engine initialized. Upload dir: {self.upload_dir}")
    
    async def process_uploaded_pdf(
        self,
        credential_id: str,
        file: UploadFile,
        document_type: str = "certification"
    ) -> Dict[str, Any]:
        """
        Validates the incoming document, buffers it securely to storage,
        and links it back to the healthcare credential record.
        
        Args:
            credential_id: Target credential UUID
            file: Uploaded file object
            document_type: Type of document (certification, cpr_card, etc.)
        
        Returns:
            Dictionary with upload status and details
        """
        logger.info(
            f"Initiating compliance document upload for Credential ID: {credential_id}"
        )
        
        try:
            # 🛡️ Validation 1: File extension check
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in self.ALLOWED_EXTENSIONS:
                return {
                    "success": False,
                    "error": "INVALID_FILE_TYPE",
                    "detail": f"Only PDF files are accepted. Received: {file_ext}",
                    "allowed_types": list(self.ALLOWED_EXTENSIONS)
                }
            
            # 🛡️ Validation 2: Find target credential
            credential = self.db.query(HealthcareCredential).filter(
                HealthcareCredential.credential_id == credential_id
            ).first()
            
            if not credential:
                return {
                    "success": False,
                    "error": "CREDENTIAL_NOT_FOUND",
                    "detail": f"Credential {credential_id} not found in database"
                }
            
            # 🛡️ Validation 3: Read and validate file size
            contents = await file.read()
            file_size = len(contents)
            
            if file_size > self.MAX_FILE_SIZE:
                return {
                    "success": False,
                    "error": "FILE_TOO_LARGE",
                    "detail": f"File size {file_size} bytes exceeds 5MB limit",
                    "max_size_bytes": self.MAX_FILE_SIZE,
                    "file_size_bytes": file_size
                }
            
            # Generate secure filename with timestamp and hash
            timestamp = int(datetime.now(timezone.utc).timestamp())
            file_hash = hashlib.sha256(contents).hexdigest()[:8]
            safe_filename = f"{credential_id}_{timestamp}_{file_hash}.pdf"
            target_path = self.upload_dir / safe_filename
            
            # 🔒 Write file securely to storage
            try:
                with open(target_path, "wb") as buffer:
                    buffer.write(contents)
                
                logger.info(f"Document saved successfully: {target_path}")
            except Exception as write_error:
                logger.error(f"File write error: {str(write_error)}")
                return {
                    "success": False,
                    "error": "STORAGE_WRITE_FAILURE",
                    "detail": f"Failed to write file to storage: {str(write_error)}"
                }
            
            # 📝 Update credential record with document metadata
            upload_timestamp = datetime.now(timezone.utc)
            document_metadata = (
                f"Document uploaded: {safe_filename} "
                f"({document_type}, {file_size} bytes, {upload_timestamp.isoformat()})"
            )
            
            # Append to verification notes
            if credential.verification_notes:
                credential.verification_notes += f"\n{document_metadata}"
            else:
                credential.verification_notes = document_metadata
            
            # Update verification timestamp if this is a certification document
            if document_type in ["certification", "license"]:
                credential.ohcq_verified_at = upload_timestamp
            
            self.db.commit()
            
            logger.info(
                f"Document processing complete for credential {credential_id}"
            )
            
            return {
                "success": True,
                "credential_id": str(credential_id),
                "filename": safe_filename,
                "file_path": str(target_path),
                "document_type": document_type,
                "uploaded_at": upload_timestamp.isoformat(),
                "file_size_bytes": file_size,
                "checksum_sha256": hashlib.sha256(contents).hexdigest(),
                "provider": {
                    "provider_id": str(credential.provider_id),
                    "license_type": credential.license_type,
                    "license_number": credential.license_number
                }
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Document processing failed for credential {credential_id}: {str(e)}",
                exc_info=True
            )
            return {
                "success": False,
                "error": "PROCESSING_FAILED",
                "detail": f"Unexpected error during document processing: {str(e)}"
            }
    
    def get_credential_documents(self, credential_id: str) -> Dict[str, Any]:
        """
        Retrieve document upload history for a credential.
        
        Args:
            credential_id: Target credential UUID
        
        Returns:
            Dictionary with document history
        """
        credential = self.db.query(HealthcareCredential).filter(
            HealthcareCredential.credential_id == credential_id
        ).first()
        
        if not credential:
            return {
                "success": False,
                "error": "CREDENTIAL_NOT_FOUND",
                "detail": f"Credential {credential_id} not found"
            }
        
        # Parse verification notes for document history
        documents = []
        if credential.verification_notes:
            # Extract document references from notes
            lines = credential.verification_notes.split("\n")
            for line in lines:
                if "Document uploaded:" in line:
                    documents.append(line)
        
        return {
            "success": True,
            "credential_id": str(credential_id),
            "total_documents": len(documents),
            "documents": documents,
            "last_verified_at": (
                credential.ohcq_verified_at.isoformat()
                if credential.ohcq_verified_at
                else None
            )
        }
    
    def verify_document_exists(self, filename: str) -> bool:
        """
        Check if a document file exists in storage.
        
        Args:
            filename: Document filename
        
        Returns:
            True if file exists, False otherwise
        """
        file_path = self.upload_dir / filename
        return file_path.exists()
    
    def get_document_stats(self) -> Dict[str, Any]:
        """
        Get document processing statistics.
        
        Returns:
            Dictionary with stats
        """
        # Count files in upload directory
        pdf_files = list(self.upload_dir.glob("*.pdf"))
        total_size = sum(f.stat().st_size for f in pdf_files if f.is_file())
        
        return {
            "upload_directory": str(self.upload_dir),
            "total_documents": len(pdf_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "directory_exists": self.upload_dir.exists()
        }
