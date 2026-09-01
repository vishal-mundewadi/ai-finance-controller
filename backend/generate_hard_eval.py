"""
Generates a "hard mode" evaluation dataset by taking a fresh batch of normal
data and deliberately corrupting a small percentage of clean payments
in two realistic, adversarial ways the baseline reconciliation engine
is NOT designed to catch:

1. MINOR_FEE_VARIANCE
   Fee is off by 0.30-0.49 rupees, just under the engine's
   0.50 rupee tolerance.

   For this evaluation, we explicitly treat every non-zero fee
   variance as a TRUE discrepancy under a strict audit policy.
   Therefore, if the engine ignores it because of its tolerance,
   that is counted as a false negative.

2. IMPOSSIBLE_SETTLEMENT_DATE
   Settlement is dated BEFORE the payment date.

   This is a genuine data-integrity problem. The baseline engine
   checks for late settlements but does not currently check for
   impossible settlement dates.

The resulting dataset is a held-out adversarial synthetic evaluation
set containing edge cases that the baseline rules do not explicitly
handle.

Run:
    python generate_hard_eval.py
"""

import random
from datetime import datetime, timedelta

from generate_dataset_v2 import build_dataset, write_csv


FEE_VARIANCE_RATE = 0.08
IMPOSSIBLE_DATE_RATE = 0.05

NUM_SETTLEMENTS = 100
PAYMENTS_PER_SETTLEMENT = 15


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def recompute_settlement_summary(
    payments,
    settlements,
    settlement_summary,
):
    """
    Recalculate summary values after modifying settlement records.

    We preserve the original expected totals because the hard-eval
    corruption changes settlement records, not the underlying payment
    expectations.

    We recalculate:
        actual_total_all
        actual_total_on_time
        discrepancy_total
    """

    # payment_id -> payment row
    payments_by_id = {
        row[0]: row
        for row in payments
    }

    # settlement_id -> list of settlement rows
    settlements_by_batch = {}

    for row in settlements:
        settlement_id = row[0]

        settlements_by_batch.setdefault(
            settlement_id,
            []
        ).append(row)

    for summary in settlement_summary:
        settlement_id = summary[0]

        batch_rows = settlements_by_batch.get(
            settlement_id,
            []
        )

        actual_total_all = round(
            sum(float(row[2]) for row in batch_rows),
            2
        )

        actual_total_on_time = 0.0

        for row in batch_rows:
            payment_id = row[1]

            payment_row = payments_by_id.get(payment_id)

            if payment_row is None:
                continue

            payment_date = parse_date(payment_row[8])
            settlement_date = parse_date(row[3])

            # Settlement is considered on-time when it occurs
            # on or after the payment date.
            if settlement_date >= payment_date:
                actual_total_on_time += float(row[2])

        actual_total_on_time = round(
            actual_total_on_time,
            2
        )

        # summary[5] = actual_total_all
        # summary[6] = actual_total_on_time
        # summary[7] = discrepancy_total
        summary[5] = actual_total_all
        summary[6] = actual_total_on_time

        correct_expected_total = float(summary[4])

        summary[7] = round(
            correct_expected_total - actual_total_on_time,
            2
        )


