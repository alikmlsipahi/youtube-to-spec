"""T-S1-12 — request_delay.
Spec: docs/specs/A6-T-S1-12-request_delay.spec.md

Pure computation: jitter is injected via the ``rng`` parameter, never via
patching ``random.random`` or ``time.sleep``. All fakes below are plain local
callables so the unit stays deterministic under test.
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


# --- Disabled case: base <= 0 -----------------------------------------------

def test_zero_base_returns_zero_and_rng_not_called(mod):
    rng = _counting_rng(0.5)
    result = mod.request_delay(0, rng)
    assert result == 0.0
    assert rng.calls["n"] == 0


def test_negative_base_returns_zero_and_rng_not_called(mod):
    rng = _counting_rng(0.5)
    result = mod.request_delay(-3.0, rng)
    assert result == 0.0
    assert rng.calls["n"] == 0


def test_negative_base_without_rng_arg_returns_zero(mod):
    # Must short-circuit before ever touching rng (default random.random here).
    assert mod.request_delay(-1.5) == 0.0


# --- Enabled case: base > 0 --------------------------------------------------

def test_rng_lower_bound_returns_exactly_base(mod):
    rng = _fixed_rng(0.0)
    assert mod.request_delay(2.0, rng) == 2.0


def test_rng_fixed_value_matches_formula(mod):
    base = 2.0
    v = 0.37
    rng = _fixed_rng(v)
    result = mod.request_delay(base, rng)
    assert result == base + base * v
    assert base <= result < 2 * base


def test_rng_near_upper_bound_approaches_but_never_reaches_double_base(mod):
    base = 5.0
    v = 0.999999
    rng = _fixed_rng(v)
    result = mod.request_delay(base, rng)
    assert base <= result < 2 * base
    assert result == base + base * v


def test_rng_invoked_at_most_once_when_base_positive(mod):
    rng = _counting_rng(0.5)
    mod.request_delay(1.0, rng)
    assert rng.calls["n"] == 1


def test_default_rng_used_when_not_supplied(mod):
    base = 1.5
    result = mod.request_delay(base)
    assert base <= result < 2 * base


# --- Jitter / determinism properties -----------------------------------------

def test_stateful_rng_produces_different_results_across_calls(mod):
    rng = _sequence_rng([0.1, 0.9])
    first = mod.request_delay(3.0, rng)
    second = mod.request_delay(3.0, rng)
    assert first != second


def test_fixed_return_rng_produces_same_result_across_calls(mod):
    rng = _fixed_rng(0.42)
    first = mod.request_delay(4.0, rng)
    second = mod.request_delay(4.0, rng)
    assert first == second
