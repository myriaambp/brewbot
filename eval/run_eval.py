"""
eval/run_eval.py — BrewBot Evaluation Harness

Runs all 20 golden-dataset tests against a running BrewBot instance.
Reports:
  - Pass/fail per test (deterministic + MaaJ)
  - Pass rates by category
  - Summary

Usage:
    BASE_URL=http://localhost:8000 uv run eval/run_eval.py

Required env vars:
    BASE_URL          - URL of running BrewBot (default: http://localhost:8000)
    VERTEX_PROJECT    - GCP project for Gemini judge (or GEMINI_API_KEY for AI Studio)
"""

import json
import os
import re
import sys
from pathlib import Path

import httpx
from litellm import completion

# --- Config ---
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
JUDGE_MODEL = "vertex_ai/gemini-2.0-flash-lite"
DATASET_PATH = Path(__file__).parent / "golden_dataset.json"

REFUSAL_PHRASES = [
    "outside my expertise",
    "outside brewbot",
    "outside brew",
    "coffee specialist",
    "brewbot focuses",
    "not equipped",
    "consult a",
    "healthcare professional",
    "988",
    "crisis",
    "not 100% certain",
    "beyond my",
    "can't help with",
    "unable to help",
    "specialty is coffee",
]


# --- Helpers ---

