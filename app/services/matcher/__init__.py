"""
VettedMe.ai Intelligent Matching Services

Semantic pgvector matcher with local fallback strategy and strict license compliance.
"""

from app.services.matcher.semantic_matcher import SemanticMatcher, MatchResult

__all__ = ["SemanticMatcher", "MatchResult"]
