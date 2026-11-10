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
    "📈 Calibration (CQR + ACI)",
    "🛡️ Backtest & Trader P&L",
    "📑 Architecture & Competition Dossier"
])

# -------------------------------------------------------------------------------------------------
# Results produced by `python src/backtest.py` (walk-forward on real HARTI data)
# -------------------------------------------------------------------------------------------------
import json, glob
sys.path.append(os.path.join(APP_DIR, "src"))
from decision import break_even, decide

RESULTS_DIR = os.path.join(APP_DIR, "results")
CROPS = ["BEANS", "CARROT", "TOMATO", "LEEKS"]


@st.cache_data
def load_summaries():
    out = {}
    for c in CROPS:
        p = os.path.join(RESULTS_DIR, f"summary_{c.lower()}.json")
        if os.path.exists(p):
            with open(p) as f:
                out[c] = json.load(f)
    return out


@st.cache_data
def load_backtest(c):
    return pd.read_csv(os.path.join(RESULTS_DIR, f"backtest_{c.lower()}.csv"), parse_dates=["date"])


SUMMARIES = load_summaries()
if not SUMMARIES:
    st.error("No results found in results/. Run `python src/backtest.py` first.")
    st.stop()

# -------------------------------------------------------------------------------------------------
# TAB 1: TRADER MORNING ASSISTANT
# -------------------------------------------------------------------------------------------------
with tabs[0]:
    st.subheader("☀️ Morning Decision Screen (06:00 briefing)")
    st.caption("Signals come from the latest HARTI bulletin in prices.db. Change your loan and cost profile "
               "and the decision rule re-runs on the calibrated interval.")

    col_w1, col_w2 = st.columns([2, 1])
    with col_w2:
        st.markdown("### ⚙️ Your loan & cost profile")
        with st.container(border=True):
            r_input = st.slider("Loan interest per trip (%)", 0.0, 5.0, 0.3, 0.1)
            c_input = st.slider("Transport & spoilage (Rs./kg)", 0.0, 40.0, 6.0, 0.5)
            quota_kg = st.number_input("Usual purchase (kg)", 20, 2000, 100, 20)
            r_frac = r_input / 100.0
            st.info(f"Break-even: $B_t = P_t^w(1 + {r_frac:.3f}) + {c_input}$")

    with col_w1:
        any_today = next(iter(SUMMARIES.values()))["today"]["date"]
        st.markdown(f"#### Dambulla → Colombo · bulletin of **{any_today}**")
        styles = {"GREEN": ("card-green", "status-badge-green", "OK TO TRADE"),
                  "AMBER": ("card-amber", "status-badge-amber", "CAUTION: BUY LESS / OWN CASH"),
                  "RED": ("card-red", "status-badge-red", "DO NOT BORROW TODAY")}
        for crop, s in SUMMARIES.items():
            t = s["today"]
            B = break_even(t["wholesale"], r_frac, c_input)
            sig, reason, show = decide(t["L"], t["M"], t["U"], B, t["m_bar"], beta=t.get("beta", 3.0),
                                       breakdown=t["breakdown"], stale=t["stale"])
            card, badge, label = styles[sig]
            rng = f"Rs. {t['L']:.0f} – {t['U']:.0f}/kg" if show else "[HIDDEN]"
            action = {"GREEN": f"Buy your usual {quota_kg} kg.",
                      "AMBER": f"Buy about {quota_kg // 2} kg, with your own cash rather than a loan.",
                      "RED": "Do not take a loan for this crop today. The range is hidden so it can't anchor you."}[sig]
            st.markdown(f"""
            <div class="{card}">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="card-title">{crop.title()} <span class="card-route">· Dambulla → Colombo</span></span>
                <span class="{badge}">{label}</span>
              </div>
              <div style="margin-top:10px;font-weight:600;">Reason: {reason}.</div>
              <div style="margin-top:12px;display:flex;justify-content:space-between;font-size:0.95rem;color:#374151;">
                <span>Dambulla today: <b>Rs. {t['wholesale']:.0f}/kg</b></span>
                <span>Your break-even: <b>Rs. {B:.0f}/kg</b></span>
                <span>Tomorrow, 90% range: <b>{rng}</b></span>
              </div>
              <div style="margin-top:6px;font-size:0.85rem;color:#4B5563;">{action}</div>
            </div>""", unsafe_allow_html=True)

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
        m2.metric("Parsed Bulletins", f"{parsed_bulletins}")
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
                    raw_df[raw_df["market_id"].isin(["DAMBULLA", "PELIYAGODA", "PETTAH"])],
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
# TAB 3: CONFORMAL CALIBRATION
# -------------------------------------------------------------------------------------------------
with tabs[2]:
    st.subheader("📈 Calibration: does the 90% range really contain the price 90% of the time?")
    with st.expander("📐 Formulas (Eq. 2–5)", expanded=False):
        st.markdown(r"""
        1. Pinball loss: $\mathcal{L}_{\tau}(y,\hat y)=\max\{\tau(y-\hat y),(1-\tau)(\hat y-y)\}$, $\tau\in\{0.05,0.5,0.95\}$
        2. CQR score: $s_i=\max\{\hat q_{lo}(x_i)-y_i,\;y_i-\hat q_{hi}(x_i)\}$
        3. ACI: $\alpha_{t+1}=\alpha_t+\gamma(\alpha-\mathbb 1\{y_t\notin C_t\})$
        """)

    crop3 = st.selectbox("Commodity", list(SUMMARIES), key="crop3")
    s3 = SUMMARIES[crop3]
    st.caption(f"Walk-forward test {s3['period'][0]} → {s3['period'][1]} · {s3['eval_days']:,} bulletin days · target 90%")

    rows = [{"Method": k, "Coverage": f"{v['coverage']:.1%}", "Avg width (% of price)": f"{v['width_pct']:.1f}%"}
            for k, v in s3["intervals"].items()]
    st.table(pd.DataFrame(rows))

    st.markdown("#### Coverage by year")
    by_year = pd.DataFrame(s3["coverage_by_year"]).applymap(lambda v: f"{v:.1%}")
    st.dataframe(by_year, use_container_width=True)

    bt = load_backtest(crop3)
    lo_d, hi_d = bt.date.min().date(), bt.date.max().date()
    d0, d1 = st.slider("Window", min_value=lo_d, max_value=hi_d,
                       value=(max(lo_d, pd.Timestamp("2021-07-01").date()), min(hi_d, pd.Timestamp("2023-06-30").date())))
    w = bt[(bt.date.dt.date >= d0) & (bt.date.dt.date <= d1) & bt.y.notna()]
    miss = (w.y < w.L) | (w.y > w.U)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=w.date, y=w.U, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=w.date, y=w.L, fill="tonexty", line=dict(width=0), name="90% ACI range",
                             fillcolor="rgba(22,163,74,0.25)"))
    fig.add_trace(go.Scatter(x=w.date, y=w.y, name="Actual Colombo price", line=dict(color="#111827", width=1)))
    fig.add_trace(go.Scatter(x=w.date[miss], y=w.y[miss], mode="markers", name="Outside range",
                             marker=dict(color="#DC2626", size=6)))
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=30, b=20), yaxis_title="Rs./kg")
    st.plotly_chart(fig, use_container_width=True)
    fig_a = px.line(w, x="date", y="alpha_t", height=200, labels={"alpha_t": "α_t"})
    fig_a.add_hline(y=0.10, line_dash="dash")
    st.plotly_chart(fig_a, use_container_width=True)
    st.caption("When the price escapes the range, α_t drops and the next day's range widens (Eq. 5).")

