"""
AI explanation layer for AI Settlement Investigator, using Google's Gemini API.

CRITICAL DESIGN RULE: the LLM only narrates numbers the deterministic
reconciliation engine already computed. It never invents amounts, and
it never decides whether something is a discrepancy -- that's the
engine's job. If the LLM call fails for any reason, we fall back to
the engine's own template explanation/action, so the product never breaks.
"""

import json
import os

from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
MODEL = "gemini-3.6-flash"  # free-tier model, good enough for narration


def generate_ai_explanations(discrepancies: list[dict]) -> dict[str, dict]:
    """
    Takes a list of already-detected discrepancy dicts (from the reconciliation
    engine) and asks the LLM to narrate each one in plain English with a
    recommended action. Returns {payment_id: {"explanation": ..., "action": ...}}.

    If discrepancies is empty, or the API call fails, returns {} and the
    caller should fall back to the engine's own template text.
    """
    if not discrepancies:
        return {}

    payload = [
        {
            "payment_id": d["payment_id"],
            "category": d["category"],
            "subtype": d["subtype"],
            "discrepancy_amount": d["discrepancy_amount"],
            "confidence": d["confidence"],
        }
        for d in discrepancies
    ]

    prompt = f"""You are a finance operations assistant. Below is a JSON list of
payment settlement discrepancies that have ALREADY been detected and classified
by a deterministic reconciliation engine. Your job is ONLY to explain each one
in plain, professional English and recommend a concrete next action.

Rules:
- Do NOT invent, guess, or alter any amount, payment_id, category, or subtype.
- Use ONLY the numbers given below.
- Be concise: 1-2 sentences per explanation, 1 sentence per action.

Discrepancies:
{json.dumps(payload, indent=2)}

Respond with ONLY a JSON array, no other text, in this exact shape:
[
  {{"payment_id": "...", "explanation": "...", "action": "..."}}
]
"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.lower().startswith("json"):
                text = text[4:]

        parsed = json.loads(text)
        return {item["payment_id"]: item for item in parsed}

    except Exception as e:
        print(f"[ai_explainer] LLM call failed, falling back to templates: {e}")
        return {}