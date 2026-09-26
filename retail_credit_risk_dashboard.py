import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==================================================================
# DASHBOARD PAGE SETUP
# ==================================================================
st.set_page_config(page_title="Retail Credit Risk Dashboard", layout="wide")

st.title("🏦 Retail Banking Credit Risk Modeling Dashboard")
st.caption(
    "Multi-factor PD/LGD/EAD engine with stress testing. "
    "Educational/illustrative model — not a substitute for a validated internal ratings model."
)
st.markdown("---")

# ==================================================================
# SIDEBAR — INPUTS
# ==================================================================
st.sidebar.header("💳 Applicant Profile")
applicant_name = st.sidebar.text_input("Applicant Name", value="Rahul Sharma")
age = st.sidebar.number_input("Age", min_value=18, max_value=100, value=35)
dependents = st.sidebar.number_input("Number of Dependents", min_value=0, max_value=10, value=1)
employment_type = st.sidebar.selectbox(
    "Employment Type", ["Salaried - Govt/PSU", "Salaried - Private", "Self-Employed", "Unemployed/Informal"]
)
employment_tenure_years = st.sidebar.slider("Employment / Business Tenure (years)", 0.0, 40.0, 4.0, 0.5)

st.sidebar.header("📊 Credit Bureau & Financials")
credit_score = st.sidebar.slider("Credit Score (300 - 850)", 300, 850, 650)
monthly_income = st.sidebar.number_input("Net Monthly Income (₹)", min_value=1000, value=60000, step=1000)
monthly_existing_emi = st.sidebar.number_input("Existing Monthly EMI Obligations (₹)", min_value=0, value=10000, step=500)
num_delinquencies_24m = st.sidebar.number_input("Delinquencies (missed payments) in last 24 months", min_value=0, max_value=50, value=0)

st.sidebar.header("🏗️ Loan Terms")
ead_sanctioned = st.sidebar.number_input("Sanctioned Loan Amount (₹)", min_value=10000, value=500000, step=25000)
loan_tenure_months = st.sidebar.slider("Loan Tenure (months)", 6, 360, 60)
is_revolving = st.sidebar.checkbox("Revolving facility (e.g. credit card / overdraft)?", value=False)
undrawn_pct = 0.0
if is_revolving:
    undrawn_pct = st.sidebar.slider("Currently Undrawn Portion (%)", 0, 100, 40) / 100.0

st.sidebar.header("🔐 Collateral / Recovery")
collateral_type = st.sidebar.selectbox(
    "Collateral Type", ["Unsecured", "Partial (e.g. vehicle/gold)", "Fully Secured (e.g. mortgage)"]
)
collateral_value = 0
if collateral_type != "Unsecured":
    collateral_value = st.sidebar.number_input("Estimated Collateral Value (₹)", min_value=0, value=300000, step=10000)

st.sidebar.header("🌐 Macroeconomic Scenario")
macro_scenario = st.sidebar.selectbox(
    "Scenario", ["Baseline", "Mild Downturn", "Severe Recession"]
)

st.sidebar.header("🛑 Bank Risk Appetite")
max_acceptable_el_rate = st.sidebar.slider("Max Acceptable EL as % of EAD", 0.1, 20.0, 5.0, 0.1) / 100.0

# ==================================================================
# INPUT VALIDATION
# ==================================================================
errors = []
if monthly_income <= 0:
    errors.append("Monthly income must be greater than zero.")
if monthly_existing_emi > monthly_income:
    errors.append("Existing EMI obligations exceed monthly income — figures look inconsistent.")
if collateral_type != "Unsecured" and collateral_value <= 0:
    errors.append("A collateral value greater than zero is required for a secured/partially secured loan.")

if errors:
    for e in errors:
        st.error(e)
    st.stop()

# ==================================================================
# RISK ENGINE
# ==================================================================

# ---- 1. Estimated monthly EMI on the new loan (simple amortization, flat 12% p.a. assumption) ----
annual_rate_assumed = 0.12
r = annual_rate_assumed / 12
n = loan_tenure_months
new_loan_emi = ead_sanctioned * r * (1 + r) ** n / ((1 + r) ** n - 1) if r > 0 else ead_sanctioned / n

# ---- 2. Debt-to-Income ratio (existing + new obligations) ----
dti = (monthly_existing_emi + new_loan_emi) / monthly_income

# ---- 3. Base PD from credit score band (calibrated anchor points) ----
def base_pd_from_score(score: int) -> float:
    if score >= 800:
        return 0.008
    elif score >= 750:
        return 0.02
    elif score >= 700:
        return 0.04
    elif score >= 680:
        return 0.06
    elif score >= 640:
        return 0.10
    elif score >= 600:
        return 0.15
    elif score >= 550:
        return 0.24
    else:
        return 0.35

base_pd = base_pd_from_score(credit_score)

# ---- 4. Multiplicative risk adjustments on top of the score-based base PD ----
# DTI: higher leverage sharply increases default risk
if dti <= 0.30:
    dti_multiplier = 0.85
elif dti <= 0.40:
    dti_multiplier = 1.00