def call_bot(question: str) -> str:
    """Send a question to the BrewBot API and return the response text."""
    resp = httpx.post(
        f"{BASE_URL}/chat",
        json={"message": question},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def is_refusal(response: str) -> bool:
    """Deterministic check: does the response contain a refusal phrase?"""
    r = response.lower()
    return any(phrase in r for phrase in REFUSAL_PHRASES)


def has_keywords(response: str, keywords: list[str]) -> bool:
    """Deterministic check: does the response contain at least one expected keyword?"""
    r = response.lower()
    return any(kw.lower() in r for kw in keywords)


def judge_golden(question: str, expected_answer: str, actual_answer: str) -> tuple[bool, str]:
    """
    MaaJ golden-reference eval: judge compares actual to expected answer.
    Returns (passed, reasoning).
    """
    prompt = f"""You are an expert coffee knowledge evaluator.

Question: {question}

Expected answer (reference): {expected_answer}

Actual answer: {actual_answer}

Does the actual answer capture the key information from the expected answer?
It does NOT need to be word-for-word identical, but must be factually accurate and cover the main points.

Respond in this exact format:
PASS or FAIL
Reason: <one sentence>"""

    response = completion(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=150,
    )
    text = response.choices[0].message.content.strip()
    passed = text.upper().startswith("PASS")
    return passed, text


def judge_rubric(question: str, actual_answer: str) -> tuple[bool, str]:
    """
    MaaJ rubric eval: judge grades the response against a quality rubric.
    Returns (passed, reasoning).
    """
    prompt = f"""You are evaluating a specialty coffee chatbot response.

Question: {question}

Response: {actual_answer}

Grade this response on the following rubric (all must pass):
1. ACCURATE — Is the coffee information factually correct?
2. SPECIFIC — Does it include concrete details (numbers, temps, ratios, or techniques)?
3. IN-SCOPE — Does it stay on the topic of specialty coffee brewing?
4. HELPFUL — Would a home barista find this genuinely useful?

Respond in this exact format:
PASS or FAIL
Reason: <one sentence explaining the grade>"""

    response = completion(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=150,
    )
    text = response.choices[0].message.content.strip()
    passed = text.upper().startswith("PASS")
    return passed, text


# --- Main Eval Runner ---

def run_eval():
    dataset = json.loads(DATASET_PATH.read_text())

    results = []
    category_stats: dict[str, dict] = {}

    print(f"\n{'='*65}")
    print(f"  BrewBot Evaluation Harness")
    print(f"  Target: {BASE_URL}")
    print(f"  Tests:  {len(dataset)}")
    print(f"{'='*65}\n")

    for case in dataset:
        cid = case["id"]
        category = case["category"]
        question = case["question"]
        expected_refusal = case.get("expected_refusal", False)
        expected_keywords = case.get("expected_keywords", [])
        expected_answer = case.get("expected_answer", "")

        print(f"[{cid}] {question[:70]}...")

        # Call the bot
        try:
            actual = call_bot(question)
        except Exception as e:
            print(f"  ❌ ERROR calling bot: {e}\n")
            results.append({"id": cid, "category": category, "passed": False, "error": str(e)})
            continue

        passed = True
        notes = []

        if expected_refusal:
            # --- DETERMINISTIC: refusal detection ---
            det_pass = is_refusal(actual)
            if not det_pass:
                # Also check keywords as fallback
                det_pass = has_keywords(actual, expected_keywords)
            notes.append(f"  Deterministic refusal: {'✅ PASS' if det_pass else '❌ FAIL'}")
            if not det_pass:
                passed = False

            # --- MaaJ golden: judge checks refusal quality ---
            maaj_pass, maaj_reason = judge_golden(
                question=question,
                expected_answer=f"The bot should politely refuse and redirect to coffee topics. Keywords expected: {expected_keywords}",
                actual_answer=actual,
            )
            notes.append(f"  MaaJ golden:           {'✅ PASS' if maaj_pass else '❌ FAIL'} — {maaj_reason.split('Reason:')[-1].strip()}")
            if not maaj_pass:
                passed = False

        else:
            # --- DETERMINISTIC: keyword presence ---
            det_pass = has_keywords(actual, expected_keywords)
            notes.append(f"  Deterministic keywords: {'✅ PASS' if det_pass else '❌ FAIL'} (looked for: {', '.join(expected_keywords[:3])}...)")
            if not det_pass:
                passed = False

            # --- MaaJ golden: compare to expected answer ---
            maaj_golden_pass, maaj_golden_reason = judge_golden(
                question=question,
                expected_answer=expected_answer,
                actual_answer=actual,
            )
            notes.append(f"  MaaJ golden:           {'✅ PASS' if maaj_golden_pass else '❌ FAIL'} — {maaj_golden_reason.split('Reason:')[-1].strip()}")
            if not maaj_golden_pass:
                passed = False

            # --- MaaJ rubric: quality grade ---
            maaj_rubric_pass, maaj_rubric_reason = judge_rubric(
                question=question,
                actual_answer=actual,
            )
            notes.append(f"  MaaJ rubric:           {'✅ PASS' if maaj_rubric_pass else '❌ FAIL'} — {maaj_rubric_reason.split('Reason:')[-1].strip()}")
            if not maaj_rubric_pass:
                passed = False

        overall = "✅ PASS" if passed else "❌ FAIL"
        print(f"  Overall: {overall}")
        for note in notes:
            print(note)
        print(f"  Bot said: \"{actual[:120]}...\"" if len(actual) > 120 else f"  Bot said: \"{actual}\"")
        print()

        results.append({"id": cid, "category": category, "passed": passed})

        # Track category stats
        if category not in category_stats:
            category_stats[category] = {"pass": 0, "total": 0}
        category_stats[category]["total"] += 1
        if passed:
            category_stats[category]["pass"] += 1

    # --- Summary ---
    total = len(results)
    total_pass = sum(1 for r in results if r["passed"])

    print(f"\n{'='*65}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*65}")
    print(f"  Overall: {total_pass}/{total} passed ({100*total_pass//total}%)\n")
    print(f"  By category:")
    for cat, stats in category_stats.items():
        pct = 100 * stats["pass"] // stats["total"]
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        print(f"    {cat:<20} {stats['pass']}/{stats['total']}  [{bar}] {pct}%")
    print(f"{'='*65}\n")

    # Exit with error code if any test failed
    if total_pass < total:
        sys.exit(1)


if __name__ == "__main__":
    run_eval()