def main():
    # ---------------------------------------------------------
    # 1. Generate a fresh normal dataset
    # ---------------------------------------------------------

    (
        payments,
        refunds,
        settlements,
        ground_truth,
        settlement_summary,
    ) = build_dataset(
        NUM_SETTLEMENTS,
        PAYMENTS_PER_SETTLEMENT,
        seed=123,
    )

    # ---------------------------------------------------------
    # 2. Build lookup indices
    # ---------------------------------------------------------

    settlements_by_payment = {
        row[1]: i
        for i, row in enumerate(settlements)
    }

    payments_by_id = {
        row[0]: i
        for i, row in enumerate(payments)
    }

    ground_truth_by_payment = {
        row[1]: i
        for i, row in enumerate(ground_truth)
    }

    # ---------------------------------------------------------
    # 3. Find clean payments that have settlements
    # ---------------------------------------------------------

    clean_payment_ids = [
        row[1]
        for row in ground_truth
        if (
            row[2] == "CLEAN"
            and row[1] in settlements_by_payment
        )
    ]

    # Separate deterministic seed for corruption.
    random.seed(999)

    random.shuffle(clean_payment_ids)

    n_fee_variance = int(
        len(clean_payment_ids) * FEE_VARIANCE_RATE
    )

    n_impossible_date = int(
        len(clean_payment_ids) * IMPOSSIBLE_DATE_RATE
    )

    fee_variance_ids = clean_payment_ids[
        :n_fee_variance
    ]

    impossible_date_ids = clean_payment_ids[
        n_fee_variance:
        n_fee_variance + n_impossible_date
    ]

    # ---------------------------------------------------------
    # 4. Inject MINOR_FEE_VARIANCE
    # ---------------------------------------------------------

    for payment_id in fee_variance_ids:

        variance = round(
            random.uniform(0.30, 0.49),
            2,
        )

        settlement_index = settlements_by_payment[
            payment_id
        ]

        # Increase charged fee.
        settlements[settlement_index][4] = round(
            settlements[settlement_index][4] + variance,
            2,
        )

        # Reduce net settled amount by the same amount.
        settlements[settlement_index][2] = round(
            settlements[settlement_index][2] - variance,
            2,
        )

        # Update ground truth.
        gt_index = ground_truth_by_payment[
            payment_id
        ]

        ground_truth[gt_index][2] = (
            "MINOR_FEE_VARIANCE"
        )

        ground_truth[gt_index][3] = variance
        ground_truth[gt_index][4] = True

    # ---------------------------------------------------------
    # 5. Inject IMPOSSIBLE_SETTLEMENT_DATE
    # ---------------------------------------------------------

    for payment_id in impossible_date_ids:

        settlement_index = settlements_by_payment[
            payment_id
        ]

        payment_index = payments_by_id[
            payment_id
        ]

        payment_date = parse_date(
            payments[payment_index][8]
        )

        impossible_date = (
            payment_date
            - timedelta(
                days=random.choice([1, 2])
            )
        )

        settlements[settlement_index][3] = (
            impossible_date.isoformat()
        )

        # Update ground truth.
        gt_index = ground_truth_by_payment[
            payment_id
        ]

        ground_truth[gt_index][2] = (
            "IMPOSSIBLE_SETTLEMENT_DATE"
        )

        ground_truth[gt_index][3] = 0.0
        ground_truth[gt_index][4] = True

    # ---------------------------------------------------------
    # 6. IMPORTANT:
    # Recalculate settlement summary AFTER corruption
    # ---------------------------------------------------------

    recompute_settlement_summary(
        payments,
        settlements,
        settlement_summary,
    )

    # ---------------------------------------------------------
    # 7. Write the hard evaluation dataset
    # ---------------------------------------------------------

    write_csv(
        "hard_eval_payments.csv",
        [
            "payment_id",
            "order_id",
            "customer_id",
            "amount",
            "currency",
            "payment_method",
            "gateway",
            "status",
            "payment_date",
            "settlement_id",
        ],
        payments,
    )

    write_csv(
        "hard_eval_refunds.csv",
        [
            "refund_id",
            "payment_id",
            "refund_type",
            "refund_amount",
            "refund_date",
            "processed_before_cutoff",
        ],
        refunds,
    )

    write_csv(
        "hard_eval_settlements.csv",
        [
            "settlement_id",
            "payment_id",
            "settled_amount",
            "settlement_date",
            "fee_charged",
            "tax_charged",
        ],
        settlements,
    )

    write_csv(
        "hard_eval_ground_truth.csv",
        [
            "settlement_id",
            "payment_id",
            "discrepancy_reason",
            "discrepancy_amount",
            "is_true_discrepancy",
        ],
        ground_truth,
    )

    write_csv(
        "hard_eval_settlement_summary.csv",
        [
            "settlement_id",
            "payment_date",
            "settlement_date",
            "naive_expected_total",
            "correct_expected_total",
            "actual_total_all",
            "actual_total_on_time",
            "discrepancy_total",
        ],
        settlement_summary,
    )

    print(
        f"Generated hard_eval dataset: "
        f"{len(payments)} payments, "
        f"{len(fee_variance_ids)} with minor fee variance, "
        f"{len(impossible_date_ids)} with impossible settlement dates."
    )


if __name__ == "__main__":
    main()