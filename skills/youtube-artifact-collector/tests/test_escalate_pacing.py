"""T-S1-18 — escalate_pacing.
Spec: docs/specs/A8-T-S1-18-escalate_pacing.spec.md

Pure arithmetic: no rng, no clock, no I/O. The across-video progression is
exercised by feeding the function its own return value back in as the next
``current``, exactly as the orchestration loop does — the unit itself holds
no state. That feedback loop is also why the non-negative floor is pinned
directly: a negative return would become the next call's ``current`` and trip
the opt-out branch, silently disabling pacing for the rest of the run.
"""


# --- Opt-out (current <= 0) --------------------------------------------------

def test_zero_current_returns_zero_so_sleep_requests_zero_survives_escalation(mod):
    assert mod.escalate_pacing(0, 60.0) == 0.0


def test_zero_float_current_returns_zero(mod):
    assert mod.escalate_pacing(0.0, 60.0) == 0.0


def test_negative_current_is_treated_identically_to_zero(mod):
    assert mod.escalate_pacing(-3.0, 60.0) == 0.0


def test_opt_out_ignores_ceiling_and_factor_entirely(mod):
    # ceiling and factor are irrelevant once current <= 0; nothing may resurrect pacing.
    assert mod.escalate_pacing(0.0, 60.0, 10.0) == 0.0
    assert mod.escalate_pacing(0.0, -5.0, 0.5) == 0.0
    assert mod.escalate_pacing(-1.0, 999.0, 100.0) == 0.0


def test_opt_out_holds_when_fed_back_in_repeatedly(mod):
    current = 0.0
    for _ in range(5):
        current = mod.escalate_pacing(current, 60.0)
        assert current == 0.0


# --- Escalation --------------------------------------------------------------

def test_default_starting_pacing_doubles_on_first_rate_limit_event(mod):
    assert mod.escalate_pacing(2.0, 60.0) == 4.0


def test_fed_back_progression_doubles_then_holds_at_ceiling(mod):
    current = 2.0
    seen = []
    for _ in range(6):
        current = mod.escalate_pacing(current, 60.0)
        seen.append(current)
    assert seen == [4.0, 8.0, 16.0, 32.0, 60.0, 60.0]


def test_result_is_never_smaller_than_current_for_positive_current_and_factor_above_one(mod):
    for current in (0.5, 1.0, 2.0, 7.5, 32.0, 59.0, 60.0):
        assert mod.escalate_pacing(current, 60.0) >= current


def test_product_slightly_below_ceiling_is_returned_unclamped(mod):
    assert mod.escalate_pacing(29.5, 60.0) == 59.0


# --- Ceiling -----------------------------------------------------------------

def test_product_above_ceiling_is_clamped_to_ceiling(mod):
    assert mod.escalate_pacing(32.0, 60.0) == 60.0


def test_current_already_at_ceiling_returns_ceiling_unchanged(mod):
    assert mod.escalate_pacing(60.0, 60.0) == 60.0


def test_further_events_at_the_ceiling_are_idempotent(mod):
    current = 60.0
    for _ in range(4):
        current = mod.escalate_pacing(current, 60.0)
        assert current == 60.0


def test_current_above_ceiling_is_lowered_to_the_ceiling(mod):
    # The one case where the monotonic guarantee deliberately does not hold.
    assert mod.escalate_pacing(90.0, 60.0) == 60.0


# --- Degenerate inputs -------------------------------------------------------

def test_zero_ceiling_with_positive_current_returns_zero(mod):
    assert mod.escalate_pacing(2.0, 0.0) == 0.0


def test_negative_ceiling_with_positive_current_is_floored_to_zero_not_the_ceiling(mod):
    # The ceiling binds, but the result is floored at 0.0 rather than going negative.
    assert mod.escalate_pacing(2.0, -5.0) == 0.0


def test_negative_ceiling_result_does_not_disable_pacing_when_fed_back_in(mod):
    # A negative return would trip the opt-out branch on the next call; 0.0 is stable.
    current = mod.escalate_pacing(2.0, -5.0)
    assert current == 0.0
    assert mod.escalate_pacing(current, 60.0) == 0.0


def test_non_default_factor_is_honored(mod):
    assert mod.escalate_pacing(2.0, 60.0, 3.0) == 6.0


def test_factor_of_one_disables_escalation_without_erroring(mod):
    assert mod.escalate_pacing(2.0, 60.0, 1.0) == 2.0


def test_factor_of_one_holds_pacing_flat_when_fed_back_in(mod):
    current = 2.0
    for _ in range(3):
        current = mod.escalate_pacing(current, 60.0, 1.0)
        assert current == 2.0


def test_factor_below_one_shrinks_the_pacing(mod):
    assert mod.escalate_pacing(2.0, 60.0, 0.5) == 1.0


def test_factor_of_zero_shrinks_the_pacing_to_zero(mod):
    assert mod.escalate_pacing(2.0, 60.0, 0.0) == 0.0


# --- Non-negative floor ------------------------------------------------------

def test_result_is_never_negative_across_input_combinations(mod):
    currents = (-5.0, -0.1, 0.0, 0.5, 2.0, 32.0, 60.0, 90.0)
    ceilings = (-60.0, -5.0, 0.0, 0.5, 60.0)
    factors = (-2.0, 0.0, 0.5, 1.0, 2.0, 3.0)
    for current in currents:
        for ceiling in ceilings:
            for factor in factors:
                assert mod.escalate_pacing(current, ceiling, factor) >= 0.0


def test_negative_factor_with_positive_current_is_floored_to_zero(mod):
    assert mod.escalate_pacing(2.0, 60.0, -2.0) == 0.0


# --- Purity / statelessness --------------------------------------------------

def test_same_inputs_twice_return_the_same_value(mod):
    first = mod.escalate_pacing(2.0, 60.0)
    second = mod.escalate_pacing(2.0, 60.0)
    assert first == second == 4.0


def test_no_hidden_event_counter_across_interleaved_calls(mod):
    # Interleaving unrelated calls must not shift the result for a repeated input.
    baseline = mod.escalate_pacing(8.0, 60.0)
    mod.escalate_pacing(32.0, 60.0)
    mod.escalate_pacing(0.0, 60.0)
    mod.escalate_pacing(2.0, 60.0, 3.0)
    assert mod.escalate_pacing(8.0, 60.0) == baseline
