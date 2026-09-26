# 🏦 Retail Banking Credit Risk Modeling Dashboard

An interactive Streamlit dashboard demonstrating a multi-factor retail credit risk engine. The application evaluates individual loan applicants using classic credit risk dimensions (**Probability of Default**, **Loss Given Default**, and **Exposure at Default**), applies macroeconomic stress shocks, and simulates Basel IRB-style Risk-Weighted Assets (RWA).

---

## 📌 Features

- **Multi-Factor PD Calibration:** Derives base PD from credit scores (300–850) and scales it using Debt-to-Income (DTI), employment stability, job tenure, prior delinquencies, and borrower age.
- **Dynamic LGD & EAD:**
  - LGD adjusts dynamically based on collateral coverage ratios and security tiers (unsecured, partial, fully secured).
  - EAD calculates effective exposure incorporating a 75% Credit Conversion Factor (CCF) on undrawn revolving facilities.
- **Macroeconomic Stress Engine:** Simulates balance-sheet impacts under **Baseline**, **Mild Downturn**, and **Severe Recession** scenarios.
- **Basel IRB Approximation:** Calculates an illustrative regulatory capital charge base using retail asset-class correlation formulas.
- **Visual Risk Analytics:** Side-by-side charts showing Expected Loss (EL) vs. bank appetite limits and PD sensitivity across the credit score curve.

---

## 🛠️ Project Structure

```text
├── app.py              # Streamlit dashboard application
├── requirements.txt    # Python dependencies
└── README.md           # Documentation
