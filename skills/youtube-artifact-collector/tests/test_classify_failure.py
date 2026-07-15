"""T-S1-16 — classify_failure.
Spec: docs/specs/A8-T-S1-16-classify_failure.spec.md

Pure computation over two plain strings: no network, no exception classes, no
fakes needed. Failure text below is written the way the collector actually
receives it — multi-line, prefixed yt-dlp stderr for the subprocess path and
bare ``str(exc)`` prose for the transcript path — so every signal is matched as
a substring inside a longer line rather than as a whole string.

The verdict vocabulary is three values, not two: ``"permanent"`` means the unit
recognized a failure that will never change, while ``"unknown"`` means it
recognized nothing at all. Folding those two into one answer is the collapse
this unit's revision exists to undo, so tests that pin a recognized signal and
tests that pin an unrecognized one are kept visibly distinct below.

Apostrophes are load-bearing here: the bot-check tests deliberately carry both
the ASCII ``'`` (U+0027) and the typographic ``’`` (U+2019) that YouTube really
sends, as pairs differing in exactly one codepoint. Do not "tidy" either form.
"""


def _ytdlp_stderr(message, video_id="dQw4w9WgXcQ"):
    """Wrap ``message`` in a realistic multi-line yt-dlp stderr block."""
    return (
        "WARNING: [youtube] Falling back to generic n function search\n"
        f"ERROR: [youtube] {video_id}: {message}\n"
        "         Use --ignore-errors to continue past this video\n"
    )


# --- Transient signals: failure class names (transcript path) ----------------

def test_request_blocked_name_is_transient(mod):
    assert mod.classify_failure("RequestBlocked", "") == "transient"


def test_ip_blocked_name_is_transient_even_though_it_is_a_subclass_of_request_blocked(mod):
    # The unit only ever sees the exact leaf name, so IpBlocked must be listed
    # independently of its parent — a string comparison has no class hierarchy.
    assert mod.classify_failure("IpBlocked", "") == "transient"


def test_youtube_request_failed_name_is_transient(mod):
    assert mod.classify_failure("YouTubeRequestFailed", "") == "transient"


# --- Transient signals: message fragments ------------------------------------

def test_http_429_in_ytdlp_stderr_is_transient(mod):
    text = _ytdlp_stderr("Unable to download API page: HTTP Error 429 (caused by <HTTPError>)")
    assert mod.classify_failure("", text) == "transient"


def test_too_many_requests_phrase_is_transient(mod):
    text = _ytdlp_stderr("Unable to download webpage: Too Many Requests")
    assert mod.classify_failure("", text) == "transient"


def test_bot_check_message_is_transient(mod):
    text = _ytdlp_stderr(
        "Sign in to confirm you're not a bot. Use --cookies-from-browser to pass browser cookies"
    )
    assert mod.classify_failure("", text) == "transient"


def test_bot_check_message_from_transcript_path_is_transient(mod):
    # Transcript-path text (bare ``str(exc)``, no yt-dlp prefix). The name here is
    # deliberately unrecognized so the verdict can only come from the text.
    text = (
        "Could not retrieve a transcript for the video dQw4w9WgXcQ!\n"
        "This is most likely caused by: Sign in to confirm you're not a bot"
    )
    assert mod.classify_failure("SomeUncharacterizedError", text) == "transient"


def test_http_500_in_ytdlp_stderr_is_transient(mod):
    text = _ytdlp_stderr("Unable to download webpage: HTTP Error 500: Internal Server Error")
    assert mod.classify_failure("", text) == "transient"


def test_http_502_in_ytdlp_stderr_is_transient(mod):
    text = _ytdlp_stderr("Unable to download webpage: HTTP Error 502: Bad Gateway")
    assert mod.classify_failure("", text) == "transient"


def test_http_503_in_ytdlp_stderr_is_transient(mod):
    text = _ytdlp_stderr("Unable to download webpage: HTTP Error 503: Service Unavailable")
    assert mod.classify_failure("", text) == "transient"


def test_timed_out_message_is_transient(mod):
    text = _ytdlp_stderr("Unable to download webpage: The read operation timed out")
    assert mod.classify_failure("", text) == "transient"


def test_timeout_message_is_transient(mod):
    text = "HTTPSConnectionPool(host='www.youtube.com', port=443): Read timeout (read=20.0)"
    assert mod.classify_failure("", text) == "transient"


