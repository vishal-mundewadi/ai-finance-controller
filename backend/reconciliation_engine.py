"""
AI Settlement Investigator — deterministic reconciliation engine.

IMPORTANT: this module must NEVER read ground_truth.csv. It only ever sees
payments.csv, refunds.csv, and settlements.csv, exactly like a real
finance-ops system would. Scoring against ground truth happens separately,
in evaluate.py, after predictions are generated.

Usage:
  python3 reconciliation_engine.py --preset quick
Writes: <preset>_predictions.csv
"""

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta

GST_ON_FEE_RATE = 0.18
PAYMENT_METHOD_FEE_RATES = {
    "UPI": 0.005, "CARD": 0.020, "NETBANKING": 0.015, "WALLET": 0.018,
    "INTERNATIONAL": 0.035,
}
FEE_TOLERANCE_ABS = 0.5       # rupees; guards against float rounding noise
SETTLEMENT_SLA_DAYS = 1       # T+1 settlement SLA, matches how this dataset is generated

ACTIONS = {
    ("MISSING_TRANSACTION", None):
        "Verify whether the transaction was omitted from the settlement batch. "
        "Escalate to the payment gateway if the settlement SLA has been exceeded.",
    ("DELAYED_SETTLEMENT", None):
        "No recovery needed yet — confirm it lands in the next batch. "
        "Escalate to the gateway only if the T+1 settlement SLA is breached.",
    ("FEE_TAX_MISMATCH", None):
        "Audit the gateway fee calculation for this payment method; "
        "raise a fee dispute with the gateway if the overcharge is confirmed.",
    ("REFUND_MISMATCH", "FULL"):
        "Verify refund accounting — the full refund does not appear to have "
        "been netted out of the settlement payout. Recover the overpaid amount.",
    ("REFUND_MISMATCH", "PARTIAL"):
        "Reconcile the remaining refunded amount — it was not netted out of "
        "the settlement payout. Recover the outstanding portion.",
    ("NO_ACTION_REQUIRED", "FAILED_PAYMENT_EXCLUDED"): "No action required.",
    ("NO_ACTION_REQUIRED", "REFUND_DELAYED"): "No action required this cycle.",
    ("NO_ACTION_REQUIRED", "CLEAN"): "No action required.",
}

EXPLANATIONS = {
    ("MISSING_TRANSACTION", None):
        "Payment was captured successfully but never appears in the settlement batch.",
    ("DELAYED_SETTLEMENT", None):
        "Payment was captured successfully but settled after the expected T+{sla}-day cutoff.",
    ("FEE_TAX_MISMATCH", None):
        "Gateway fee/tax charged does not match the expected rate for this payment method.",
    ("REFUND_MISMATCH", "FULL"):
        "Payment was fully refunded to the customer, but the settlement still paid out the full amount.",
    ("REFUND_MISMATCH", "PARTIAL"):
        "Payment was partially refunded, but the settlement was not adjusted for the refund.",
    ("NO_ACTION_REQUIRED", "FAILED_PAYMENT_EXCLUDED"):
        "Payment failed and was correctly excluded from expected settlement.",
    ("NO_ACTION_REQUIRED", "REFUND_DELAYED"):
        "A refund exists but was processed after this settlement's cutoff, so no adjustment is due yet.",
    ("NO_ACTION_REQUIRED", "CLEAN"):
        "Settlement matches the expected amount within tolerance.",
}


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def index_by_payment(rows):
    idx = defaultdict(list)
    for r in rows:
        idx[r["payment_id"]].append(r)
    return idx


def expected_settlement(amount, method):
    fee_rate = PAYMENT_METHOD_FEE_RATES.get(method, 0.02)  # sane default if method unseen
    fee = round(amount * fee_rate, 2)
    gst = round(fee * GST_ON_FEE_RATE, 2)
    return round(amount - fee - gst, 2), fee, gst


def make_result(payment_id, settlement_id, is_discrepancy, category, subtype,
                 discrepancy_amount, confidence):
    key = (category, subtype)
    explanation = EXPLANATIONS.get(key, "").format(sla=SETTLEMENT_SLA_DAYS)
    action = ACTIONS.get(key, "Review manually.")
    return {
        "payment_id": payment_id,
        "settlement_id": settlement_id,
        "is_discrepancy": is_discrepancy,
        "category": category,
        "subtype": subtype or "",
        "discrepancy_amount": discrepancy_amount,
        "confidence": confidence,
        "explanation": explanation,
        "recommended_action": action,
    }