# -------------------------------------------------------------------------------------------------
# TAB 4: BACKTEST
# -------------------------------------------------------------------------------------------------
with tabs[3]:
    st.subheader("🛡️ Trader P&L backtest (walk-forward, real data)")
    crop4 = st.selectbox("Commodity", list(SUMMARIES), key="crop4")
    s4 = SUMMARIES[crop4]
    rule = st.radio("Decision thresholds", ["tuned", "plan"], horizontal=True,
                    format_func=lambda k: {"tuned": "Tuned on 2016–2019 (used live)",
                                           "plan": "Original plan values"}[k])
    d4 = s4["decision"][rule]
    th, p = d4["thresholds"], s4["params"]
    fmt = lambda v, off: "off" if abs(v) >= 1e8 or v <= -2 else f"{v:g}"
    st.caption(f"Test {s4['period'][0]} → {s4['period'][1]} · {s4['eval_days']:,} days · "
               f"{p['quota_kg']} kg/day · interest {p['r']:.1%}/trip · transport Rs. {p['C']}/kg · "
               f"β = {fmt(th['beta'],1)}, residual z > {fmt(th['z_limit'],1)}, corr < {fmt(th['corr_limit'],1)} · "
               "GREEN = full quota, AMBER = half, RED = none")

    pnl = pd.DataFrame(d4["pnl"]).T
    pnl.columns = ["Total P&L (Rs.)", "Days traded", "Losing days", "Catastrophic (>30% loss)",
                   "Rs. lost in catastrophes", "Worst day (Rs.)"]
    st.dataframe(pnl.style.format({"Total P&L (Rs.)": "{:,.0f}", "Rs. lost in catastrophes": "{:,.0f}",
                                   "Worst day (Rs.)": "{:,.0f}"}), use_container_width=True)

    k1, k2, k3, k4 = st.columns(4)
    rj, lt = d4["refusal_justification_rate"], d4["loss_rate_on_traded_days"]
    k1.metric("RED days that would have lost", f"{rj:.1%}" if rj is not None else "–")
    k2.metric("Loss rate on days it trades", f"{lt:.1%}" if lt is not None else "–")
    k3.metric("Loss rate if you always trade", f"{d4['base_loss_rate']:.1%}")
    k4.metric("Breakdown flagged", f"{d4['breakdown_rate']:.0%} of days")

    sby = pd.DataFrame(d4["signals_by_year"]).T.fillna(0)
    fig_sig = go.Figure()
    for sig, colr in [("GREEN", "#16A34A"), ("AMBER", "#D97706"), ("RED", "#DC2626")]:
        if sig in sby:
            fig_sig.add_trace(go.Bar(x=sby.index.astype(str), y=sby[sig], name=sig, marker_color=colr))
    fig_sig.update_layout(barmode="stack", height=360, margin=dict(l=20, r=20, t=30, b=20),
                          xaxis_title="Year", yaxis_title="Days")
    st.plotly_chart(fig_sig, use_container_width=True)

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
    - 📄 **ModelX_Dataset_Gathering_Guide.pdf** — Multi-source harvesting, cleaning, and SQLite schema specification.
    - 📄 **ModelX_Implementation_Plan.pdf** — Phase 2 engineering roadmap, mathematical derivations, and evaluation metrics.
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6B7280; font-size: 0.85rem;">
    ModelX 2.0 Phase 2 Implementation · Team Model Y · IEEE Computational Intelligence Society Student Chapter, IIT
</div>
""", unsafe_allow_html=True)
