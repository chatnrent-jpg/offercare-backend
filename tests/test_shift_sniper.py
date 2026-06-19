from app.shift_sniper import (
  ClinicianCandidate,
  SniperWeights,
  matching_priority_score,
  placement_probability,
  rank_clinicians_for_shift,
  saint_judes_icu_demo,
)


def test_saint_judes_nurse_a_priority_score() -> None:
  score = matching_priority_score(
    shift_pay=120.0,
    candidate=ClinicianCandidate("nurse_a", 1, 85.0, 0.85, 0.0),
    weights=SniperWeights(),
  )
  assert score == 471.25


def test_saint_judes_nurse_b_priority_score() -> None:
  score = matching_priority_score(
    shift_pay=120.0,
    candidate=ClinicianCandidate("nurse_b", 1, 110.0, 0.95, 1.0),
    weights=SniperWeights(),
  )
  assert score == 218.75


def test_saint_judes_nurse_c_eliminated_negative_rate_delta() -> None:
  score = matching_priority_score(
    shift_pay=120.0,
    candidate=ClinicianCandidate("nurse_c", 1, 130.0, 0.80, 0.0),
    weights=SniperWeights(),
  )
  assert score is None


def test_rank_order_notify_nurse_a_first() -> None:
  demo = saint_judes_icu_demo()
  assert demo["notify_order"] == ["nurse_a", "nurse_b"]
  eliminated = demo["eliminated"]
  assert len(eliminated) == 1
  assert eliminated[0]["clinician_id"] == "nurse_c"


def test_placement_probability_decay() -> None:
  assert placement_probability(0.0) == 0.95
  later = placement_probability(10.0)
  assert later < placement_probability(0.0)


def test_non_compliant_clinician_eliminated() -> None:
  ranked, eliminated = rank_clinicians_for_shift(
    shift_pay=120.0,
    candidates=[ClinicianCandidate("nurse_x", 0, 80.0, 0.9, 0.0)],
  )
  assert ranked == []
  assert eliminated[0].reason == "non_compliant"
