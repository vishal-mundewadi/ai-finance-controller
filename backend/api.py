from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from reconciliation_engine import reconcile, load_rows
from ai_explainer import generate_ai_explanations

app = FastAPI(title="AI Settlement Investigator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_dataset(preset: str):
    payments = load_rows(f"data/{preset}/payments.csv")
    refunds = load_rows(f"data/{preset}/refunds.csv")
    settlements = load_rows(f"data/{preset}/settlements.csv")
    return payments, refunds, settlements


@app.get("/settlements/{preset}/{settlement_id}/analyze")
def analyze_settlement(preset: str, settlement_id: str):
    payments, refunds, settlements = get_dataset(preset)

    batch_payments = [p for p in payments if p["settlement_id"] == settlement_id]
    if not batch_payments:
        raise HTTPException(status_code=404, detail=f"No payments found for {settlement_id}")

    results = reconcile(batch_payments, refunds, settlements)
    discrepancies = [r for r in results if r["is_discrepancy"]]

    # Ask the LLM to narrate the already-detected discrepancies.
    # If it fails for any reason, ai_map stays empty and we silently
    # keep each result's original template explanation/action.
    ai_map = generate_ai_explanations(discrepancies)

    for r in results:
        ai = ai_map.get(r["payment_id"])
        if ai:
            r["explanation"] = ai["explanation"]
            r["recommended_action"] = ai["action"]
            r["explanation_source"] = "ai"
        else:
            r["explanation_source"] = "template"

    total_discrepancy_amount = round(sum(r["discrepancy_amount"] for r in discrepancies), 2)

    return {
        "settlement_id": settlement_id,
        "total_payments": len(batch_payments),
        "total_discrepancies": len(discrepancies),
        "total_discrepancy_amount": total_discrepancy_amount,
        "results": results,
    }


@app.get("/")
def root():
    return {"status": "AI Settlement Investigator API is running"}