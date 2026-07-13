"""
VettedMe Enterprise Engine - Models Package
Submodule models for specialized database tables.
"""

# Load main models from models.py using importlib to avoid circular imports
import sys
import importlib.util
from pathlib import Path

# Check if models.py has already been loaded as a module
if "app._models_main_file" not in sys.modules:
    # Load models.py directly (not as a package)
    _models_py_path = Path(__file__).parent.parent / "models.py"
    _spec = importlib.util.spec_from_file_location("app._models_main_file", _models_py_path)
    if _spec and _spec.loader:
        _main_models = importlib.util.module_from_spec(_spec)
        sys.modules["app._models_main_file"] = _main_models
        # Import without executing the problematic import at the end
        # We'll let it execute normally since we commented out the circular import
        _spec.loader.exec_module(_main_models)
else:
    _main_models = sys.modules["app._models_main_file"]

# Export commonly used main models
ClinicalPlacementLedger = _main_models.ClinicalPlacementLedger
ClinicianPortalAccount = _main_models.ClinicianPortalAccount
ClinicianPushSubscription = _main_models.ClinicianPushSubscription
MarylandFacility = _main_models.MarylandFacility
MarylandProvider = _main_models.MarylandProvider
OfferCareJobOffer = _main_models.OfferCareJobOffer
VmsSubmissionLog = _main_models.VmsSubmissionLog

# Import models from submodules ONLY if they're not already defined in models.py
# This prevents duplicate table registration errors
try:
    # Try to get AIAuditLog from main models first
    AIAuditLog = getattr(_main_models, 'AIAuditLog', None)
except AttributeError:
    AIAuditLog = None

# If not in main models, import from submodule
if AIAuditLog is None:
    from app.models.ai_audit import AIAuditLog

# Import healthcare credential (new model from submodule)
from app.models.healthcare_credential import HealthcareCredential

# NOTE: We're NOT importing clinician_calendar, compliance_audit_ledger, etc.
# because those models are already registered when models.py is loaded.
# Direct imports of those submodules elsewhere in the codebase will still work.

__all__ = [
    "AIAuditLog",
    "HealthcareCredential",
    "ClinicalPlacementLedger",
    "ClinicianPortalAccount",
    "ClinicianPushSubscription",
    "MarylandFacility",
    "MarylandProvider",
    "OfferCareJobOffer",
    "VmsSubmissionLog",
]