elif dti <= 0.55:
    dti_multiplier = 1.35
else:
    dti_multiplier = 1.90

# Employment stability
employment_multiplier = {
    "Salaried - Govt/PSU": 0.80,
    "Salaried - Private": 1.00,
    "Self-Employed": 1.20,
    "Unemployed/Informal": 2.20,
}[employment_type]

# Tenure at job/business — longer tenure = more stability
if employment_tenure_years >= 5:
    tenure_multiplier = 0.90
elif employment_tenure_years >= 2:
    tenure_multiplier = 1.00
else:
    tenure_multiplier = 1.25

# Recent delinquency history — strong behavioral signal, compounds
delinquency_multiplier = 1.0 + 0.25 * num_delinquencies_24m

# Age effect — very young/very old borrowers carry marginally more uncertainty
if 25 <= age <= 55:
    age_multiplier = 1.00
else:
    age_multiplier = 1.10

# Macro scenario stress on PD (systemic risk overlay)
macro_pd_multiplier = {"Baseline": 1.00, "Mild Downturn": 1.35, "Severe Recession": 2.00}[macro_scenario]

pd_unstressed = base_pd * dti_multiplier * employment_multiplier * tenure_multiplier * delinquency_multiplier * age_multiplier
pd_unstressed = min(pd_unstressed, 0.99)  # cap at 99%
pd_stressed = min(pd_unstressed * macro_pd_multiplier, 0.99)

# ---- 5. LGD — driven by collateral coverage, not a flat assumption ----
if collateral_type == "Unsecured":
    lgd_base = 0.85
elif collateral_type == "Partial (e.g. vehicle/gold)":
    lgd_base = 0.55
else:
    lgd_base = 0.30

coverage_ratio = (collateral_value / ead_sanctioned) if ead_sanctioned > 0 else 0
# Better collateral coverage reduces LGD, but recovery is never assumed to be 100%
collateral_adjustment = max(0.0, 1 - 0.5 * min(coverage_ratio, 1.5))
lgd = np.clip(lgd_base * collateral_adjustment + 0.10, 0.10, 0.95)

# Macro scenario also depresses collateral recovery values (e.g. fire-sale / asset price shock)
macro_lgd_multiplier = {"Baseline": 1.00, "Mild Downturn": 1.10, "Severe Recession": 1.30}[macro_scenario]
lgd_stressed = np.clip(lgd * macro_lgd_multiplier, 0.10, 0.99)

# ---- 6. EAD — apply a Credit Conversion Factor (CCF) to undrawn revolving exposure ----
ccf = 0.75  # Basel-style CCF assumption for undrawn commitments
ead_effective = ead_sanctioned * (1 - undrawn_pct) + ead_sanctioned * undrawn_pct * ccf if is_revolving else ead_sanctioned

# ---- 7. Expected Loss & stressed Expected Loss ----
expected_loss = pd_unstressed * lgd * ead_effective
expected_loss_stressed = pd_stressed * lgd_stressed * ead_effective
worst_case_loss = ead_effective * lgd_stressed  # full write-off exposure under stress
el_rate = expected_loss / ead_effective if ead_effective > 0 else 0

# ---- 8. Simplified regulatory-style capital charge (illustrative Basel IRB retail formula, NOT for compliance use) ----
# Correlation term for retail exposures (simplified constant per Basel retail formula)
rho = 0.15
from scipy.stats import norm
try:
    z = norm.ppf(0.999)
    g_pd = norm.ppf(pd_unstressed) if 0 < pd_unstressed < 1 else 0
    k = lgd * (norm.cdf((g_pd + np.sqrt(rho) * z) / np.sqrt(1 - rho)) - pd_unstressed)
    k = max(k, 0)
    rwa = k * 12.5 * ead_effective
except Exception:
    rwa = np.nan

# ==================================================================
# HEADLINE METRICS
# ==================================================================
st.header(f"🔍 Credit Assessment: {applicant_name}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Probability of Default (PD)", f"{pd_unstressed*100:.2f}%", help="Baseline, unstressed 12-month PD")
with col2:
    st.metric("Loss Given Default (LGD)", f"{lgd*100:.1f}%", help="Adjusted for collateral coverage")
with col3:
    st.metric("Effective EAD", f"₹{ead_effective:,.0f}", help="Sanctioned amount adjusted for CCF on undrawn revolving exposure")
with col4:
    st.metric("Expected Loss (EL)", f"₹{expected_loss:,.2f}", f"{el_rate*100:.2f}% of EAD")

col5, col6, col7 = st.columns(3)
with col5:
    st.metric("Debt-to-Income (DTI)", f"{dti*100:.1f}%", help="Existing EMIs + new loan EMI ÷ net monthly income")
with col6:
    st.metric("Est. New Loan EMI", f"₹{new_loan_emi:,.0f}/mo")
with col7:
    if not np.isnan(rwa):
        st.metric("Illustrative RWA (capital charge base)", f"₹{rwa:,.0f}", help="Simplified Basel IRB-style formula — illustrative only")

