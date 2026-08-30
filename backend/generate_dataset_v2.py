"""
Synthetic settlement dataset generator (v2) for the AI Settlement Investigator project.

Models the real business-logic layers explicitly:

    ORDER AMOUNT -> PAYMENT CAPTURED -> SETTLEMENT EXPECTED -> SETTLEMENT ACTUAL

Key fix vs v1: a FAILED payment was never captured, so it must NOT be counted
in the correct expected-settlement total. We keep a separate naive_expected_total
so you can demonstrate the classic naive mistake of using raw order totals.

Discrepancy / label types produced (see `is_true_discrepancy` column):
  True discrepancies (engine should flag these):
    MISSING_TRANSACTION   - captured payment, no settlement row at all
    REFUND_MISMATCH_FULL  - fully refunded, but settlement still pays full amount
    REFUND_MISMATCH_PARTIAL - partially refunded, refund not netted out
    DELAYED_SETTLEMENT    - captured payment, settles after this batch's cutoff
    FEE_TAX_MISMATCH      - wrong fee/tax rate applied for the payment method
  Non-discrepancies (engine should NOT flag these -- false-positive test cases):
    NO_ISSUE_FAILED_PAYMENT_EXCLUDED - failed payment correctly excluded
    NO_ISSUE_REFUND_DELAYED          - refund exists but hasn't hit cutoff yet
    CLEAN                            - ordinary correctly-settled payment

Run:
  python3 generate_dataset.py --preset quick   (~120 payments,  fast local dev)
  python3 generate_dataset.py --preset dev     (~6000 payments, build/tune engine)
  python3 generate_dataset.py --preset eval    (~1500 payments, held-out scoring)
"""

import argparse
import csv
import random
from datetime import date, timedelta

GST_ON_FEE_RATE = 0.18

# Realistic-ish gateway fee rates by payment method (fraction of payment amount)
PAYMENT_METHODS = {
    "UPI": 0.005,
    "CARD": 0.020,
    "NETBANKING": 0.015,
    "WALLET": 0.018,
    "INTERNATIONAL": 0.035,
}
METHOD_WEIGHTS = [0.40, 0.30, 0.15, 0.10, 0.05]  # UPI-heavy, like real Indian fintech traffic

CURRENCY_BY_METHOD = {
    "UPI": "INR", "CARD": "INR", "NETBANKING": "INR", "WALLET": "INR",
    "INTERNATIONAL": "USD",
}

GATEWAY = "Razorpay"

PRESETS = {
    "quick": dict(num_settlements=10, payments_per_settlement=12),
    "dev":   dict(num_settlements=400, payments_per_settlement=15),
    "eval":  dict(num_settlements=100, payments_per_settlement=15),
}

# label -> relative weight (CLEAN weighted highest so discrepancies stay a realistic minority)
LABELS = [
    "MISSING_TRANSACTION",
    "FAILED_PAYMENT",          # -> NO_ISSUE_FAILED_PAYMENT_EXCLUDED
    "REFUND_MISMATCH_FULL",
    "REFUND_MISMATCH_PARTIAL",
    "REFUND_DELAYED",          # -> NO_ISSUE_REFUND_DELAYED
    "DELAYED_SETTLEMENT",
    "FEE_TAX_MISMATCH",
    "CLEAN",
]
LABEL_WEIGHTS = [1, 1.5, 0.8, 0.8, 0.8, 1, 1, 4]

START_DATE = date(2026, 8, 1)


