import pandas as pd 
import numpy as np
from datetime import datetime, timedelta
import random

# Set seed for reproducibility 
random.seed(42) 
np.random.seed(42)

# Define master transaction archetypes (Business & Household)
transaction_types = [

    # --- HOUSEHOLD TRANSACTIONS ---
    {
        "Scope": "Household", 
        "Category": "Salary / Wages", 
        "Type": "Income", 
        "PL_Impact": "Profit", 
        "BS_Category": "Asset", 
        "DC_Type": "Credit", 
        "Desc": "Monthly salary direct deposit", 
        "Amount_Range": (2500, 6000)
    },
    {
        "Scope": "Household", 
        "Category": "Groceries", 
        "Type": "Expense", 
        "PL_Impact": "Loss", 
        "BS_Category": "Asset", 
        "DC_Type": "Debit", 
        "Desc": "Supermarket purchase (food/supplies)", 
        "Amount_Range": (40, 250)
    },
    {
        "Scope": "Household", 
        "Category": "Rent / Mortgage", 
        "Type": "Expense", 
        "PL_Impact": "Loss", 
        "BS_Category": "Liability", 
        "DC_Type": "Debit", 
        "Desc": "Monthly residential lease/mortgage payment", 
        "Amount_Range": (1000, 2800)
    },
    {
        "Scope": "Household", 
        "Category": "Utilities", 
        "Type": "Expense", 
        "PL_Impact": "Loss", 
        "BS_Category": "Liability", 
        "DC_Type": "Debit", 
        "Desc": "Electricity, water, and gas bills", 
        "Amount_Range": (80, 300)
    },
    {
        "Scope": "Household", 
        "Category": "Dining Out", 
        "Type": "Expense", 
        "PL_Impact": "Loss", 
        "BS_Category": "Asset", 
        "DC_Type": "Debit", 
        "Desc": "Restaurant bill / food delivery", 
        "Amount_Range": (15, 120)
    },
    {
        "Scope": "Household", 
        "Category": "Investment Returns", 
        "Type": "Income", 
        "PL_Impact": "Profit", 
        "BS_Category": "Asset", 
        "DC_Type": "Credit", 
        "Desc": "Stock dividend or savings interest payout", 
        "Amount_Range": (10, 500)
    },
    {
        "Scope": "Household", 
        "Category": "Credit Card Payment", 
        "Type": "Transfer", 
        "PL_Impact": "Neutral", 
        "BS_Category": "Liability", 
        "DC_Type": "Debit", 
        "Desc": "Credit card balance payoff from checking account", 
        "Amount_Range": (200, 1500)
    },
    {
        "Scope": "Household", "Category": "Healthcare / Medical", "Type": "Expense", "PL_Impact": "Loss", "BS_Category": "Asset", "DC_Type": "Debit", "Desc": "Pharmacy prescription / Doctor copay", "Amount_Range": (20, 350)
    },
    {
        "Scope": "Household", "Category": "Vehicle Maintenance", "Type": "Expense", "PL_Impact": "Loss", "BS_Category": "Asset", "DC_Type": "Debit", "Desc": "Gasoline, car insurance, or repairs", "Amount_Range": (35, 600)
    },

    # --- BUSINESS TRANSACTIONS ---

    {
        "Scope": "Business", "Category": "Product Sales Revenue", "Type": "Income", "PL_Impact": "Profit", "BS_Category": "Asset", "DC_Type": "Credit", "Desc": "Direct cash/card sales to customers", "Amount_Range": (150, 4500)
    },
    {
        "Scope": "Business", "Category": "Accounts Receivable Invoicing", "Type": "Income", "PL_Impact": "Profit", "BS_Category": "Asset", "DC_Type": "Credit", "Desc": "Client invoice generated for B2B services rendered", "Amount_Range": (1000, 12000)
    },
    {
        "Scope": "Business", "Category": "Cost of Goods Sold (COGS)", "Type": "Expense", "PL_Impact": "Loss", "BS_Category": "Asset", "DC_Type": "Debit", "Desc": "Raw materials and inventory purchases", "Amount_Range": (200, 5000)
    },
    {
        "Scope": "Business", "Category": "Payroll & Wages", "Type": "Expense", "PL_Impact": "Loss", "BS_Category": "Liability", "DC_Type": "Debit", "Desc": "Employee salaries, benefits, and payroll taxes", "Amount_Range": (3000, 25000)
    },
    {
        "Scope": "Business", "Category": "Office Rent & Lease", "Type": "Expense", "PL_Impact": "Loss", "BS_Category": "Liability", "DC_Type": "Debit", "Desc": "Commercial property rental fee", "Amount_Range": (1500, 6000)
    },
    {
        "Scope": "Business", "Category": "Software / SaaS Subscriptions", "Type": "Expense", "PL_Impact": "Loss", "BS_Category": "Asset", "DC_Type": "Debit", "Desc": "Cloud infrastructure, accounting & CRM tools", "Amount_Range": (29, 800)
    },
    {
        "Scope": "Business", "Category": "Owner's Equity Injection", "Type": "Equity Injection", "PL_Impact": "Neutral", "BS_Category": "Equity", "DC_Type": "Credit", "Desc": "Capital contributed by business owner/investor", "Amount_Range": (5000, 50000)
    },
    {
        "Scope": "Business", "Category": "Owner's Drawings / Distributions", "Type": "Equity Withdrawal", "PL_Impact": "Neutral", "BS_Category": "Equity", "DC_Type": "Debit", "Desc": "Owner cash withdrawal for personal use", "Amount_Range": (1000, 8000)
    },
    {
        "Scope": "Business", "Category": "Bank Loan Principal Payment", "Type": "Transfer", "PL_Impact": "Neutral", "BS_Category": "Liability", "DC_Type": "Debit", "Desc": "Repayment of principal on commercial loan", "Amount_Range": (500, 3500)
    },
    {
        "Scope": "Business", "Category": "Loan Interest Expense", "Type": "Expense", "PL_Impact": "Loss", "BS_Category": "Liability", "DC_Type": "Debit", "Desc": "Interest charge on business debt/credit lines", "Amount_Range": (50, 750)
    },
    {
        "Scope": "Business", "Category": "Equipment Asset Purchase", "Type": "Asset Acquisition", "PL_Impact": "Neutral", "BS_Category": "Asset", "DC_Type": "Debit", "Desc": "Purchase of machinery, computers, or office hardware", "Amount_Range": (800, 7500)
    }
]

