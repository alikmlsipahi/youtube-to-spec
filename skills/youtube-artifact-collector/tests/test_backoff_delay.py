"""T-S1-17 — backoff_delay.
Spec: docs/specs/A8-T-S1-17-backoff_delay.spec.md

Pure computation: the exponent is verified with jitter injected via the ``rng``
parameter, never by patching ``random.random`` or ``time.sleep``, and never by
waiting. All fakes below are plain local callables so the unit stays
deterministic under test.
"""


def _counting_rng(value=0.5):
    """Fake rng that records how many times it was called."""
    calls = {"n": 0}

    def _rng():
        calls["n"] += 1
        return value

    _rng.calls = calls
    return _rng


def _fixed_rng(value):
    """Fake rng that always returns the same fixed value."""
    def _rng():
        return value
    return _rng


def _sequence_rng(values):
    """Fake rng that returns successive values from ``values`` on each call."""
    it = iter(values)

    def _rng():
        return next(it)
    return _rng


# --- Exponential growth ------------------------------------------------------

def test_attempt_zero_with_zero_jitter_returns_exactly_base(mod):
    # 2 ** 0 == 1: the zero-based rung has not grown yet.
    assert mod.backoff_delay(0, 5.0, 300.0, _fixed_rng(0.0)) == 5.0


def test_attempt_three_with_zero_jitter_returns_base_times_two_cubed(mod):
    assert mod.backoff_delay(3, 5.0, 300.0, _fixed_rng(0.0)) == 40.0


def test_default_rungs_with_zero_jitter_are_the_exact_doubling_sequence(mod):
    results = [
        mod.backoff_delay(attempt, 5.0, 300.0, _fixed_rng(0.0))
        for attempt in (0, 1, 2, 3, 4)
    ]
    assert results == [5.0, 10.0, 20.0, 40.0, 80.0]


def test_each_rung_is_exactly_double_its_predecessor_under_zero_jitter(mod):
    results = [
        mod.backoff_delay(attempt, 5.0, 300.0, _fixed_rng(0.0))
        for attempt in (0, 1, 2, 3, 4)
    ]
    for earlier, later in zip(results, results[1:]):
        assert later == 2 * earlier


def test_growth_scales_with_base_rather_than_being_hardcoded(mod):
    assert mod.backoff_delay(2, 1.0, 300.0, _fixed_rng(0.0)) == 4.0
    assert mod.backoff_delay(2, 3.0, 300.0, _fixed_rng(0.0)) == 12.0


# --- Cap ---------------------------------------------------------------------

def test_cap_does_not_bind_at_the_default_rungs(mod):
    for attempt, expected in ((0, 5.0), (1, 10.0), (2, 20.0), (3, 40.0), (4, 80.0)):
        assert mod.backoff_delay(attempt, 5.0, 300.0, _fixed_rng(0.0)) == expected


def test_attempt_five_still_grows_below_the_cap(mod):
    # 5 * 2**5 == 160, still under the 300 ceiling.
    assert mod.backoff_delay(5, 5.0, 300.0, _fixed_rng(0.0)) == 160.0


def test_attempt_six_is_the_first_rung_at_which_the_cap_binds(mod):
    # 5 * 2**6 == 320, clamped down to the 300 ceiling.
    assert mod.backoff_delay(6, 5.0, 300.0, _fixed_rng(0.0)) == 300.0


def test_rungs_beyond_the_cap_stay_clamped_at_the_ceiling(mod):
    for attempt in (6, 7, 10):
        assert mod.backoff_delay(attempt, 5.0, 300.0, _fixed_rng(0.0)) == 300.0


def test_large_attempt_stays_bounded_within_cap_and_twice_cap(mod):
    result = mod.backoff_delay(20, 5.0, 300.0, _fixed_rng(0.5))
    assert 300.0 <= result < 600.0


def test_large_attempt_with_maximal_jitter_never_reaches_twice_cap(mod):
    result = mod.backoff_delay(20, 5.0, 300.0, _fixed_rng(0.999999))
    assert 300.0 <= result < 600.0


def test_large_attempt_with_zero_jitter_returns_exactly_cap(mod):
    assert mod.backoff_delay(20, 5.0, 300.0, _fixed_rng(0.0)) == 300.0


def test_cap_below_base_clamps_from_attempt_zero_onward(mod):
    # Degenerate but not an error: the sequence never grows.
    for attempt in (0, 1, 2, 5):
        assert mod.backoff_delay(attempt, 100.0, 10.0, _fixed_rng(0.0)) == 10.0


def test_cap_below_base_still_jitters_within_the_capped_band(mod):
    result = mod.backoff_delay(3, 100.0, 10.0, _fixed_rng(0.6))
    assert 10.0 <= result < 20.0


# --- Degenerate inputs -------------------------------------------------------

def test_zero_base_returns_zero_and_rng_not_called(mod):
    for attempt in (0, 1, 4):
        rng = _counting_rng(0.5)
        assert mod.backoff_delay(attempt, 0.0, 300.0, rng) == 0.0
        assert rng.calls["n"] == 0


def test_negative_base_returns_zero_and_rng_not_called(mod):
    rng = _counting_rng(0.5)
    assert mod.backoff_delay(2, -5.0, 300.0, rng) == 0.0
    assert rng.calls["n"] == 0


def test_zero_cap_returns_zero_and_rng_not_called(mod):
    rng = _counting_rng(0.5)
    assert mod.backoff_delay(3, 5.0, 0.0, rng) == 0.0
    assert rng.calls["n"] == 0


def test_negative_cap_returns_zero_and_rng_not_called(mod):
    rng = _counting_rng(0.5)
    assert mod.backoff_delay(3, 5.0, -10.0, rng) == 0.0
    assert rng.calls["n"] == 0


def test_negative_attempt_halves_base_rather_than_raising(mod):
    # 2 ** -1 == 0.5, so d == base / 2 — a shorter delay, not an error.
    assert mod.backoff_delay(-1, 5.0, 300.0, _fixed_rng(0.0)) == 2.5


def test_negative_attempt_still_jitters_within_its_shortened_band(mod):
    result = mod.backoff_delay(-1, 5.0, 300.0, _fixed_rng(0.75))
    assert 2.5 <= result < 5.0


# --- Jitter / determinism ----------------------------------------------------

def test_jitter_keeps_result_within_the_rung_band(mod):
    for v in (0.0, 0.25, 0.5, 0.999999):
        result = mod.backoff_delay(2, 5.0, 300.0, _fixed_rng(v))
        assert 20.0 <= result < 40.0


def test_jitter_never_returns_less_than_the_pre_jitter_delay(mod):
    # The jitter's job is to break the rhythm, never to shorten the wait.
    for v in (0.0, 0.1, 0.5, 0.9, 0.999999):
        assert mod.backoff_delay(3, 5.0, 300.0, _fixed_rng(v)) >= 40.0


def test_default_rng_used_when_not_supplied(mod):
    result = mod.backoff_delay(1, 5.0, 300.0)
    assert 10.0 <= result < 20.0


def test_stateful_rng_produces_different_results_for_the_same_attempt(mod):
    rng = _sequence_rng([0.1, 0.9])
    first = mod.backoff_delay(2, 5.0, 300.0, rng)
    second = mod.backoff_delay(2, 5.0, 300.0, rng)
    assert first != second


def test_fixed_return_rng_produces_same_result_across_calls(mod):
    rng = _fixed_rng(0.42)
    first = mod.backoff_delay(2, 5.0, 300.0, rng)
    second = mod.backoff_delay(2, 5.0, 300.0, rng)
    assert first == second