def reconcile(payments, refunds, settlements):
    settlements_by_payment = index_by_payment(settlements)
    refunds_by_payment = index_by_payment(refunds)

    results = []
    for p in payments:
        payment_id = p["payment_id"]
        settlement_id = p["settlement_id"]
        amount = float(p["amount"])
        method = p["payment_method"]
        payment_date = parse_date(p["payment_date"])
        expected_cutoff = payment_date + timedelta(days=SETTLEMENT_SLA_DAYS)

        # ---- Failed payment: correctly excluded, never expected to settle ----
        if p["status"] == "FAILED":
            results.append(make_result(payment_id, settlement_id, False,
                                        "NO_ACTION_REQUIRED", "FAILED_PAYMENT_EXCLUDED",
                                        0.0, 1.0))
            continue

        base_expected, expected_fee, expected_gst = expected_settlement(amount, method)
        settlement_rows = settlements_by_payment.get(payment_id, [])

        # ---- Missing transaction: captured, but no settlement row at all ----
        if not settlement_rows:
            results.append(make_result(payment_id, settlement_id, True,
                                        "MISSING_TRANSACTION", None,
                                        base_expected, 1.0))
            continue

        srow = settlement_rows[0]
        settled_amount = float(srow["settled_amount"])
        settled_date = parse_date(srow["settlement_date"])
        fee_charged = float(srow["fee_charged"])

        # ---- Delayed settlement: landed after the T+N cutoff ----
        if settled_date > expected_cutoff:
            results.append(make_result(payment_id, settlement_id, True,
                                        "DELAYED_SETTLEMENT", None,
                                        base_expected, 0.95))
            continue

        refund_rows = refunds_by_payment.get(payment_id, [])
        if refund_rows:
            refund = refund_rows[0]
            refund_type = refund["refund_type"]
            refund_amount = float(refund["refund_amount"])
            processed_before_cutoff = refund["processed_before_cutoff"] == "True"

            if not processed_before_cutoff:
                # Refund hasn't hit the books yet this cycle -- correctly no action, IF
                # the settlement amount still matches what it should absent any refund.
                if abs(settled_amount - base_expected) <= FEE_TOLERANCE_ABS:
                    results.append(make_result(payment_id, settlement_id, False,
                                                 "NO_ACTION_REQUIRED", "REFUND_DELAYED",
                                                 0.0, 0.9))
                    continue
                # else fall through to fee/mismatch checks below

            elif refund_type == "FULL":
                correct_expected = 0.0
                diff = round(settled_amount - correct_expected, 2)
                if abs(diff) > FEE_TOLERANCE_ABS:
                    results.append(make_result(payment_id, settlement_id, True,
                                                 "REFUND_MISMATCH", "FULL", diff, 0.95))
                    continue

            elif refund_type == "PARTIAL":
                correct_expected = round(base_expected - refund_amount, 2)
                diff = round(settled_amount - correct_expected, 2)
                if abs(diff) > FEE_TOLERANCE_ABS:
                    results.append(make_result(payment_id, settlement_id, True,
                                                 "REFUND_MISMATCH", "PARTIAL", diff, 0.95))
                    continue

        # ---- Fee/tax mismatch check ----
        if abs(fee_charged - expected_fee) > FEE_TOLERANCE_ABS:
            diff = round(base_expected - settled_amount, 2)
            results.append(make_result(payment_id, settlement_id, True,
                                        "FEE_TAX_MISMATCH", None, diff, 0.9))
            continue

        # ---- Clean ----
        results.append(make_result(payment_id, settlement_id, False,
                                    "NO_ACTION_REQUIRED", "CLEAN", 0.0, 0.9))

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="quick")
    args = parser.parse_args()

    payments = load_rows(f"data/{args.preset}/payments.csv")
    refunds = load_rows(f"data/{args.preset}/refunds.csv")
    settlements = load_rows(f"data/{args.preset}/settlements.csv")

    results = reconcile(payments, refunds, settlements)

    out_path = f"data/{args.preset}/predictions.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    flagged = sum(1 for r in results if r["is_discrepancy"])
    print(f"[{args.preset}] {len(results)} payments processed, "
          f"{flagged} flagged as discrepancies -> {out_path}")


if __name__ == "__main__":
    main()