# Payment modes & channels
payment_methods = [
    "Checking Account", 
    "Credit Card",
    "Cash", 
    "ACH Transfer", 
    "Wire Transfer", 
    "Digital Wallet"
    ]

# Generate dataset records
num_records = 1200

start_date = datetime(2025, 1, 1)

data=[]

for i in range(1, num_records + 1): 
    txn = random.choice(transaction_types) 
    random_days = random.randint(0, 365) 
    txn_date = start_date + timedelta(days=random_days) 
    amount = round(random.uniform(*txn["Amount_Range"]), 2)

    data.append({ 
        "Transaction_ID": f"TXN-{10000 + i}", 
        "Date": txn_date.strftime("%Y-%m-%d"), 
        "Scope": txn["Scope"], 
        "Category": txn["Category"], 
        "Description": txn["Desc"], 
        "Amount": amount, 
        "Income_vs_Expense": txn["Type"], 
        "Profit_vs_Loss": txn["PL_Impact"], 
        "Balance_Sheet_Category": txn["BS_Category"], 
        "Debit_vs_Credit": txn["DC_Type"], 
        "Payment_Method": random.choice(payment_methods) 
    })

# Convert to DataFrame 
df = pd.DataFrame(data)

# Sort chronologically
df = df.sort_values(by="Date").reset_index(drop=True)

# Save to CSV
df.to_csv("synthetic_financial_dataset_1000.csv", index=False)
print(f"Successfully generated {len(df)} records and saved to 'synthetic_financial_dataset_1000.csv'.")

