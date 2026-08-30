"""
AI Settlement Investigator — evaluator.

This is the ONLY script that reads ground_truth.csv. The reconciliation
engine never sees it. Run this after reconciliation_engine.py has produced
<preset>_predictions.csv.

Usage:
  python3 evaluate.py --preset quick
"""

import argparse
import csv

# Map the dataset's ground-truth labels onto the engine's (category, subtype) output space
GT_TO_CATEGORY = {
    "MISSING_TRANSACTION": ("MISSING_TRANSACTION", None),
    "DELAYED_SETTLEMENT": ("DELAYED_SETTLEMENT", None),
    "FEE_TAX_MISMATCH": ("FEE_TAX_MISMATCH", None),
    "REFUND_MISMATCH_FULL": ("REFUND_MISMATCH", "FULL"),
    "REFUND_MISMATCH_PARTIAL": ("REFUND_MISMATCH", "PARTIAL"),
    "NO_ISSUE_FAILED_PAYMENT_EXCLUDED": ("NO_ACTION_REQUIRED", "FAILED_PAYMENT_EXCLUDED"),
    "NO_ISSUE_REFUND_DELAYED": ("NO_ACTION_REQUIRED", "REFUND_DELAYED"),
    "CLEAN": ("NO_ACTION_REQUIRED", "CLEAN"),
}


def load_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="quick")
    args = parser.parse_args()

    gt_rows = load_rows(f"{args.preset}_ground_truth.csv")
    pred_rows = load_rows(f"{args.preset}_predictions.csv")

    gt_by_id = {r["payment_id"]: r for r in gt_rows}
    pred_by_id = {r["payment_id"]: r for r in pred_rows}

    tp = fp = fn = tn = 0
    category_correct = 0
    category_total = 0
    mismatches = []

    for payment_id, gt in gt_by_id.items():
        pred = pred_by_id.get(payment_id)
        if pred is None:
            continue  # shouldn't happen if engine covers all payments

        gt_is_true = gt["is_true_discrepancy"] == "True"
        pred_is_true = pred["is_discrepancy"] == "True"

        if gt_is_true and pred_is_true:
            tp += 1
        elif not gt_is_true and pred_is_true:
            fp += 1
        elif gt_is_true and not pred_is_true:
            fn += 1
        else:
            tn += 1

        # Classification accuracy: category (+subtype) correctness, scored for every row
        gt_category, gt_subtype = GT_TO_CATEGORY[gt["discrepancy_reason"]]
        pred_category = pred["category"]
        pred_subtype = pred["subtype"] or None
        category_total += 1
        if pred_category == gt_category and pred_subtype == gt_subtype:
            category_correct += 1
        else:
            mismatches.append({
                "payment_id": payment_id,
                "true_reason": gt["discrepancy_reason"],
                "predicted": f"{pred_category}/{pred_subtype}",
            })

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) and precision == precision and recall == recall else float("nan"))
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else float("nan")
    fpr = fp / (fp + tn) if (fp + tn) else float("nan")
    classification_accuracy = category_correct / category_total if category_total else float("nan")

    print(f"=== Evaluation: {args.preset} ({category_total} payments) ===")
    print(f"Discrepancy Detection Precision : {precision:.3f}")
    print(f"Discrepancy Detection Recall    : {recall:.3f}")
    print(f"Discrepancy Detection F1        : {f1:.3f}")
    print(f"Overall Detection Accuracy      : {accuracy:.3f}")
    print(f"False Positive Rate             : {fpr:.3f}")
    print(f"Category+Subtype Accuracy       : {classification_accuracy:.3f}")
    print(f"(TP={tp} FP={fp} FN={fn} TN={tn})")

    if mismatches:
        print(f"\nFirst {min(5, len(mismatches))} category mismatches (for debugging):")
        for m in mismatches[:5]:
            print(f"  {m['payment_id']}: true={m['true_reason']:35s} predicted={m['predicted']}")


if __name__ == "__main__":
    main()