def test_connection_reset_message_is_transient(mod):
    text = _ytdlp_stderr("Unable to download webpage: <urlopen error [Errno 54] Connection reset by peer>")
    assert mod.classify_failure("", text) == "transient"


def test_connection_refused_message_is_transient(mod):
    text = _ytdlp_stderr("Unable to download webpage: <urlopen error [Errno 61] Connection refused>")
    assert mod.classify_failure("", text) == "transient"


def test_dns_resolution_failure_message_is_transient(mod):
    text = _ytdlp_stderr(
        "Unable to download webpage: <urlopen error [Errno -3] Temporary failure in name resolution>"
    )
    assert mod.classify_failure("", text) == "transient"


# --- Permanent signals: failure class names (transcript path) ----------------

def test_no_transcript_found_name_is_permanent(mod):
    assert mod.classify_failure("NoTranscriptFound", "") == "permanent"


def test_transcripts_disabled_name_is_permanent(mod):
    assert mod.classify_failure("TranscriptsDisabled", "") == "permanent"


def test_video_unavailable_name_is_permanent(mod):
    assert mod.classify_failure("VideoUnavailable", "") == "permanent"


def test_video_unplayable_name_is_permanent(mod):
    assert mod.classify_failure("VideoUnplayable", "") == "permanent"


def test_age_restricted_name_is_permanent(mod):
    assert mod.classify_failure("AgeRestricted", "") == "permanent"


# --- Permanent signals: message fragments ------------------------------------

def test_private_video_in_ytdlp_stderr_is_permanent(mod):
    text = _ytdlp_stderr("Private video. Sign in if you've been granted access to this video")
    assert mod.classify_failure("", text) == "permanent"


def test_this_video_is_private_phrase_is_permanent(mod):
    text = "Could not retrieve a transcript for the video dQw4w9WgXcQ! This video is private."
    assert mod.classify_failure("", text) == "permanent"


def test_video_unavailable_in_ytdlp_stderr_is_permanent(mod):
    text = _ytdlp_stderr("Video unavailable")
    assert mod.classify_failure("", text) == "permanent"


def test_this_video_is_not_available_phrase_is_permanent(mod):
    text = _ytdlp_stderr("This video is not available in your country")
    assert mod.classify_failure("", text) == "permanent"


def test_removed_by_the_uploader_message_is_permanent(mod):
    text = _ytdlp_stderr("This video has been removed by the uploader")
    assert mod.classify_failure("", text) == "permanent"


def test_members_only_message_is_permanent(mod):
    text = _ytdlp_stderr("This video is available to this channel's members-only tier")
    assert mod.classify_failure("", text) == "permanent"


def test_join_this_channel_message_is_permanent(mod):
    text = _ytdlp_stderr("Join this channel to get access to perks")
    assert mod.classify_failure("", text) == "permanent"


def test_age_gate_message_is_permanent(mod):
    text = _ytdlp_stderr("Sign in to confirm your age. This video may be inappropriate for some users")
    assert mod.classify_failure("", text) == "permanent"


# --- The shared "Sign in to confirm" prefix: opposite verdicts ---------------

def test_bot_check_and_age_gate_share_a_prefix_but_the_bot_check_tail_is_transient(mod):
    bot_check = _ytdlp_stderr("Sign in to confirm you're not a bot")
    assert mod.classify_failure("", bot_check) == "transient"


def test_bot_check_and_age_gate_share_a_prefix_but_the_age_gate_tail_is_permanent(mod):
    age_gate = _ytdlp_stderr("Sign in to confirm your age")
    assert mod.classify_failure("", age_gate) == "permanent"


def test_the_two_sign_in_to_confirm_messages_resolve_oppositely(mod):
    # Matching the shared "Sign in to confirm" prefix alone would collapse these
    # two into one verdict; the distinguishing tail is what must decide.
    bot_check = _ytdlp_stderr("Sign in to confirm you're not a bot. Use --cookies-from-browser")
    age_gate = _ytdlp_stderr("Sign in to confirm your age. This video may be inappropriate")
    assert mod.classify_failure("", bot_check) != mod.classify_failure("", age_gate)


# --- Apostrophe normalization: U+2019 folds to U+0027 ------------------------
#
# The bot check is the highest-consequence string in the unit, and YouTube ships
# it with a TYPOGRAPHIC apostrophe while the documented signal is ASCII. The two
# tests below are a pair: identical text differing in exactly one codepoint, so
# the fold is the only variable between them.

