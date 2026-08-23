"""Tone guardrails for the dunning escalation ladder.

Deterministic tone policy (the "strict system-prompt constraint" the build guide
allows in place of Bedrock Guardrails). ``apply_tone_guardrail`` checks a draft
against a small set of aggressive markers and, when the draft fails, returns a
professionally reworded message for the same escalation tier. A clean draft is
returned unchanged.

It is registered as a Strands ``@tool``, but the deterministic
``check_due_dates`` pipeline also calls it directly, so a tone check is never
left to the model's discretion.
"""

from __future__ import annotations

from strands import tool

# Lowercase substrings that indicate an unprofessional / aggressive tone.
AGGRESSIVE_PHRASES = (
    "sue",
    "lawsuit",
    "legal action",
    "collections",
    "debt collector",
    "or else",
    "pay up",
    "you better",
    "final warning",
    "last chance",
    "we will not hesitate",
    "deadbeat",
    "scam",
)


def _has_aggressive_phrase(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in AGGRESSIVE_PHRASES)


def _has_shouting(text: str) -> bool:
    """True when the draft contains a run of three or more all-caps words."""
    run = 0
    for word in text.split():
        if word.isalpha() and word.isupper() and len(word) >= 3:
            run += 1
            if run >= 3:
                return True
        else:
            run = 0
    return False


def _is_aggressive(text: str) -> bool:
    return _has_aggressive_phrase(text) or _has_shouting(text)


def _professional_rewrite(tier: str) -> str:
    """A safe, tier-appropriate message used when a draft fails the tone check."""
    if tier == "day_3":
        return (
            "Just a friendly check-in regarding your open invoice. No rush — "
            "could you let us know its status when you have a moment? Thank you."
        )
    if tier == "day_7":
        return (
            "This is a polite reminder that your invoice is now past its due date "
            "and a late fee may apply. Please let us know if you have any questions "
            "or would like to arrange payment."
        )
    # day_14 (work-pause warning)
    return (
        "We value the work we do together and want to flag that this invoice is "
        "significantly overdue. To continue work we will need this resolved — "
        "please reach out so we can sort it out together."
    )


@tool
def apply_tone_guardrail(draft_text: str, tier: str) -> str:
    """Check a draft's tone and rewrite it if it is unprofessional.

    Args:
        draft_text: The proposed email text.
        tier: Escalation tier (day_3, day_7, or day_14).

    Returns:
        The original text if it is professional, otherwise a safe reworded
        message for the same tier.
    """
    if not _is_aggressive(draft_text):
        return draft_text
    return _professional_rewrite(tier)
