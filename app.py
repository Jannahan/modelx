import os
import sys
import sqlite3
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Setup paths
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "prices.db")

# Streamlit Page Configuration
st.set_page_config(
    page_title="Model Y — Uncertainty-Aware Vegetable Price Engine",
    page_icon="🥬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #006850;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4A5568;
        margin-bottom: 15px;
    }
    .category-badge {
        display: inline-block;
        background-color: #E6F4EA;
        color: #006850;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 4px 12px;
        border-radius: 16px;
        border: 1px solid #A3D9C9;
        margin-bottom: 12px;
    }
    .card-red {
        background-color: #FEF2F2;
        border: 2px solid #DC2626;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .card-amber {
        background-color: #FFFBEB;
        border: 2px solid #D97706;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .card-green {
        background-color: #F0FDF4;
        border: 2px solid #16A34A;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .card-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .card-route {
        font-size: 0.9rem;
        color: #6B7280;
        font-weight: 500;
    }
    .status-badge-red {
        background-color: #DC2626;
        color: white;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .status-badge-amber {
        background-color: #D97706;
        color: white;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .status-badge-green {
        background-color: #16A34A;
        color: white;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #111827;
    }
</style>
""", unsafe_allow_html=True)

# App Header
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<div class="category-badge">🏷️ ModelX 2.0 · Domain 01: Cost of living and everyday economics</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header">Knowing When Not to Trade</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Uncertainty-Aware Price Forecasting to Protect Debt-Financed Vegetable Traders in Sri Lanka</div>', unsafe_allow_html=True)

with col_h2:
    st.markdown("""
    <div style="text-align: right; font-size: 0.85rem; color: #4B5563; padding-top: 10px;">
        <b>Team Model Y</b><br>
        Informatics Institute of Technology (IIT)<br>
        <i>Tharusha · Sethuli · Janakan</i>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Navigation Tabs
tabs = st.tabs([
    "📱 Trader Morning Assistant",
    "📊 Real Market Explorer (prices.db)",
    "📈 Conformal Calibration & ACI (2022 Crisis)",
    "🛡️ Backtest & Catastrophic Loss Prevention",
    "📑 Architecture & Competition Dossier"
])

# -------------------------------------------------------------------------------------------------
# TAB 1: TRADER MORNING ASSISTANT (FIG 2 WIREFRAME REPLICA)
# -------------------------------------------------------------------------------------------------
with tabs[0]:
    st.subheader("☀️ Daily Morning Decision Screen (06:00 AM Dawn Briefing)")
    st.caption("Customized risk evaluation comparing calibrated price bounds against trader break-even costs before purchasing stock.")

    col_w1, col_w2 = st.columns([2, 1])

    with col_w2:
        st.markdown("### ⚙️ Trader Loan & Cost Profile")
        with st.container(border=True):
            r_input = st.slider("Loan Interest Rate per Trip (%)", min_value=0.0, max_value=2.0, value=0.3, step=0.1, help="Typical informal microfinance or daily loan interest rate")
            c_input = st.slider("Transport & Spoilage Cost (Rs./kg)", min_value=2.0, max_value=20.0, value=6.0, step=0.5, help="Trucking diesel cost + handling & spoilage allowance")
            quota_kg = st.number_input("Purchase Quota (kg)", min_value=20, max_value=2000, value=100, step=20)
            
            r_frac = r_input / 100.0
            st.info(f"Break-even formula: $B_t = P_t^w(1 + {r_frac}) + {c_input}$")

    with col_w1:
        st.markdown("#### Market Signals for Today (Peliyagoda & Pettah Corridors)")

        # Card 1: Beans (RED)
        w_beans = 400.0
        b_beans = w_beans * (1 + r_frac) + c_input
        st.markdown(f"""
        <div class="card-red">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="card-title">Beans <span class="card-route">· Dambulla → Peliyagoda Wholesale</span></span>
                <span class="status-badge-red">DO NOT BORROW TODAY</span>
            </div>
            <div style="margin-top: 10px; font-weight: 600; color: #991B1B;">
                ⚠️ Reason: Dambulla and Peliyagoda prices are out of step this week (breakdown flag active). Forecast is too uncertain.
            </div>
            <div style="margin-top: 12px; display: flex; justify-content: space-between; font-size: 0.95rem; color: #374151;">
                <span>Wholesale Cost: <b>Rs. {w_beans:.2f}/kg</b></span>
                <span>Break-Even: <b>Rs. {b_beans:.2f}/kg</b></span>
                <span style="color: #991B1B;"><b>Range: [HIDDEN]</b></span>
            </div>
            <div style="margin-top: 6px; font-size: 0.8rem; color: #6B7280; font-style: italic;">
                * Point forecast and range are hidden on RED to prevent cognitive anchoring when the trade is statistically unsafe.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Card 2: Carrot (AMBER)
        w_carrot = 240.0
        b_carrot = w_carrot * (1 + r_frac) + c_input
        q_lo_carrot, q_hi_carrot = 235.0, 300.0
        st.markdown(f"""
        <div class="card-amber">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="card-title">Carrot <span class="card-route">· Dambulla → Pettah Terminal</span></span>
                <span class="status-badge-amber">CAUTION: BUY LESS / CASH ONLY</span>
            </div>
            <div style="margin-top: 10px; font-weight: 500; color: #92400E;">
                ⚖️ Reason: Expected median price covers debt, but 5th percentile lower bound falls below break-even. Loss is plausible.
            </div>
            <div style="margin-top: 12px; display: flex; justify-content: space-between; font-size: 0.95rem; color: #374151;">
                <span>Wholesale: <b>Rs. {w_carrot:.2f}/kg</b></span>
                <span>Break-Even: <b>Rs. {b_carrot:.2f}/kg</b></span>
                <span>Calibrated 90% Range: <b>Rs. {q_lo_carrot:.0f} – {q_hi_carrot:.0f}/kg</b></span>
            </div>
            <div style="margin-top: 6px; font-size: 0.8rem; color: #78350F;">
                Suggested action: Reduce purchase volume to {quota_kg//2} kg, or fund exclusively with personal cash reserves (no debt).
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Card 3: Leeks (GREEN)
        w_leeks = 135.0
        b_leeks = w_leeks * (1 + r_frac) + c_input
        q_lo_leeks, q_hi_leeks = 165.0, 195.0
        st.markdown(f"""
        <div class="card-green">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="card-title">Leeks <span class="card-route">· Dambulla → Peliyagoda Wholesale</span></span>
                <span class="status-badge-green">OK TO TRADE</span>
            </div>
            <div style="margin-top: 10px; font-weight: 500; color: #166534;">
                ✅ Reason: Even the worst-case 5th percentile price (Rs. {q_lo_leeks:.0f}) safely covers loan interest and transport costs.
            </div>
            <div style="margin-top: 12px; display: flex; justify-content: space-between; font-size: 0.95rem; color: #374151;">
                <span>Wholesale: <b>Rs. {w_leeks:.2f}/kg</b></span>
                <span>Break-Even: <b>Rs. {b_leeks:.2f}/kg</b></span>
                <span>Calibrated 90% Range: <b>Rs. {q_lo_leeks:.0f} – {q_hi_leeks:.0f}/kg</b></span>
            </div>
            <div style="margin-top: 6px; font-size: 0.8rem; color: #14532D;">
                Suggested action: Buy full standard quota ({quota_kg} kg). Maximum downside bounded by conformal interval.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Interactive Scenario Calculator
    st.markdown("---")
    st.markdown("### 🧮 Interactive Trader P&L Simulator")
    calc_col1, calc_col2, calc_col3, calc_col4 = st.columns(4)

    with calc_col1:
        sel_comm = st.selectbox("Select Commodity", ["Beans", "Carrot", "Leeks", "Tomato"])
    with calc_col2:
        custom_w = st.number_input("Wholesale Buy Price (Rs./kg)", value=float(w_carrot), step=5.0)
    with calc_col3:
        custom_sell = st.number_input("Realized Selling Price (Rs./kg)", value=270.0, step=5.0)
    with calc_col4:
        calc_b = custom_w * (1 + r_frac) + c_input
        profit_total = (custom_sell - calc_b) * quota_kg
        st.metric("Break-Even Threshold", f"Rs. {calc_b:.2f}/kg", delta=f"{custom_sell - calc_b:.2f} Rs/kg margin")

    if profit_total >= 0:
        st.success(f"Estimated Net Trader Profit after paying debt interest ({r_input}%) & transport: **+Rs. {profit_total:,.2f}** on {quota_kg} kg.")
    else:
        st.error(f"Trader Debt Default / Net Loss: **-Rs. {abs(profit_total):,.2f}** on {quota_kg} kg. Model Y warning prevents this loss!")

# -------------------------------------------------------------------------------------------------
# TAB 2: REAL MARKET DATA EXPLORER
# -------------------------------------------------------------------------------------------------
with tabs[1]:
    st.subheader("🏪 Real Price Data Extracted from Official HARTI Bulletins")
    st.caption("Live connection to local SQLite database (`prices.db`) populated directly by `src/harti_scraper.py` and `src/harti_parser.py`.")

    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        
        # Summary counts
        cur = conn.cursor()
        total_bulletins = cur.execute("SELECT count(*) FROM bulletins").fetchone()[0]
        parsed_bulletins = cur.execute("SELECT count(*) FROM bulletins WHERE parse_status = 'PARSED'").fetchone()[0]
        total_obs = cur.execute("SELECT count(*) FROM wholesale_prices").fetchone()[0]
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cataloged Bulletins (2015–2026)", f"{total_bulletins:,}")
        m2.metric("Parsed Sample Bulletins", f"{parsed_bulletins}")
        m3.metric("Extracted Price Rows", f"{total_obs:,}")
        m4.metric("Database Format", "SQLite (WAL Mode)")

        st.markdown("---")

        q_comm = st.selectbox("Filter Commodity", ["BEANS", "CARROT", "TOMATO", "LEEKS", "CABBAGE", "BEET_ROOT"], index=0)
        
        query = """
            SELECT date, market_id, price_low, price_high, price_mid, is_traded
            FROM wholesale_prices
            WHERE commodity_id = ?
            ORDER BY date DESC, market_id ASC
        """
        raw_df = pd.read_sql_query(query, conn, params=(q_comm,))
        conn.close()

        if not raw_df.empty:
            c_chart, c_table = st.columns([3, 2])
            with c_chart:
                st.markdown(f"#### Wholesale Price Movement: {q_comm}")
                fig = px.line(
                    raw_df[raw_df["market_id"].isin(["DAMBULLA", "PELIYAGODA", "KANDY", "MEEGODA"])],
                    x="date", y="price_mid", color="market_id",
                    markers=True,
                    labels={"price_mid": "Wholesale Price (Rs./kg)", "date": "Bulletin Date", "market_id": "Market Hub"},
                    title=f"Wholesale Prices across Dedicated Economic Centres (Rs./kg)"
                )
                fig.update_layout(height=400, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)

            with c_table:
                st.markdown(f"#### Parsed Records ({q_comm})")
                st.dataframe(raw_df, height=380, use_container_width=True)
        else:
            st.warning("No price observations found for this commodity in sample database.")
    else:
        st.error(f"Database not found at {DB_PATH}. Run `python src/db.py` to initialize.")

# -------------------------------------------------------------------------------------------------
# TAB 3: CONFORMAL CALIBRATION & 2022 CRISIS
# -------------------------------------------------------------------------------------------------
with tabs[2]:
    st.subheader("📈 Conformalized Quantile Regression (CQR) & Adaptive Conformal Inference (ACI)")
    st.markdown("""
    Agricultural prices in Sri Lanka are **non-exchangeable** and experience sharp distribution shifts 
    (e.g., COVID market lockdowns in 2020, and the **2022 fertilizer ban + fuel distribution crisis** where inflation exceeded 80%).
    Standard machine learning models fail during shocks. Model Y uses **Adaptive Conformal Inference (ACI)** to maintain coverage guarantees.
    """)

    # Math details
    with st.expander("📐 View Mathematical Formulas (Eq. 2–5 from Proposal)", expanded=False):
        st.markdown(r"""
        1. **LightGBM Quantile Pinball Loss:**
           $$\mathcal{L}_{\tau}(y, \hat{y}) = \max\left\{ \tau(y - \hat{y}), (1 - \tau)(\hat{y} - y) \right\}, \quad \tau \in \{0.05, 0.50, 0.95\}$$
        2. **CQR Nonconformity Score:**
           $$s_i = \max\left\{ \hat{q}_{\text{lo}}(x_i) - y_i,\; y_i - \hat{q}_{\text{hi}}(x_i) \right\}$$
        3. **ACI Online Error Rate Update (Gibbs & Candès, 2021):**
           $$\alpha_{t+1} = \alpha_t + \gamma\left(\alpha - \mathbb{1}\{y_t \notin C_t\}\right)$$
        """)

    # Display 2022 Shock Replay Chart
    st.markdown("### 🌪️ The 2022 Crisis Stress Test")
    fig_path = os.path.join(APP_DIR, "figures", "aci_2022.png")
    if os.path.exists(fig_path):
        st.image(fig_path, caption="Adaptive Conformal Inference (ACI) automatically expanding interval width during the 2022 macroeconomic shock to prevent undercoverage.", use_container_width=True)
    else:
        st.info("Chart figure not found. Run `python src/plot_aci.py` to generate.")

    # Table of Year-by-Year Coverage
    st.markdown("#### Empirical Coverage Comparison Across Regimes")
    cov_data = {
        "Year": ["2020 (Lockdowns)", "2021", "2022 (Macro Crisis)", "2023", "2024", "2025", "2026 (YTD)", "Overall"],
        "Raw LightGBM Coverage": ["71.0%", "75.3%", "57.0% ❌", "75.9%", "83.1%", "78.4%", "81.2%", "74.4%"],
        "Static CQR Coverage": ["91.0%", "90.4%", "83.0% ⚠️", "95.6%", "91.5%", "90.4%", "91.7%", "90.5%"],
        "Model Y (CQR + ACI γ=0.02)": ["91.7%", "88.5%", "89.3% ✅", "91.2%", "89.3%", "89.9%", "90.8%", "90.0%"]
    }
    st.table(pd.DataFrame(cov_data))
    st.caption("ACI successfully restores honest 90% interval coverage even during the unprecedented 2022 macroeconomic shock.")

# -------------------------------------------------------------------------------------------------
# TAB 4: BACKTEST & CATASTROPHIC LOSS ELIMINATION
# -------------------------------------------------------------------------------------------------
with tabs[3]:
    st.subheader("🛡️ Financial Backtest & Downside Risk Protection (2019–2026)")
    st.markdown("""
    Walk-forward simulation over **2,497 trading days** comparing **Model Y** against standard trader heuristic baselines.
    The primary goal is not squeezing extra pennies in calm periods, but **preventing ruinous debt-financed wipeouts**.
    """)

    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    b_col1.metric("Trading Days Evaluated", "2,497")
    b_col2.metric("Catastrophic Losses Avoided", "100%", delta="11 events → 0")
    b_col3.metric("Losing Days Cut", "46 vs 103", delta="-55.3% fewer losses")
    b_col4.metric("Worst Drawdown Reduction", "-Rs. 1,745", delta="+Rs. 4,792 saved")

    # Strategy comparison table
    st.markdown("#### Multi-Year Performance Summary")
    perf_data = {
        "Trading Strategy": ["Always Trade", "Yesterday's Spread Rule", "Model Y (Our System)"],
        "Total Profit (Rs.)": ["Rs. 4,390,901", "Rs. 4,234,874", "Rs. 3,200,604"],
        "Days Traded": [2497, 2329, 2010],
        "Losing Trades": [103, 69, 46],
        "Catastrophic Losses (>30%)": [11, 0, 0],
        "Worst Single-Day Loss": ["-Rs. 6,537", "-Rs. 3,490", "-Rs. 1,745"]
    }
    st.dataframe(pd.DataFrame(perf_data), use_container_width=True)

    # Signal distribution
    st.markdown("#### Signal Distribution Over Time")
    sig_data = pd.DataFrame({
        "Year": [2020, 2021, 2022, 2023, 2024, 2025, 2026],
        "GREEN (Safe to Trade)": [180, 310, 16, 299, 325, 283, 242],
        "AMBER (Caution / Half Quota)": [36, 31, 157, 37, 9, 59, 24],
        "RED (Do Not Borrow)": [150, 24, 192, 29, 32, 23, 37]
    })
    
    fig_sig = go.Figure()
    fig_sig.add_trace(go.Bar(x=sig_data["Year"], y=sig_data["GREEN (Safe to Trade)"], name="GREEN (Trade)", marker_color="#16A34A"))
    fig_sig.add_trace(go.Bar(x=sig_data["Year"], y=sig_data["AMBER (Caution / Half Quota)"], name="AMBER (Caution)", marker_color="#D97706"))
    fig_sig.add_trace(go.Bar(x=sig_data["Year"], y=sig_data["RED (Do Not Borrow)"], name="RED (Do Not Borrow)", marker_color="#DC2626"))
    fig_sig.update_layout(barmode="stack", height=380, margin=dict(l=20, r=20, t=30, b=20), xaxis_title="Year", yaxis_title="Number of Days")
    st.plotly_chart(fig_sig, use_container_width=True)
    st.caption("Notice how in the crisis year 2022, Model Y issued 192 RED signals and 157 AMBER signals, shielding traders from borrowing during supply collapses.")

# -------------------------------------------------------------------------------------------------
# TAB 5: ARCHITECTURE & COMPETITION DOSSIER
# -------------------------------------------------------------------------------------------------
with tabs[4]:
    st.subheader("📑 Project Dossier & System Architecture")

    st.markdown("""
    ### 🏛️ ModelX 2.0 Competition Specification
    - **Competition:** ModelX 2.0 (Powered by Zuu Crew & IEEE CIS Student Chapter, IIT)
    - **Assigned Domain:** **Domain 01: Cost of living and everyday economics**
    - **Problem Statement:** Small vegetable traders in Sri Lanka take on short-term debt to buy wholesale produce at Dambulla without any quantitative measure of whether tomorrow's Colombo selling price will cover loan interest and transport costs.
    - **Team Model Y:**
      - **Tharusha Liyanagama** — Data Pipelines, Web Scrapers, Database Architecture & App Deployment
      - **Sethuli Tinara Harischandra** — Feature Engineering Store, LightGBM Quantiles & Loss-Frequency Analysis
      - **Janakan Jude** — Conformal Prediction (CQR/ACI), Market Breakdown Detector & Walk-Forward Backtester
    """)

    st.markdown("---")
    st.markdown("### 🧩 System Architecture Flow")
    st.code("""
  [HARTI & CBSL Daily PDFs] -----> [Scheduler & Scrapers] -----> [PyMuPDF Parser]
               |                                                       |
  [Open-Meteo Weather & Diesel]                                        v
                                                               [prices.db SQLite]
                                                                       |
  [Walk-Forward Backtester] <----+---- [Feature Store] <---------------+
               |                 |             |
               v                 |             v
     [Risk & P&L Report]         |      [LightGBM Quantiles]
                                 |             |
                                 |             v
                                 +-----> [CQR + ACI Calibrator]
                                               |
                                               v
                                        [Breakdown Detector]
                                               |
                                               v
                                        [Decision Engine]
                                               |
                               +---------------+---------------+
                               |                               |
                               v                               v
                     [📱 Trader Mobile UI]          [📊 Policy Dashboard]
    """, language="text")

    st.markdown("---")
    st.markdown("### 📂 Generated Phase 2 Artifacts & Downloadable Guides")
    st.markdown("""
    - 📄 **[ModelX_Dataset_Gathering_Guide.pdf](file:///d:/Model%20X/ModelX_Dataset_Gathering_Guide.pdf)** — Multi-source harvesting, cleaning, and SQLite schema specification.
    - 📄 **[ModelX_Implementation_Plan.pdf](file:///d:/Model%20X/ModelX_Implementation_Plan.pdf)** — Phase 2 engineering roadmap, mathematical derivations, and evaluation metrics.
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6B7280; font-size: 0.85rem;">
    ModelX 2.0 Phase 2 Implementation · Team Model Y · IEEE Computational Intelligence Society Student Chapter, IIT
</div>
""", unsafe_allow_html=True)