def test_bot_check_with_ascii_apostrophe_is_transient(mod):
    text = _ytdlp_stderr("Sign in to confirm you're not a bot. Use --cookies-from-browser")
    assert "you're not a bot" in text
    assert mod.classify_failure("", text) == "transient"


def test_bot_check_with_typographic_apostrophe_is_transient(mod):
    # U+2019 — the form YouTube actually sends. Unfolded, this misses the ASCII
    # signal and falls through to "unknown" — which is precisely the drift the
    # unknown verdict exists to make visible instead of losing in silence.
    text = _ytdlp_stderr("Sign in to confirm you’re not a bot. Use --cookies-from-browser")
    assert "you’re not a bot" in text
    assert mod.classify_failure("", text) == "transient"


def test_both_apostrophe_forms_of_the_bot_check_classify_identically(mod):
    ascii_form = _ytdlp_stderr("Sign in to confirm you're not a bot")
    typographic_form = _ytdlp_stderr("Sign in to confirm you’re not a bot")
    assert ascii_form != typographic_form
    assert mod.classify_failure("", ascii_form) == mod.classify_failure("", typographic_form)


def test_typographic_bot_check_from_transcript_path_is_transient(mod):
    # Bare ``str(exc)`` with no yt-dlp prefix; unrecognized name so only text decides.
    text = (
        "Could not retrieve a transcript for the video dQw4w9WgXcQ!\n"
        "This is most likely caused by: Sign in to confirm you’re not a bot"
    )
    assert mod.classify_failure("SomeUncharacterizedError", text) == "transient"


def test_mixed_case_bot_check_with_typographic_apostrophe_is_transient(mod):
    # The fold composes with case-insensitive matching rather than replacing it.
    text = _ytdlp_stderr("sIgN In To CoNfIrM YoU’rE NoT A BoT")
    assert mod.classify_failure("", text) == "transient"


def test_the_fold_does_not_disturb_the_prefix_trap_for_the_age_gate(mod):
    # Normalizing apostrophes must not widen the match to the shared prefix: the
    # typographic bot check and the age gate still resolve oppositely.
    typographic_bot_check = _ytdlp_stderr("Sign in to confirm you’re not a bot")
    age_gate = _ytdlp_stderr("Sign in to confirm your age. This video may be inappropriate")
    assert mod.classify_failure("", typographic_bot_check) == "transient"
    assert mod.classify_failure("", age_gate) == "permanent"


# --- Unrecognized failures: the "unknown" verdict ------------------------------
#
# Nothing in either signal list matched, so the unit reports that it recognized
# nothing rather than guessing. This is not a retry decision — callers test
# ``!= "transient"``, so an unknown failure is not retried, exactly as before —
# it is an honest one: the caller may not record a conclusion the unit never
# reached.

def test_unrecognized_text_is_unknown(mod):
    assert mod.classify_failure("", "ERROR: something nobody has ever seen") == "unknown"


def test_empty_name_and_empty_text_is_unknown(mod):
    # Nothing was offered to recognize, so nothing was recognized.
    assert mod.classify_failure("", "") == "unknown"


def test_unrecognized_class_name_with_empty_text_is_unknown(mod):
    # An unlisted class name is as unrecognized as unlisted text.
    assert mod.classify_failure("SomeUncharacterizedError", "") == "unknown"


def test_unrecognized_class_name_with_unrecognized_text_is_unknown(mod):
    text = _ytdlp_stderr("Unable to extract player response; please report this issue")
    assert mod.classify_failure("CouldNotExtract", text) == "unknown"


def test_missing_ytdlp_executable_message_is_unknown(mod):
    # Not a statement about the video at all — no signal in either list describes
    # a missing binary, so the unit must not dress this up as an established fact.
    text = "[Errno 2] No such file or directory: 'yt-dlp'"
    assert mod.classify_failure("", text) == "unknown"


# --- The permanent / unknown split: established vs merely unrecognized ---------
#
# The pair below is the distinction the unit used to collapse: under the old
# contract both sides returned "permanent", making "this video will never yield
# captions" and "I have never seen this message before" the same string. Only
# the first of those licenses a caller to write the conclusion down.

def test_a_recognized_permanent_signal_is_permanent_not_unknown(mod):
    text = _ytdlp_stderr("Private video. Sign in if you've been granted access to this video")
    assert mod.classify_failure("", text) == "permanent"


