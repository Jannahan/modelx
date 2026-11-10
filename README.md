# Knowing When Not to Trade: Uncertainty-Aware Price Forecasting to Protect Debt-Financed Vegetable Traders in Sri Lanka

[![ModelX 2.0](https://img.shields.io/badge/Competition-ModelX%202.0-006850?style=for-the-badge)](https://modelx2.pages.dev)
[![Domain](https://img.shields.io/badge/Domain%2001-Cost%20of%20living%20%26%20everyday%20economics-10b981?style=for-the-badge)](https://modelx2.pages.dev)
[![Team](https://img.shields.io/badge/Team-Model%20Y%20%7C%20IIT-blue?style=for-the-badge)](https://iit.ac.lk)

> **Official Competition Deliverables:**  
> 📄 **[Download Official 2-Page Technical Report (PDF)](./ModelX_Technical_Report_Two_Page_Summary.pdf)**  
> 🌐 **Live Web Application:** Launch with `run_web.bat` or `run_desktop.bat`  
> 💻 **GitHub Repository:** `https://github.com/Jannahan/modelx`

---

## 1. Executive Summary & Problem Grounding

In Sri Lanka's agricultural supply chain, small vegetable traders borrow daily working capital from informal microfinance lenders at high interest to buy perishable produce before dawn at wholesale hubs (such as the **Dambulla Dedicated Economic Centre - DDEC**) and transport it to Colombo terminal markets (**Peliyagoda Manning Market and Pettah**). 

For a trader who buys at wholesale price $P_t^w$, incurs transport and spoilage cost $C$, and borrows at period interest rate $r$, profit on selling at tomorrow's realized price $P_{t+1}^r$ is:
$$\Pi_t = P_{t+1}^r - P_t^w - C - r\,P_t^w \quad\Longleftrightarrow\quad \text{Break-Even Price: } B_t = P_t^w(1 + r) + C$$

While lenders collect $(1 + r)P_t^w$ unconditionally, the trader carries **100% of downside price volatility**. When market prices crash due to sudden supply inflows, traders suffer debt-financed wipeouts, driving rural workers into severe indebtedness.

### The Model Y Solution
Rather than predicting an overconfident single-point estimate that encourages risky borrowing during volatile periods, **Model Y** produces:
1. **Calibrated 90% Price Intervals ($[L_t, U_t]$):** LightGBM quantile regression at 5th, 50th, and 95th percentiles via pinball loss.
2. **Adaptive Conformal Inference (ACI):** Dynamically updates error rate $\alpha_t$ ($\gamma = 0.02$) to guarantee long-run 90% coverage even during severe non-exchangeable structural shocks (such as the 2022 macroeconomic crisis).
3. **Spatial Breakdown Detection:** Tracks Dambulla-to-Colombo price transmission and flags broken linkages.
4. **Protective 3-Tier Decision Engine:**
   - 🟢 **Green (OK to Trade):** $L_t \ge B_t$ (Even the 5th percentile worst-case price covers loan interest and transport).
   - 🟡 **Amber (Caution: Buy Less / Own Cash):** Median $M_t \ge B_t$ but $L_t < B_t$ (Loss is plausible).
   - 🔴 **Red (Do Not Borrow Today):** $M_t < B_t$, or range too wide, or breakdown flagged. **Hides the point forecast to prevent cognitive anchoring.**

---

## 2. Technical Stack & Architecture

- **Language & Modeling:** Python 3.12, LightGBM (asymmetric quantile pinball loss), MAPIE (conformal benchmarking).
- **Data & Storage:** SQLite with WAL mode (`data/prices.db`), `PyMuPDF` (`fitz`) for sub-second table extraction.
- **Frontend & Desktop:** 
  - **Electron Desktop App** (`run_desktop.bat`) matching modern agricultural farm dashboard aesthetics.
  - **Standalone Responsive Web App** (`ui/index.html`, `run_web.bat`).
  - **Streamlit Analyst App** (`app.py`).

```text
  [HARTI Daily PDFs (2015-2026)] ---> [PyMuPDF Parser] ---> [prices.db SQLite]
                 |                                                 |
  [Open-Meteo Weather & Fuel]                                      v
                                                          [Corridor Features]
                                                                   |
  [Walk-Forward Backtester] <----+---------------------------------+
                 |               |                                 v
                 v               |                       [LightGBM Quantiles]
      [P&L Risk Analytics]       |                                 |
                                 +------------------------> [CQR + ACI Engine]
                                                                   |
                                                            [Breakdown Detector]
                                                                   |
                                                            [Decision Engine]
                                                                   |
                                              +--------------------+--------------------+
                                              |                                         |
                                              v                                         v
                                    [📱 Trader Mobile UI]                    [📊 Analyst Dashboard]
```

---

## 3. Account of Data Used, Temporality & Gaps

> **Status (work in progress):** the full HARTI archive (3,140 English bulletins, Jun 2015 – Nov 2026) is being downloaded and parsed into `prices.db`. This section will be replaced with the final real-data counts and gap report from `src/data_quality.py`.

| Source | Status | Role |
| :--- | :--- | :--- |
| **HARTI Daily Food Bulletin** | Indexed: 3,140 bulletins. Backfill in progress. 3 bulletins return HTTP 404 on HARTI's server (2023-07-29, 2023-08-30, 2023-10-28). | Dambulla wholesale (buy price) and Colombo terminal price (Pettah to 2021, Peliyagoda after) |
| CBSL Daily Price Report | Not collected yet | Planned cross-check |
| Open-Meteo weather | Not collected yet | Planned rainfall features |
| CPC diesel revisions | Not collected yet | Planned transport cost $C_t$ |

---

## 4. Evaluation

> **The numbers below the line were produced on _synthetic_ data** (`src/make_fake_market.py`, `python src/backtest.py --synthetic`). They validate that the CQR + ACI + decision pipeline behaves as designed. They are **not** real-market results. Real walk-forward results on HARTI data (`python src/backtest.py`) will replace them.

Synthetic sanity check, 2,497 simulated days (2019-12 to 2026-10). 90% interval coverage:
Raw LightGBM 73.5% · Naive 86.5% · ARIMA 89.4% · Rolling CQR 89.6% · **CQR + ACI 90.1%**.

---

## 5. Quick Start: How to Run

### Option 1: Run Web Application (Browser)
Double-click `run_web.bat` or run:
```powershell
.\run_web.bat
```
Opens the dashboard at `http://localhost:3000` (or open `ui/index.html` directly in any browser).

### Option 2: Run Electron Desktop App
Double-click `run_desktop.bat` or run:
```powershell
.\run_desktop.bat
```

### Option 3: Run Streamlit Analyst App
```powershell
streamlit run app.py
```

### Option 4: Run Verification Tests
```powershell
python tests/test_harti.py     # 5/5 parser unit tests pass
python src/decision.py         # 6/6 decision engine tests pass
python src/backtest.py         # Run full walk-forward backtest
```

---

## 6. Repository Structure

```text
Implementation/modelx/
├── ModelX_Technical_Report_Two_Page_Summary.pdf   # Official 2-Page Technical Report
├── app.py                                        # Streamlit multi-tab analyst web app
├── package.json                                  # Desktop app configuration
├── requirements.txt                              # Python dependency manifest
├── run_desktop.bat                               # 1-Click Electron desktop launcher
├── run_web.bat                                   # 1-Click Browser web launcher
├── electron/
│   └── main.cjs                                  # Electron main process
├── ui/
│   ├── index.html                                # Dashboard interface
│   ├── styles.css                                # Starline-style design system
│   └── app.js                                    # Simulator & modal controller
├── src/
│   ├── db.py                                     # SQLite prices.db schema
│   ├── harti_scraper.py                          # 2015-2026 archive crawler
│   ├── harti_parser.py                           # PyMuPDF Page 2 table parser
│   ├── build_real_features.py                    # Dambulla-Peliyagoda corridor dataset
│   ├── cqr.py                                    # Conformalized Quantile Regression
│   ├── aci.py                                    # Adaptive Conformal Inference (Eq. 5)
│   ├── verify_mapie.py                           # MAPIE numerical verification
│   ├── breakdown.py                              # Transmission breakdown detector
│   ├── decision.py                               # 3-tier signal & break-even logic
│   └── backtest.py                               # 2019-2026 walk-forward replay
├── tests/
│   └── test_harti.py                             # Unit tests
└── data/
    └── prices.db                                 # Real SQLite price database
```

---

## Team Model Y Sign-Off
- **Tharusha Liyanagama** — Data Pipelines, Scrapers, SQLite Database & UI/Deployment
- **Sethuli Tinara Harischandra** — Feature Engineering, LightGBM Quantile Models & Analyst Views
- **Janakan Jude** — Conformal Calibration (CQR/ACI), Breakdown Detector & Backtest Simulation

*Informatics Institute of Technology (IIT) · IEEE Computational Intelligence Society Student Chapter*
