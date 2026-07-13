"""
VettedMe Enterprise Engine - Resume Parser Service
Async resume extraction and structured parsing using OpenAI.
Supports PDF, DOCX, and TXT formats with healthcare staffing focus.
"""

import io
import json
import logging
import os
from typing import Any, Optional

from pydantic import BaseModel
from app.services.ai_client import get_ai_client, AIClient
from app.api.v1.schemas import HealthcareCredentialSchema, MarylandLicenseType

logger = logging.getLogger(__name__)

# Resume parsing configuration
RESUME_PARSER_ENABLED = os.getenv("RESUME_PARSER_ENABLED", "true").lower() == "true"
RESUME_MAX_SIZE_MB = int(os.getenv("RESUME_MAX_SIZE_MB", "5"))
RESUME_CONFIDENCE_THRESHOLD = float(os.getenv("RESUME_CONFIDENCE_THRESHOLD", "0.7"))


class ResumeParserError(Exception):
    """Base exception for resume parsing operations."""
    pass


class MarylandCredentialsExtraction(BaseModel):
    """
    Response model for Maryland healthcare credential extraction.
    Wraps multiple credentials found in resume text.
    """
    credentials: list[HealthcareCredentialSchema]
    extraction_notes: str
    found_count: int


class ResumeParser:
    """
    VettedMe resume parser with OpenAI-powered structured extraction.
    Focuses on healthcare staffing requirements: skills, certifications, work history, education.
    """
    
    def __init__(self, ai_client: Optional[AIClient] = None):
        """
        Initialize resume parser with AI client.
        
        Args:
            ai_client: Optional AIClient instance (defaults to singleton)
        """
        self.ai_client = ai_client or get_ai_client()
        self.enabled = RESUME_PARSER_ENABLED and self.ai_client.enabled
    
    async def parse_resume_text(
        self,
        resume_text: str,
        candidate_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Parse resume text into structured healthcare staffing data.
        
        Args:
            resume_text: Raw resume text content
            candidate_name: Optional candidate name for context
        
        Returns:
            Dict with parsed resume data including skills, certifications, work history, education
        """
        if not self.enabled:
            logger.warning("Resume parser not enabled - returning mock data")
            return self._graceful_degradation_response(resume_text, candidate_name)
        
        if not resume_text or len(resume_text.strip()) < 50:
            logger.warning("Resume text too short - minimum 50 characters required")
            return self._graceful_degradation_response(resume_text, candidate_name)
        
        # Construct healthcare-focused parsing prompt
        system_prompt = """You are a healthcare staffing resume parser. Extract structured information from resumes and return JSON.

Focus on:
1. Skills (clinical, technical, soft skills)
2. Certifications (licenses, credentials with expiration dates if available)
3. Work History (facility name, role, dates, responsibilities)
4. Education (degree, institution, year)

Return JSON with this exact structure:
{
    "candidate_name": "Full Name",
    "email": "email@example.com or null",
    "phone": "phone number or null",
    "skills": ["skill1", "skill2", ...],
    "certifications": [
        {"name": "RN License", "state": "MD", "number": "12345", "expiration": "2025-12-31 or null"},
        ...
    ],
    "work_history": [
        {
            "facility": "Hospital Name",
            "role": "Registered Nurse",
            "start_date": "2020-01",
            "end_date": "2023-12 or Present",
            "responsibilities": ["responsibility1", "responsibility2"]
        },
        ...
    ],
    "education": [
        {"degree": "BSN", "institution": "University Name", "year": "2019"},
        ...
    ],
    "confidence_score": 0.95,
    "verification_flags": {
        "has_license": true,
        "has_healthcare_experience": true,
        "has_education": true
    }
}"""
        
        user_prompt = f"Parse this healthcare resume:\n\n{resume_text}"
        
        if candidate_name:
            user_prompt += f"\n\nCandidate name for context: {candidate_name}"
        
        # Execute AI parsing
        try:
            response = await self.ai_client.structured_json_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            
            if not response or not response.get("content"):
                logger.error("AI resume parsing returned empty response")
                return self._graceful_degradation_response(resume_text, candidate_name)
            
            # Parse JSON response
            parsed_data = json.loads(response["content"])
            
            # Add metadata
            parsed_data["_ai_metadata"] = {
                "model": response.get("model"),
                "tokens": response.get("total_tokens"),
                "cost": response.get("cost"),
                "elapsed_ms": response.get("elapsed_ms"),
            }
            
            # Validate confidence threshold
            confidence = parsed_data.get("confidence_score", 0.0)
            if confidence < RESUME_CONFIDENCE_THRESHOLD:
                logger.warning(
                    "Resume parsing confidence %.2f below threshold %.2f",
                    confidence,
                    RESUME_CONFIDENCE_THRESHOLD,
                )
                parsed_data["_warning"] = "low_confidence"
            
            logger.info(
                "Resume parsed successfully: confidence=%.2f tokens=%s",
                confidence,
                response.get("total_tokens"),
            )
            
            return parsed_data
        
        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON: %s", e)
            return self._graceful_degradation_response(resume_text, candidate_name)
        
        except Exception as e:
            logger.error("Resume parsing error: %s", e)
            return self._graceful_degradation_response(resume_text, candidate_name)
    
    async def extract_maryland_credentials(
        self,
        resume_text: str,
        candidate_name: Optional[str] = None,
    ) -> Optional[MarylandCredentialsExtraction]:
        """
        Extract Maryland Board of Nursing credentials using OpenAI Structured Output.
        
        Uses the HealthcareCredentialSchema Pydantic model for guaranteed schema compliance.
        This ensures extracted credentials match our database structure exactly.
        
        Args:
            resume_text: Raw resume text content
            candidate_name: Optional candidate name for context
        
        Returns:
            MarylandCredentialsExtraction with found credentials or None on failure
        """
        if not self.enabled:
            logger.warning("Resume parser not enabled - credential extraction unavailable")
            return None
        
        if not resume_text or len(resume_text.strip()) < 50:
            logger.warning("Resume text too short for credential extraction")
            return None
        
        # Construct Maryland-specific credential extraction prompt
        system_prompt = """You are a Maryland Board of Nursing credential verification specialist.

Your task: Extract ONLY Maryland state nursing licenses from resumes.

**Maryland License Types:**
- CNA: Certified Nursing Assistant
- GNA: Geriatric Nursing Assistant (Critical for Assisted Living Facilities)
- LPN: Licensed Practical Nurse
- RN: Registered Nurse

**Extraction Rules:**
1. ONLY extract Maryland licenses (MD, Maryland Board of Nursing, MBON)
2. License numbers are typically alphanumeric (e.g., "R123456", "CNA-45678")
3. Expiration dates must be parseable dates (YYYY-MM-DD format)
4. If expiration date is missing or unclear, omit the credential
5. Do NOT extract licenses from other states
6. Do NOT extract certifications (CPR, BLS, ACLS) - only state nursing licenses

**Output:**
- Return all valid Maryland nursing credentials found
- Set is_ohcq_verified=false and background_check_passed=false (verification happens separately)
- Include extraction_notes explaining what you found
- Set found_count to the number of valid credentials extracted

If NO Maryland licenses are found, return empty credentials list with explanatory notes."""
        
        user_prompt = f"Extract Maryland nursing licenses from this resume:\n\n{resume_text}"
        
        if candidate_name:
            user_prompt += f"\n\nCandidate name: {candidate_name}"
        
        # Execute AI extraction with Pydantic schema
        try:
            extracted = await self.ai_client.structured_pydantic_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_model=MarylandCredentialsExtraction,
                temperature=0.2,  # Very low temperature for precision
            )
            
            if not extracted:
                logger.error("Maryland credential extraction returned empty response")
                return None
            
            logger.info(
                "Maryland credentials extracted: found=%d candidate=%s",
                extracted.found_count,
                candidate_name or "unknown",
            )
            
            return extracted
        
        except Exception as e:
            logger.error("Maryland credential extraction error: %s", e)
            return None
    
    async def extract_text_from_file(
        self,
        file_content: bytes,
        filename: str,
    ) -> Optional[str]:
        """
        Extract text content from resume file (PDF, DOCX, TXT).
        
        Args:
            file_content: Raw file bytes
            filename: Original filename with extension
        
        Returns:
            Extracted text or None on failure
        """
        # Check file size
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > RESUME_MAX_SIZE_MB:
            logger.warning(
                "Resume file size %.2f MB exceeds limit %d MB",
                file_size_mb,
                RESUME_MAX_SIZE_MB,
            )
            raise ResumeParserError(f"File size exceeds {RESUME_MAX_SIZE_MB}MB limit")
        
        filename_lower = filename.lower()
        
        try:
            # TXT files - direct decode
            if filename_lower.endswith(".txt"):
                return file_content.decode("utf-8", errors="ignore")
            
            # PDF files - requires pypdf
            elif filename_lower.endswith(".pdf"):
                try:
                    import pypdf
                    
                    pdf_file = io.BytesIO(file_content)
                    pdf_reader = pypdf.PdfReader(pdf_file)
                    
                    text_parts = []
                    for page in pdf_reader.pages:
                        text_parts.append(page.extract_text())
                    
                    return "\n\n".join(text_parts)
                
                except ImportError:
                    logger.error("pypdf not installed - PDF parsing unavailable")
                    raise ResumeParserError("PDF parsing not available - pypdf required")
            
            # DOCX files - requires python-docx
            elif filename_lower.endswith(".docx"):
                try:
                    import docx
                    
                    docx_file = io.BytesIO(file_content)
                    doc = docx.Document(docx_file)
                    
                    text_parts = []
                    for paragraph in doc.paragraphs:
                        text_parts.append(paragraph.text)
                    
                    return "\n\n".join(text_parts)
                
                except ImportError:
                    logger.error("python-docx not installed - DOCX parsing unavailable")
                    raise ResumeParserError("DOCX parsing not available - python-docx required")
            
            else:
                logger.warning("Unsupported file format: %s", filename)
                raise ResumeParserError(f"Unsupported file format: {filename}")
        
        except ResumeParserError:
            raise
        
        except Exception as e:
            logger.error("Text extraction error for %s: %s", filename, e)
            raise ResumeParserError(f"Text extraction failed: {e}")
    
    def _graceful_degradation_response(
        self,
        resume_text: str,
        candidate_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Return partial results when AI parsing fails or is disabled.
        
        Args:
            resume_text: Raw resume text
            candidate_name: Optional candidate name
        
        Returns:
            Dict with basic extracted data and degradation flag
        """
        # Basic keyword extraction for skills
        healthcare_keywords = [
            "RN", "LPN", "CNA", "nursing", "patient care", "medication",
            "vital signs", "EMR", "EHR", "CPR", "BLS", "ACLS",
        ]
        
        text_lower = resume_text.lower()
        detected_skills = [kw for kw in healthcare_keywords if kw.lower() in text_lower]
        
        return {
            "candidate_name": candidate_name or "Unknown",
            "email": None,
            "phone": None,
            "skills": detected_skills,
            "certifications": [],
            "work_history": [],
            "education": [],
            "confidence_score": 0.3,
            "verification_flags": {
                "has_license": False,
                "has_healthcare_experience": len(detected_skills) > 0,
                "has_education": False,
            },
            "_degraded": True,
            "_reason": "AI parsing unavailable - basic keyword extraction only",
        }


# Global singleton instance
_resume_parser_instance: Optional[ResumeParser] = None


def get_resume_parser() -> ResumeParser:
    """
    Get or create global resume parser singleton instance.
    
    Returns:
        ResumeParser instance
    """
    global _resume_parser_instance
    if _resume_parser_instance is None:
        _resume_parser_instance = ResumeParser()
    return _resume_parser_instance
