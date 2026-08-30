from src.data_loader import load_data

payments, refunds, settlements, settlement_summary = load_data("quick")

print("PAYMENTS")
print(payments.head())

print("\nREFUNDS")
print(refunds.head())

print("\nSETTLEMENTS")
print(settlements.head())

print("\nSETTLEMENT SUMMARY")
print(settlement_summary.head())