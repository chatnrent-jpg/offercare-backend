"""
Payment Provider Adapters
Concrete implementations for each financial rail.
"""

from .airwallex_adapter import AirwallexAdapter

__all__ = [
    "AirwallexAdapter",
]