def test_an_unrecognized_text_is_unknown_not_permanent(mod):
    text = _ytdlp_stderr("Unable to extract player response; please report this issue")
    assert mod.classify_failure("", text) == "unknown"


def test_a_recognized_permanent_signal_and_an_unrecognized_text_are_different_answers(mod):
    recognized = _ytdlp_stderr("Private video. Sign in if you've been granted access")
    unrecognized = _ytdlp_stderr("Unable to extract player response; please report this issue")
    assert mod.classify_failure("", recognized) != mod.classify_failure("", unrecognized)


# --- Case-insensitive substring matching --------------------------------------

def test_lowercase_and_documented_casing_of_a_transient_signal_agree(mod):
    documented = _ytdlp_stderr("Unable to download webpage: Too Many Requests")
    lowercased = documented.lower()
    assert mod.classify_failure("", documented) == "transient"
    assert mod.classify_failure("", lowercased) == "transient"


def test_uppercase_transient_signal_is_still_transient(mod):
    text = _ytdlp_stderr("UNABLE TO DOWNLOAD WEBPAGE: TOO MANY REQUESTS").upper()
    assert mod.classify_failure("", text) == "transient"


def test_mixed_case_bot_check_message_is_transient(mod):
    text = _ytdlp_stderr("sIgN In To CoNfIrM YoU'rE NoT A BoT")
    assert mod.classify_failure("", text) == "transient"


def test_lowercase_and_documented_casing_of_a_permanent_signal_agree(mod):
    documented = _ytdlp_stderr("Private video. Sign in if you've been granted access")
    lowercased = documented.lower()
    assert mod.classify_failure("", documented) == "permanent"
    assert mod.classify_failure("", lowercased) == "permanent"


def test_signal_is_matched_inside_a_longer_line_not_as_the_whole_string(mod):
    text = _ytdlp_stderr("Unable to download API page: HTTP Error 429 — retry later please")
    assert text.strip() != "HTTP Error 429"
    assert mod.classify_failure("", text) == "transient"


# --- Repetition ---------------------------------------------------------------

def test_transient_signal_appearing_twice_still_yields_one_transient_answer(mod):
    text = (
        "ERROR: [youtube] dQw4w9WgXcQ: Unable to download API page: HTTP Error 429\n"
        "ERROR: [youtube] dQw4w9WgXcQ: Unable to download webpage: HTTP Error 429\n"
    )
    assert mod.classify_failure("", text) == "transient"


# --- Precedence: transient wins when name and text disagree -------------------

def test_transient_name_with_permanent_looking_text_is_transient(mod):
    text = "Could not retrieve a transcript for the video dQw4w9WgXcQ! This video is private."
    assert mod.classify_failure("IpBlocked", text) == "transient"


def test_permanent_name_with_transient_looking_text_is_transient(mod):
    text = "Could not retrieve a transcript for the video dQw4w9WgXcQ! HTTP Error 429"
    assert mod.classify_failure("TranscriptsDisabled", text) == "transient"


def test_text_carrying_both_a_transient_and_a_permanent_signal_is_transient(mod):
    text = (
        "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable\n"
        "ERROR: [youtube] dQw4w9WgXcQ: Unable to download webpage: HTTP Error 429\n"
    )
    assert mod.classify_failure("", text) == "transient"


# --- Purity and return vocabulary ---------------------------------------------

def test_same_inputs_always_yield_the_same_answer(mod):
    text = _ytdlp_stderr("Unable to download webpage: HTTP Error 503: Service Unavailable")
    first = mod.classify_failure("", text)
    second = mod.classify_failure("", text)
    assert first == second == "transient"


def test_return_value_is_only_ever_one_of_the_three_verdict_strings(mod):
    samples = [
        ("", ""),
        ("", _ytdlp_stderr("Video unavailable")),
        ("", _ytdlp_stderr("Sign in to confirm you're not a bot")),
        ("IpBlocked", ""),
        ("RequestBlocked", ""),
        ("YouTubeRequestFailed", ""),
        ("NoTranscriptFound", ""),
        ("VideoUnplayable", ""),
        ("AgeRestricted", ""),
        ("TotallyUnknownError", "ERROR: something nobody has ever seen"),
    ]
    for name, text in samples:
        assert mod.classify_failure(name, text) in ("transient", "permanent", "unknown")