def build_dataset(num_settlements, payments_per_settlement, seed=42):
    random.seed(seed)

    payments, refunds, settlements, ground_truth = [], [], [], []
    settlement_summary = []
    payment_counter = 1
    refund_counter = 1

    for s_idx in range(1, num_settlements + 1):
        settlement_id = f"SET{s_idx:04d}"
        payment_date = START_DATE + timedelta(days=(s_idx - 1) % 300)
        settlement_date = payment_date + timedelta(days=1)

        naive_expected_total = 0.0
        correct_expected_total = 0.0
        actual_total_all = 0.0
        actual_total_on_time = 0.0

        for _ in range(payments_per_settlement):
            payment_id = f"PAY{payment_counter:05d}"
            order_id = f"ORD{payment_counter:05d}"
            customer_id = f"CUST{random.randint(1, payment_counter // 3 + 50):05d}"
            amount = random.choice([500, 750, 1000, 1500, 2000, 2500, 5000, 10000, 15000])
            method = random.choices(list(PAYMENT_METHODS.keys()), weights=METHOD_WEIGHTS, k=1)[0]
            currency = CURRENCY_BY_METHOD[method]
            label = random.choices(LABELS, weights=LABEL_WEIGHTS, k=1)[0]

            fee_rate = PAYMENT_METHODS[method]
            expected_fee = round(amount * fee_rate, 2)
            expected_gst = round(expected_fee * GST_ON_FEE_RATE, 2)
            base_expected_settlement = round(amount - expected_fee - expected_gst, 2)

            naive_expected_total += amount  # naive analyst counts every order amount

            # ---------------- FAILED_PAYMENT ----------------
            if label == "FAILED_PAYMENT":
                status = "FAILED"
                payments.append([payment_id, order_id, customer_id, amount, currency,
                                  method, GATEWAY, status, payment_date.isoformat(), settlement_id])
                ground_truth.append([settlement_id, payment_id, "NO_ISSUE_FAILED_PAYMENT_EXCLUDED", 0.0, False])
                # correct_expected contributes 0; no settlement row at all
                payment_counter += 1
                continue

            status = "SUCCESS"
            payments.append([payment_id, order_id, customer_id, amount, currency,
                              method, GATEWAY, status, payment_date.isoformat(), settlement_id])

            # ---------------- MISSING_TRANSACTION ----------------
            if label == "MISSING_TRANSACTION":
                correct_expected_total += base_expected_settlement
                ground_truth.append([settlement_id, payment_id, "MISSING_TRANSACTION",
                                      base_expected_settlement, True])
                payment_counter += 1
                continue  # no row in settlements.csv at all

            # ---------------- DELAYED_SETTLEMENT ----------------
            if label == "DELAYED_SETTLEMENT":
                correct_expected_total += base_expected_settlement
                late_date = settlement_date + timedelta(days=random.choice([2, 3, 4]))
                settlements.append([settlement_id, payment_id, base_expected_settlement,
                                     late_date.isoformat(), expected_fee, expected_gst])
                actual_total_all += base_expected_settlement
                # NOT counted in actual_total_on_time since it lands after cutoff
                ground_truth.append([settlement_id, payment_id, "DELAYED_SETTLEMENT",
                                      base_expected_settlement, True])
                payment_counter += 1
                continue

            # ---------------- Refund scenarios ----------------
            if label in ("REFUND_MISMATCH_FULL", "REFUND_MISMATCH_PARTIAL", "REFUND_DELAYED"):
                refund_id = f"REF{refund_counter:05d}"
                refund_counter += 1

                if label == "REFUND_MISMATCH_FULL":
                    refund_amount = amount
                    refunds.append([refund_id, payment_id, "FULL", refund_amount,
                                     payment_date.isoformat(), True])
                    correct_expected = 0.0  # fully refunded -> nothing should settle
                    actual_settled = base_expected_settlement  # bug: paid out anyway
                    reason, amt, is_true = "REFUND_MISMATCH_FULL", round(actual_settled - correct_expected, 2), True

                elif label == "REFUND_MISMATCH_PARTIAL":
                    refund_amount = round(amount * random.choice([0.25, 0.4, 0.5]), 2)
                    refunds.append([refund_id, payment_id, "PARTIAL", refund_amount,
                                     payment_date.isoformat(), True])
                    correct_expected = round(base_expected_settlement - refund_amount, 2)
                    actual_settled = base_expected_settlement  # bug: refund not netted
                    reason, amt, is_true = "REFUND_MISMATCH_PARTIAL", round(actual_settled - correct_expected, 2), True

                else:  # REFUND_DELAYED
                    refund_amount = amount
                    late_refund_date = settlement_date + timedelta(days=random.choice([2, 3]))
                    refunds.append([refund_id, payment_id, "FULL", refund_amount,
                                     late_refund_date.isoformat(), False])
                    # refund hasn't hit cutoff yet -> correctly settles in full, no issue THIS cycle
                    correct_expected = base_expected_settlement
                    actual_settled = base_expected_settlement
                    reason, amt, is_true = "NO_ISSUE_REFUND_DELAYED", 0.0, False

                correct_expected_total += correct_expected
                settlements.append([settlement_id, payment_id, actual_settled,
                                     settlement_date.isoformat(), expected_fee, expected_gst])
                actual_total_all += actual_settled
                actual_total_on_time += actual_settled
                ground_truth.append([settlement_id, payment_id, reason, amt, is_true])
                payment_counter += 1
                continue

            # ---------------- FEE_TAX_MISMATCH ----------------
            if label == "FEE_TAX_MISMATCH":
                wrong_multiplier = random.choice([1.5, 2.0, 2.5])
                actual_fee = round(expected_fee * wrong_multiplier, 2)
                actual_gst = round(actual_fee * GST_ON_FEE_RATE, 2)
                actual_settled = round(amount - actual_fee - actual_gst, 2)

                correct_expected_total += base_expected_settlement
                settlements.append([settlement_id, payment_id, actual_settled,
                                     settlement_date.isoformat(), actual_fee, actual_gst])
                actual_total_all += actual_settled
                actual_total_on_time += actual_settled
                diff = round(base_expected_settlement - actual_settled, 2)
                ground_truth.append([settlement_id, payment_id, "FEE_TAX_MISMATCH", diff, True])
                payment_counter += 1
                continue

            # ---------------- CLEAN ----------------
            correct_expected_total += base_expected_settlement
            settlements.append([settlement_id, payment_id, base_expected_settlement,
                                 settlement_date.isoformat(), expected_fee, expected_gst])
            actual_total_all += base_expected_settlement
            actual_total_on_time += base_expected_settlement
            ground_truth.append([settlement_id, payment_id, "CLEAN", 0.0, False])
            payment_counter += 1

        settlement_summary.append([
            settlement_id, payment_date.isoformat(), settlement_date.isoformat(),
            round(naive_expected_total, 2), round(correct_expected_total, 2),
            round(actual_total_all, 2), round(actual_total_on_time, 2),
            round(correct_expected_total - actual_total_on_time, 2),
        ])

    return payments, refunds, settlements, ground_truth, settlement_summary


