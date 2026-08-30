import pandas as pd

def load_data(preset="quick"):
    base = f"data/{preset}"
    payments = pd.read_csv(f"{base}/payments.csv")
    refunds = pd.read_csv(f"{base}/refunds.csv")
    settlements = pd.read_csv(f"{base}/settlements.csv")
    settlement_summary = pd.read_csv(f"{base}/settlement_summary.csv")

    return payments, refunds, settlements, settlement_summary