st.markdown("---")

# ==================================================================
# DECISION ENGINE
# ==================================================================
decision_col, notes_col = st.columns(2)

with decision_col:
    st.subheader("✅ Underwriting Decision")
    if el_rate <= max_acceptable_el_rate and dti <= 0.55 and num_delinquencies_24m <= 2:
        st.success(
            f"**APPROVED** — Expected loss rate ({el_rate*100:.2f}%) is within the bank's "
            f"appetite ({max_acceptable_el_rate*100:.2f}%), and DTI/delinquency checks pass."
        )
    elif el_rate <= max_acceptable_el_rate * 1.5:
        st.warning(
            "**REFER FOR MANUAL REVIEW** — Borderline risk profile. Consider adjusting loan "
            "amount, tenure, pricing, or requesting additional collateral/guarantor."
        )
    else:
        st.error(
            f"**DECLINED** — Expected loss rate ({el_rate*100:.2f}%) exceeds the bank's "
            f"risk appetite ({max_acceptable_el_rate*100:.2f}%)."
        )

    st.caption(
        "Decision considers: EL vs. risk appetite, DTI ceiling (55%), and recent delinquency count. "
        "This is a rules-of-thumb overlay on top of the EL calculation, not a full policy engine."
    )

with notes_col:
    st.subheader("💡 Risk Committee Notes")
    st.info(
        f"**Stress Test ({macro_scenario}):** Under this scenario, PD rises to "
        f"**{pd_stressed*100:.2f}%** and LGD to **{lgd_stressed*100:.1f}%**, taking stressed "
        f"Expected Loss to **₹{expected_loss_stressed:,.2f}**."
    )
    st.warning(
        f"**Worst-Case Write-off:** If the borrower defaults outright under stress, maximum "
        f"unrecovered exposure is **₹{worst_case_loss:,.2f}**."
    )
    if coverage_ratio < 1.0 and collateral_type != "Unsecured":
        st.caption(f"⚠️ Collateral covers only {coverage_ratio*100:.0f}% of the sanctioned loan amount.")

st.markdown("---")

# ==================================================================
# VISUALS
# ==================================================================
viz1, viz2 = st.columns(2)

with viz1:
    st.subheader("Expected Loss: Baseline vs. Stressed")
    labels = ["Baseline EL", f"{macro_scenario} EL", "Worst-Case Loss"]
    vals = [expected_loss, expected_loss_stressed, worst_case_loss]
    colors = ["#00c0f2", "#ff9f1c", "#ff4b4b"]

    fig1, ax1 = plt.subplots(figsize=(6, 4))
    bars = ax1.bar(labels, vals, color=colors, width=0.55)
    ax1.axhline(max_acceptable_el_rate * ead_effective, color="black", linestyle="--", linewidth=1, label="Risk Appetite Limit")
    ax1.set_ylabel("Amount (₹)")
    ax1.ticklabel_format(style="plain", axis="y")
    ax1.legend(fontsize=8)
    for bar in bars:
        h = bar.get_height()
        ax1.annotate(f"₹{h:,.0f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)
    st.pyplot(fig1)

with viz2:
    st.subheader("PD Sensitivity to Credit Score")
    score_range = np.arange(300, 851, 10)
    pd_curve = [
        base_pd_from_score(s) * dti_multiplier * employment_multiplier * tenure_multiplier
        * delinquency_multiplier * age_multiplier
        for s in score_range
    ]
    pd_curve = np.minimum(pd_curve, 0.99) * 100

    fig2, ax2 = plt.subplots(figsize=(6, 4))
    ax2.plot(score_range, pd_curve, color="#31333f", linewidth=2)
    ax2.axvline(credit_score, color="#ff4b4b", linestyle="--", label=f"Applicant: {credit_score}")
    ax2.set_xlabel("Credit Score")
    ax2.set_ylabel("Probability of Default (%)")
    ax2.legend(fontsize=8)
    st.pyplot(fig2)

st.subheader("Risk Factor Breakdown (multipliers applied to base PD)")
factor_df = pd.DataFrame({
    "Factor": ["Base PD (score band)", "DTI", "Employment Type", "Tenure", "Delinquency History", "Age Band", "Macro Scenario"],
    "Multiplier / Value": [
        f"{base_pd*100:.2f}%", f"×{dti_multiplier:.2f}", f"×{employment_multiplier:.2f}",
        f"×{tenure_multiplier:.2f}", f"×{delinquency_multiplier:.2f}", f"×{age_multiplier:.2f}",
        f"×{macro_pd_multiplier:.2f} (PD) / ×{macro_lgd_multiplier:.2f} (LGD)"
    ],
})
st.dataframe(factor_df, hide_index=True, use_container_width=True)

st.caption(
    "⚠️ **Model limitations:** multipliers and thresholds here are illustrative anchors, not "
    "statistically fitted coefficients. A production model should be calibrated on historical "
    "default data, validated for discriminatory power (e.g. AUC/Gini), monitored for drift, and "
    "reviewed against fair-lending requirements before use in real underwriting decisions."
)