def write_csv(filename, header, rows):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=PRESETS.keys(), default="quick")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    cfg = PRESETS[args.preset]
    payments, refunds, settlements, ground_truth, settlement_summary = build_dataset(
        cfg["num_settlements"], cfg["payments_per_settlement"], seed=args.seed
    )

    prefix = f"{args.preset}_"
    write_csv(prefix + "payments.csv",
              ["payment_id", "order_id", "customer_id", "amount", "currency", "payment_method",
               "gateway", "status", "payment_date", "settlement_id"], payments)
    write_csv(prefix + "refunds.csv",
              ["refund_id", "payment_id", "refund_type", "refund_amount", "refund_date",
               "processed_before_cutoff"], refunds)
    write_csv(prefix + "settlements.csv",
              ["settlement_id", "payment_id", "settled_amount", "settlement_date",
               "fee_charged", "tax_charged"], settlements)
    write_csv(prefix + "ground_truth.csv",
              ["settlement_id", "payment_id", "discrepancy_reason", "discrepancy_amount",
               "is_true_discrepancy"], ground_truth)
    write_csv(prefix + "settlement_summary.csv",
              ["settlement_id", "payment_date", "settlement_date", "naive_expected_total",
               "correct_expected_total", "actual_total_all", "actual_total_on_time",
               "discrepancy_total"], settlement_summary)

    true_disc = sum(1 for row in ground_truth if row[4])
    print(f"[{args.preset}] {len(payments)} payments, {len(refunds)} refunds, "
          f"{len(settlements)} settlement rows, {len(ground_truth)} labels "
          f"({true_disc} true discrepancies, {len(ground_truth) - true_disc} non-issues) "
          f"across {cfg['num_settlements']} settlement batches.")


if __name__ == "__main__":
    main()
