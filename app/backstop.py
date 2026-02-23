"""
backstop.py — Python post-generation filter.

Catches cases where the LLM fails to refuse out-of-scope or safety-sensitive
messages, and returns a safe fallback response instead.
"""

import re

# --- Safety / Distress Keywords ---
# If the user input contains these, skip the LLM and return a crisis response.
DISTRESS_PATTERNS = [
    r"\b(suicid|kill myself|end my life|self.harm|want to die|hurt myself)\b",
    r"\b(depressed|hopeless|no reason to live)\b",
]

DISTRESS_RESPONSE = (
    "I'm just a coffee bot, so I'm not equipped to help with what you're describing. "
    "Please reach out to someone who can — the 988 Suicide & Crisis Lifeline is available "
    "24/7 by calling or texting 988 (US). You deserve real support. ☕"
)

# --- Out-of-Scope Topics (keyword backstop) ---
# These catch cases where the LLM answers something it shouldn't.
# Maps a regex pattern to a friendly redirect message.
OUT_OF_SCOPE_PATTERNS = [
    (
        r"\b(open a caf[eé]|start a coffee shop|business plan|profit margin|wholesale price|pos system|hire barista)\b",
        "That sounds like a café business question, which is outside BrewBot's expertise! "
        "For business advice, check out the Specialty Coffee Association (sca.coffee). "
        "Happy to help with anything about brewing though! ☕",
    ),
    (
        r"\b(tea|matcha|chai|kombucha|juice|smoothie|beer|wine|cocktail|whiskey|alcohol)\b",
        "BrewBot is a coffee specialist — other beverages are outside my expertise. "
        "Ask me anything about coffee brewing and I'm all yours! ☕",
    ),
    (
        r"\b(diagnos|prescri|medication|doctor|cancer|diabetes|heart disease|blood pressure|calorie|diet plan|weight loss)\b",
        "BrewBot covers brewing craft, not medical or nutritional advice. "
        "For health questions, please consult a healthcare professional. "
        "I'm happy to talk about coffee flavors, ratios, or brewing methods! ☕",
    ),
]

# --- LLM Refusal Bypass Detection ---
# If the model's OUTPUT looks like it answered an out-of-scope topic despite
# our prompt, these patterns on the OUTPUT signal a missed refusal.
# (Used in eval only — not applied at runtime to avoid false positives.)
REFUSAL_PHRASES = [
    "outside my expertise",
    "outside brewbot",
    "i'm just a coffee",
    "coffee specialist",
    "brewbot focuses on",
    "not equipped to help",
    "consult a",
    "healthcare professional",
    "not 100% certain",
]


def check_input(user_message: str) -> str | None:
    """
    Check user input BEFORE sending to the LLM.
    Returns a fallback string if triggered, or None if input is safe to pass through.
    """
    msg = user_message.lower()

    # Check distress first (highest priority)
    for pattern in DISTRESS_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return DISTRESS_RESPONSE

    # Check out-of-scope topics
    for pattern, response in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return response

    return None


def check_output(llm_response: str, user_message: str) -> str | None:
    """
    Check LLM OUTPUT after generation.
    Returns a corrected fallback if the model appears to have answered
    something it shouldn't. Returns None if output looks fine.
    """
    msg_lower = user_message.lower()
    response_lower = llm_response.lower()

    # If user asked about non-coffee beverage but model didn't refuse
    if re.search(r"\b(matcha|kombucha|beer|wine|cocktail)\b", msg_lower):
        if not any(phrase in response_lower for phrase in REFUSAL_PHRASES):
            return (
                "BrewBot is a coffee specialist — other beverages fall outside my expertise. "
                "Ask me anything coffee-related and I'm happy to help! ☕"
            )

    return None


def is_refusal(response: str) -> bool:
    """Return True if a response contains a recognizable refusal phrase."""
    response_lower = response.lower()
    return any(phrase in response_lower for phrase in REFUSAL_PHRASES)
