"""
Payment Provider Adapters
Concrete implementations for each financial rail.
"""

from .airwallex_rail import AirwallexRail

__all__ = [
    "AirwallexRail",
]
