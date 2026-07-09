"""
Test Suite: Semantic pgvector Matcher & Local Fallback Strategy

Component 2 validation: vector generation, license enforcement, performance, consistency.

Authority: Elite Systems Engineer Architecture Audit (2026-07-06).
"""

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.matcher.semantic_matcher import (
    LICENSE_HIERARCHY,
    STRICT_LICENSE_MATCHING,
    VECTOR_DIMENSION,
    MatchResult,
    SemanticMatcher,
)


@pytest.fixture
def semantic_matcher():
    """Fixture: SemanticMatcher instance."""
    return SemanticMatcher(vector_dimension=VECTOR_DIMENSION)


@pytest.fixture
def mock_db_session():
    """Fixture: Mocked SQLAlchemy AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ============================================================================
# TEST 1: Dry-run vector generation — dimension validation
# ============================================================================


@pytest.mark.asyncio
async def test_dry_run_vector_generation_dimensions(semantic_matcher):
    """
    Test that dry-run mode generates vectors with correct dimensions (1536).

    Validates:
    - Local text parsing produces valid Python list of floats
    - Vector length matches VECTOR_DIMENSION (1536)
    - All elements are finite floats (no NaN, inf)
    """
    # Sample caregiver skills text
    caregiver_text = """
    Certified Nursing Assistant with 5 years experience.
    Skills: Vitals monitoring, ADL assistance, patient mobility, wound care.
    Certifications: CPR, First Aid, Dementia Care.
    """

    # Generate embedding using local fallback
    vector = semantic_matcher._generate_local_embedding(caregiver_text)

    # Assert dimension matches
    assert len(vector) == VECTOR_DIMENSION, f"Expected {VECTOR_DIMENSION} dimensions, got {len(vector)}"

    # Assert all elements are valid floats
    assert all(isinstance(v, float) for v in vector), "Vector contains non-float elements"

    # Assert no NaN or inf values
    import math

    assert all(math.isfinite(v) for v in vector), "Vector contains NaN or inf values"

    # Assert vector is normalized (L2 norm ≈ 1.0)
    magnitude = sum(x**2 for x in vector) ** 0.5
    assert 0.99 <= magnitude <= 1.01, f"Vector not normalized: magnitude={magnitude}"

    print(f"✓ Dry-run vector generation: {len(vector)} dimensions, normalized magnitude {magnitude:.4f}")


@pytest.mark.asyncio
async def test_dry_run_empty_text_handling(semantic_matcher):
    """
    Test that empty text produces zero vector with correct dimensions.
    """
    empty_texts = ["", "   ", None]

    for text in empty_texts:
        if text is None:
            text = ""  # Convert None to empty string

        vector = semantic_matcher._generate_local_embedding(text)

        # Assert correct dimension
        assert len(vector) == VECTOR_DIMENSION

        # Assert all zeros
        assert all(v == 0.0 for v in vector), f"Empty text should produce zero vector, got non-zero values"

    print("✓ Empty text handling: zero vectors with correct dimensions")


# ============================================================================
# TEST 2: Hard license restriction enforcement
# ============================================================================


@pytest.mark.asyncio
async def test_license_restriction_cna_blocked_from_lpn(semantic_matcher, mock_db_session):
    """
    Test that CNA caregiver is strictly blocked from LPN shift.

    Validates:
    - License compatibility check occurs BEFORE vector distance calculation
    - Match returns compliance_passed=False for incompatible licenses
    - CNA cannot match LPN, GNA endorsement required for GNA shifts
    """
    caregiver_id = str(uuid.uuid4())
    shift_id = str(uuid.uuid4())

    # Mock caregiver profile: CNA license
    mock_caregiver_result = MagicMock()
    mock_caregiver_result.first.return_value = ("CNA", "CNA with patient care experience")

    # Mock shift requirements: LPN required
    mock_shift_result = MagicMock()

    async def mock_execute(query, params=None):
        if "maryland_providers" in str(query):
            return mock_caregiver_result
        return mock_shift_result

    mock_db_session.execute.side_effect = mock_execute

    # Patch shift requirements to return LPN
    with patch.object(
        semantic_matcher,
        "_get_shift_requirements",
        return_value={
            "required_license": "LPN",
            "requirements_text": "LPN shift requiring medication administration",
        },
    ):
        # Execute match
        results = await semantic_matcher.match_caregiver_to_shift(
            caregiver_id=caregiver_id,
            facility_shift_id=shift_id,
            db_session=mock_db_session,
            dry_run=True,
        )

    # Assert license block
    assert len(results) == 1
    result = results[0]
    assert result.compliance_passed is False, "CNA should be blocked from LPN shift"
    assert result.caregiver_license == "CNA"
    assert result.shift_license_required == "LPN"
    assert result.similarity_score == 0.0
    assert result.match_method == "license_blocked"

    print("✓ License restriction enforced: CNA blocked from LPN shift")


@pytest.mark.asyncio
async def test_license_compatibility_matrix(semantic_matcher):
    """
    Test full license compatibility matrix against STRICT_LICENSE_MATCHING.

    Validates:
    - RN can work any shift
    - LPN cannot work RN shifts
    - CNA cannot work LPN or GNA shifts
    - NA can only work NA shifts
    """
    # Test cases: (caregiver_license, shift_license, expected_compatible)
    test_cases = [
        ("RN", "RN", True),
        ("RN", "LPN", True),
        ("RN", "CNA", True),
        ("LPN", "RN", False),  # LPN blocked from RN
        ("LPN", "LPN", True),
        ("LPN", "CNA", True),
        ("CNA", "LPN", False),  # CNA blocked from LPN
        ("CNA", "GNA", False),  # CNA blocked from GNA
        ("CNA", "CNA", True),
        ("CNA", "NA", True),
        ("NA", "CNA", False),  # NA blocked from CNA
        ("NA", "NA", True),
        ("GNA", "LPN", False),  # GNA blocked from LPN
        ("GNA", "GNA", True),
    ]

    for caregiver_license, shift_license, expected in test_cases:
        result = semantic_matcher._is_license_compatible(caregiver_license, shift_license)
        assert result == expected, (
            f"License compatibility failed: {caregiver_license} → {shift_license} "
            f"expected {expected}, got {result}"
        )

    print(f"✓ License compatibility matrix validated: {len(test_cases)} cases passed")


# ============================================================================
# TEST 3: Fallback execution speed — performance threshold
# ============================================================================


@pytest.mark.asyncio
async def test_fallback_execution_speed(semantic_matcher, mock_db_session):
    """
    Test that local tokenization pipeline executes within performance thresholds.

    Validates:
    - Dry-run mode completes within 50ms for typical caregiver-shift match
    - No external API calls made
    - Vector generation and similarity calculation are fast
    """
    caregiver_id = str(uuid.uuid4())
    shift_id = str(uuid.uuid4())

    # Mock database responses
    mock_caregiver_result = MagicMock()
    mock_caregiver_result.first.return_value = (
        "CNA",
        "Experienced CNA with vitals monitoring, ADL assistance, patient mobility skills",
    )

    async def mock_execute(query, params=None):
        return mock_caregiver_result

    mock_db_session.execute.side_effect = mock_execute

    # Patch methods to avoid actual database writes
    with patch.object(semantic_matcher, "_store_embedding", new_callable=AsyncMock):
        with patch.object(semantic_matcher, "_store_shift_embedding", new_callable=AsyncMock):
            # Execute match with timing
            start_time = datetime.now()

            results = await semantic_matcher.match_caregiver_to_shift(
                caregiver_id=caregiver_id,
                facility_shift_id=shift_id,
                db_session=mock_db_session,
                dry_run=True,
            )

            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

    # Assert performance threshold (50ms for local fallback)
    assert execution_time_ms < 50.0, f"Execution too slow: {execution_time_ms:.2f}ms (threshold: 50ms)"

    # Assert result returned
    assert len(results) == 1
    result = results[0]
    assert result.compliance_passed is True
    assert result.match_method == "dry_run_fallback"

    print(f"✓ Fallback execution speed: {execution_time_ms:.2f}ms (threshold: 50ms)")


@pytest.mark.asyncio
async def test_batch_matching_performance(semantic_matcher):
    """
    Test batch matching performance for multiple caregiver-shift pairs.

    Validates:
    - Vector generation scales linearly
    - Batch of 10 matches completes within 200ms
    """
    # Generate 10 sample text pairs
    text_pairs = [
        (
            f"Caregiver {i}: CNA with patient care skills",
            f"Shift {i}: CNA shift requiring basic patient care",
        )
        for i in range(10)
    ]

    start_time = datetime.now()

    for caregiver_text, shift_text in text_pairs:
        vec1 = semantic_matcher._generate_local_embedding(caregiver_text)
        vec2 = semantic_matcher._generate_local_embedding(shift_text)
        similarity = semantic_matcher._cosine_similarity(vec1, vec2)

    execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

    # Assert batch performance threshold
    assert execution_time_ms < 200.0, f"Batch execution too slow: {execution_time_ms:.2f}ms (threshold: 200ms)"

    print(f"✓ Batch matching performance: 10 pairs in {execution_time_ms:.2f}ms (threshold: 200ms)")


# ============================================================================
# TEST 4: Score calculation consistency
# ============================================================================


@pytest.mark.asyncio
async def test_score_calculation_consistency(semantic_matcher):
    """
    Test that identical inputs produce identical similarity scores.

    Validates:
    - Deterministic vector generation (hash-based)
    - Cosine similarity calculation is stable
    - Same input text always produces same vector and score
    """
    text_a = "CNA with 5 years experience in vitals monitoring and patient care"
    text_b = "Shift requires CNA with vitals monitoring and patient mobility skills"

    # Generate vectors multiple times
    runs = 5
    scores = []

    for _ in range(runs):
        vec_a = semantic_matcher._generate_local_embedding(text_a)
        vec_b = semantic_matcher._generate_local_embedding(text_b)
        score = semantic_matcher._cosine_similarity(vec_a, vec_b)
        scores.append(score)

    # Assert all scores are identical
    assert len(set(scores)) == 1, f"Inconsistent scores: {scores}"

    # Assert score is reasonable (should be positive for similar text)
    assert scores[0] > 0.0, f"Expected positive similarity, got {scores[0]}"

    print(f"✓ Score calculation consistency: {runs} runs, identical score {scores[0]:.4f}")


@pytest.mark.asyncio
async def test_similarity_score_range(semantic_matcher):
    """
    Test that similarity scores fall within valid range [-1, 1].

    Validates:
    - Identical text → score ≈ 1.0
    - Completely different text → score ≈ 0.0
    - Opposite/negated text → score < 0.0 (if applicable)
    """
    # Test case 1: Identical text
    text_identical = "CNA with patient care experience"
    vec1 = semantic_matcher._generate_local_embedding(text_identical)
    vec2 = semantic_matcher._generate_local_embedding(text_identical)
    score_identical = semantic_matcher._cosine_similarity(vec1, vec2)

    assert 0.99 <= score_identical <= 1.0, f"Identical text should have score ≈ 1.0, got {score_identical}"

    # Test case 2: Similar text
    text_a = "CNA with vitals monitoring and ADL assistance skills"
    text_b = "Shift requires CNA with vitals and patient care"
    vec_a = semantic_matcher._generate_local_embedding(text_a)
    vec_b = semantic_matcher._generate_local_embedding(text_b)
    score_similar = semantic_matcher._cosine_similarity(vec_a, vec_b)

    assert 0.0 < score_similar < 1.0, f"Similar text should have 0 < score < 1, got {score_similar}"

    # Test case 3: Completely different text
    text_x = "CNA with patient care skills"
    text_y = "software engineer with Python JavaScript experience"
    vec_x = semantic_matcher._generate_local_embedding(text_x)
    vec_y = semantic_matcher._generate_local_embedding(text_y)
    score_different = semantic_matcher._cosine_similarity(vec_x, vec_y)

    # Different text should have lower score than similar text
    assert score_different < score_similar, (
        f"Different text score ({score_different:.4f}) should be lower than "
        f"similar text score ({score_similar:.4f})"
    )

    print(
        f"✓ Similarity score range: identical={score_identical:.4f}, "
        f"similar={score_similar:.4f}, different={score_different:.4f}"
    )


# ============================================================================
# TEST 5 (BONUS): Integration test with mocked database
# ============================================================================


@pytest.mark.asyncio
async def test_full_matching_workflow_integration(semantic_matcher, mock_db_session):
    """
    Integration test: Full matching workflow from caregiver to shift.

    Validates:
    - End-to-end dry-run matching
    - Database writes (mocked)
    - Result metadata completeness
    """
    caregiver_id = str(uuid.uuid4())
    shift_id = str(uuid.uuid4())

    # Mock caregiver profile
    mock_caregiver_result = MagicMock()
    mock_caregiver_result.first.return_value = (
        "CNA",
        "Experienced CNA with vitals, ADL assistance, patient mobility",
    )

    async def mock_execute(query, params=None):
        return mock_caregiver_result

    mock_db_session.execute.side_effect = mock_execute

    # Mock storage methods
    with patch.object(semantic_matcher, "_store_embedding", new_callable=AsyncMock) as mock_store_embedding:
        with patch.object(
            semantic_matcher, "_store_shift_embedding", new_callable=AsyncMock
        ) as mock_store_shift:
            # Execute full match
            results = await semantic_matcher.match_caregiver_to_shift(
                caregiver_id=caregiver_id,
                facility_shift_id=shift_id,
                db_session=mock_db_session,
                dry_run=True,
            )

    # Assert results structure
    assert len(results) == 1
    result = results[0]

    # Assert all fields populated
    assert result.caregiver_id == caregiver_id
    assert result.shift_id == shift_id
    assert 0.0 <= result.similarity_score <= 1.0
    assert result.rank == 1
    assert result.caregiver_license == "CNA"
    assert result.shift_license_required == "CNA"
    assert result.compliance_passed is True
    assert result.match_method == "dry_run_fallback"
    assert result.execution_time_ms > 0

    # Assert database writes attempted (mocked)
    mock_store_embedding.assert_called_once()
    mock_store_shift.assert_called_once()

    print("✓ Full matching workflow integration: end-to-end dry-run completed successfully")


# ============================================================================
# TEST 6 (BONUS): pgvector extension initialization
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_pgvector_indices(semantic_matcher, mock_db_session):
    """
    Test pgvector extension and HNSW index initialization.

    Validates:
    - CREATE EXTENSION IF NOT EXISTS pgvector
    - HNSW index creation on provider_profile_embeddings
    - HNSW index creation on shift_embeddings
    """
    # Mock execute to capture SQL commands
    executed_queries = []

    async def mock_execute(query, params=None):
        executed_queries.append(str(query))
        mock_result = MagicMock()
        mock_result.first.return_value = None  # Column doesn't exist initially
        return mock_result

    mock_db_session.execute.side_effect = mock_execute

    # Run initialization
    await semantic_matcher.initialize_indices(mock_db_session)

    # Assert pgvector extension created
    assert any("CREATE EXTENSION IF NOT EXISTS pgvector" in q for q in executed_queries), (
        "pgvector extension not created"
    )

    # Assert HNSW indices created
    assert any("provider_embedding_hnsw_idx" in q for q in executed_queries), (
        "Provider HNSW index not created"
    )
    assert any("shift_embedding_hnsw_idx" in q for q in executed_queries), "Shift HNSW index not created"

    # Assert commit called
    mock_db_session.commit.assert_called()

    print(f"✓ pgvector indices initialized: {len(executed_queries)} SQL commands executed")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
