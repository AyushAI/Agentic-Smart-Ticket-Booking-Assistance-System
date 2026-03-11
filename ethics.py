"""
ethics.py — Unethical request detection.

Requirement: "Reject unethical requests (e.g., booking for fake identities)"

Approach: rule-based keyword list + LLM-based classification via Groq.
The LLM check catches paraphrased / indirect attempts the keyword list misses.
"""

import os
import logging
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Fast keyword pre-filter (no LLM call needed for obvious cases)
BLOCKED_KEYWORDS = [
    "fake id", "fake identity", "fake name", "false name", "false identity",
    "someone else's id", "another person's id", "stolen passport", "forged",
    "fraud", "fraudulent", "illegal", "smuggle", "smuggling",
    "book for free without paying", "bypass payment", "cheat the system",
    "terrorist", "weapon", "explosive", "bomb",
]

_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)


def is_unethical(query: str) -> tuple[bool, str]:
    """
    Returns (is_blocked: bool, reason: str).
    Two-stage check: keyword scan first, then LLM classification.
    """
    q_lower = query.lower()

    # Stage 1: keyword scan — fast, no API call
    for kw in BLOCKED_KEYWORDS:
        if kw in q_lower:
            reason = f"Request contains disallowed content: '{kw}'"
            logger.warning("Ethics block (keyword): %s | query: %s", kw, query)
            return True, reason

    # Stage 2: LLM classification — catches paraphrased/indirect attempts
    prompt = f"""You are a safety classifier for a travel booking assistant.

Determine if the following user request is unethical, illegal, or violates terms of service.
Unethical includes: booking under fake/stolen identities, fraud, smuggling, threats, or any illegal activity.

User request: "{query}"

Reply with ONLY one of these two formats — nothing else:
SAFE
UNSAFE: <one sentence reason>"""

    try:
        response = _llm.invoke(prompt)
        answer = response.content.strip()
        if answer.startswith("UNSAFE"):
            reason = answer.replace("UNSAFE:", "").strip()
            logger.warning("Ethics block (LLM): %s | query: %s", reason, query)
            return True, reason
        return False, ""
    except Exception as e:
        # If the ethics check itself fails, fail open (allow) but log it
        logger.error("Ethics LLM check failed: %s — allowing request", e)
        return False, ""