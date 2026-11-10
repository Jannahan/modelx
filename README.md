# Knowing When Not to Trade

**Uncertainty-aware price forecasting to protect debt-financed vegetable traders in Sri Lanka**

[![ModelX 2.0](https://img.shields.io/badge/Competition-ModelX%202.0-006850?style=for-the-badge)](https://modelx2.pages.dev)
[![Domain](https://img.shields.io/badge/Domain%2001-Cost%20of%20living%20%26%20everyday%20economics-10b981?style=for-the-badge)](https://modelx2.pages.dev)
[![Team](https://img.shields.io/badge/Team-Model%20Y%20%7C%20IIT-blue?style=for-the-badge)](https://iit.ac.lk)

Team Model Y (Informatics Institute of Technology): Tharusha Liyanagama · Sethuli Tinara Harischandra · Janakan Jude

---

## 1. The problem

A small trader borrows before dawn, buys vegetables at the **Dambulla Dedicated Economic Centre** at price $P^w_t$, trucks them to the **Colombo terminal market** and sells the next day at $P^r_{t+1}$. With transport and spoilage $C$ (Rs./kg) and loan interest $r$ per trip:

$$\Pi_t = P^r_{t+1} - P^w_t - C - r\,P^w_t \qquad\text{break-even } B_t = P^w_t(1+r) + C$$

The lender is repaid $(1+r)P^w_t$ whatever happens. The trader carries all of the price risk. A single-number forecast hides that risk, so it encourages borrowing on days when the outcome is a coin toss.

**Model Y gives the trader a calibrated 90% range for tomorrow's Colombo price and a three-level signal**, every morning, from public HARTI bulletins:

| Signal | Rule | What the trader is told |
| :--- | :--- | :--- |
| 🟢 **GREEN** | lower bound $L_t \ge B_t$ | Even a bad day (5th percentile) covers loan and transport. Buy the usual quantity. |
| 🟡 **AMBER** | median $M_t \ge B_t > L_t$ | Profit is likely but a loss is plausible. Buy half, with your own cash. |
| 🔴 **RED** | $M_t < B_t$, or the route lost money on average over the last 90 days, or the bulletin is stale | Do not borrow today. **The price range is hidden** so it can't anchor the trader. |

---

## 2. Data: sources, time handling and gaps

### What we collected

| Source | Status | Volume |
| :--- | :--- | :--- |
| **HARTI Daily Food Commodities Bulletin** (English), [harti.gov.lk](https://www.harti.gov.lk/daily-price.php) | ✅ Collected and parsed | 3,140 bulletins listed, Jun 2015 – Nov 2026 · 3,101 downloaded · **3,097 parsed** · **376,152 price cells** |
| CBSL Daily Price Report | ❌ Not collected (planned cross-check) | – |
| Open-Meteo weather, CPC diesel prices, holiday calendar | ❌ Not collected (planned features) | – |

The model uses **only HARTI prices**. Weather, fuel and holiday features from the plan were cut for time. Transport cost $C$ is a fixed Rs. 6/kg, not a diesel-linked series.

### Corridor

**Dambulla wholesale → Colombo terminal**, for **Beans, Carrot, Tomato and Leeks**: 3,019 aligned bulletin days per crop, 22 Jun 2015 – 9 Nov 2026.

HARTI labels the Colombo column **"Pettah Market" up to 2021 and "Peliyagoda Market" afterwards**. In 2021 the label switches back and forth, with 91 days Pettah and 121 Peliyagoda. We treat it as one Colombo terminal series and keep the original label in the `retail_market` column. Both are **wholesale** prices: the trader buys wholesale in Dambulla and sells wholesale in Colombo. We do not have Colombo retail prices.

### Time handling: no look-ahead

On day $t$ at 06:00 the system knows only:
- today's Dambulla price (the trader is standing in the market),
- Colombo prices **up to yesterday**.

It forecasts the Colombo price on the **next bulletin day**. Every split in `src/walk_forward.py` asserts train < calibration < test. The ARIMA baseline is held to the same rule: it makes a 2-step-ahead forecast from yesterday's price.

### Gaps, reported rather than filled

| Gap | Cause | Handling |
| :--- | :--- | :--- |
| **39 bulletins** return HTTP 404 on HARTI's server, including most of **February 2017** (18 days) | Missing at source | Not filled. Listed in `results/data_quality.json` |
| **4 bulletins** (2019) are a single page in a legacy Sinhala font | No English labels to match | Marked `EMPTY` and not guessed |
| **94 days**, 13 Mar – 15 Jun 2020 | COVID-19 lockdown, no bulletins | No forward-fill. Day-gap is a model feature. A gap of more than 4 days triggers **RED** |
| 57 days, Oct – Dec 2020; 18 days, May – Jun 2021 | Later lockdowns | Same |
| 28% of price cells are "–" (no trade) | Market didn't trade that item | Stored as `NULL`, **never 0** |

### Quality checks (`src/data_quality.py`)

| Check | Result |
| :--- | :--- |
| low ≤ high price | 0 violations |
| Zero prices | 0 |
| More than 60% change between bulletins (core corridor) | 265 flagged in `results/flagged_jumps.csv` and **kept**. Spot checks show real moves, e.g. Beans Rs. 175 → 375 after the April New Year closure |

### Parser (`src/harti_parser.py`)

The parser handles every layout from 2015 to 2026:
- the single range cell per market (`"180.00 - 220.00"`)
- the 2022 format with separate **Min/Max columns** and truncated headers ("Dambulla h", "mKappetipola")
- spelling variants ("Petha", "Megoda", "Kappetipola")

It also stops "Long Beans" and "Wing Beans" being read as Beans.

### Ethics and licensing

- **Data source:** HARTI bulletins are public government publications.
- **What the repo contains:** raw PDFs and `prices.db` are **not** committed. Run the scraper (polite 0.4 s delay) to rebuild them. The repo contains only derived corridor series and results.
- **No personal data** is collected.
- **Decision support only:** the tool is not financial advice. On RED it hides the price range to avoid anchoring.

---

## 3. Method

```
HARTI PDFs ──► harti_scraper.py ──► harti_parser.py ──► prices.db (SQLite)
                                                           │
                                     build_real_features.py (Dambulla→Colombo, t-1 features)
                                                           │
            walk_forward.py ──► LightGBM quantiles τ∈{.05,.5,.95} (cqr.py, pinball loss)
                                                           │
                                     CQR + ACI calibration (aci.py, γ = 0.02, 90-day window)
                                                           │
                        breakdown.py (residual + correlation) ─┐
                                                           ▼
                                     decision.py: GREEN / AMBER / RED
                                                           │
                         backtest.py ──► results/*.json ──► app.py (Streamlit)
```

- **Quantile model:** LightGBM predicts the ratio of tomorrow's Colombo price to today's Dambulla price at τ = 0.05, 0.5, 0.95. It retrains every 30 bulletin days on an expanding window. Features: yesterday's Colombo/Dambulla ratio, the Dambulla change since the last bulletin, the 7-bulletin lag, 7-day log volatility, weekday, and days since the last bulletin.
- **CQR:** the conformity score $s_i=\max\{\hat q_{lo}-y_i,\;y_i-\hat q_{hi}\}$ over the last 90 days widens or narrows the interval.
- **ACI** (Gibbs & Candès 2021): $\alpha_{t+1}=\alpha_t+\gamma(\alpha-\mathbb 1\{y_t\notin C_t\})$. After a miss the next range widens.
- **Check against MAPIE:** `src/verify_mapie.py` gives the same trained quantile models to our CQR and to MAPIE 1.6's `ConformalizedQuantileRegressor`. The intervals are **identical**: largest difference 0.0 over 270 test days.

---

## 4. Results on real data (test: 1 Jan 2020 – 8 Nov 2026, 1,971 days per crop)

Reproduce with `python src/backtest.py`. Every number below is in `results/summary_<crop>.json`.

### 4.1 Calibration: does the "90% range" really hold 90% of outcomes?

| Method | Beans | Carrot | Tomato | Leeks | Avg width (% of price) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Naive (last-90-day ratio quantiles) | 86.3% | 88.0% | 86.1% | 86.8% | 54–68% |
| ARIMA(1,1,1) | 90.6% | 90.2% | 90.1% | 90.4% | 63–79% |
| Raw LightGBM quantiles | 79.5% | 79.0% | 79.0% | 76.3% | 40–48% |
| Rolling CQR (γ = 0) | 90.4% | 89.7% | 90.3% | 90.0% | 57–66% |
| **CQR + ACI (γ = 0.02)** | **90.1%** | **89.9%** | **90.0%** | **89.9%** | 57–68% |

- **Raw LightGBM is overconfident.** Its "90%" range contains only 76–80% of outcomes.
- **CQR + ACI reaches the 90% target on all four crops.** It also stays close year by year: Beans ranges from 87.3% (2021) to 94.5% (2020), with **89.9% in the 2022 crisis year**. Raw LightGBM gets 83.2% that year.
- ARIMA is also calibrated but about **5–16 points wider**.
- **Honest caveat:** next-day Colombo prices are very volatile. A calibrated 90% range is about **±30% of the price**, and that width is the main reason GREEN days are rare.

### 4.2 Decision rule: thresholds tuned without seeing the test period

The plan fixed three RED triggers before any data existed:
- interval width > 3 × average margin,
- breakdown residual z > 2.5,
- 14-day correlation < 0.35.

On real data these flagged a breakdown on **29–62% of all days**, and RED fired on 71–100% of days. RED days were no more likely to lose money than an average day, so the signal carried no information.

We therefore **chose the thresholds on 2016-07 – 2019-12 only**: one shared setting for all crops, maximising Model Y's pooled profit (`results/tuning_grid.csv`, 140 combinations). Then we ran the 2020–2026 test untouched.

**Result of tuning:** both the width rule and the breakdown trigger *reduced* profit in 2016–2019, so the tuned rule switches them off. `breakdown.py` still runs, and the plan-threshold results are shown next to the tuned ones in the dashboard.

### 4.3 Trader P&L, 100 kg/day, interest 0.3%/trip, transport Rs. 6/kg (test period)

| Crop | Strategy | Net P&L (Rs.) | Days traded | Catastrophic days (loss > 30% of outlay) | Worst day (Rs.) |
| :--- | :--- | ---: | ---: | ---: | ---: |
| Beans | Always trade | 5,075,938 | 1,971 | 43 | −40,848 |
| | Yesterday's spread | 4,494,858 | 1,301 | 28 | −40,848 |
| | **Model Y** | 2,810,935 | 1,418 | **22** | **−12,905** |
| Carrot | Always trade | **−1,404,118** | 1,971 | 64 | −76,155 |
| | Yesterday's spread | 89,319 | 768 | 19 | −41,140 |
| | **Model Y** | **276,641** | 399 | **4** | **−11,670** |
| Tomato | Always trade | 6,153,725 | 1,971 | 17 | −15,780 |
| | Yesterday's spread | 5,501,877 | 1,566 | 13 | −15,780 |
| | **Model Y** | 3,293,863 | 1,794 | 13 | **−7,890** |
| Leeks | Always trade | **−1,692,692** | 1,971 | 121 | −68,385 |
| | Yesterday's spread | −200,748 | 688 | 35 | −68,385 |
| | **Model Y** | **104,482** | 183 | **1** | **−7,844** |
| **All 4** | Always trade | 8,132,853 | | 245 | |
| | Yesterday's spread | 9,885,306 | | 95 | |
| | **Model Y** | 6,485,921 | | **40** | |

**Reading this honestly:**
- **Model Y is the only strategy that makes money on all four routes.** Always-trade loses Rs. 1.4M on Carrot and Rs. 1.7M on Leeks.
- **It cuts catastrophic days from 245 to 40 (−84%)** and **cuts the worst single-day loss by 50–89%**. That's what protects a borrower from a ruinous day.
- **It earns less in total than the simple "yesterday's spread" rule** (Rs. 6.5M vs 9.9M). Most of its trades are AMBER (half quantity), because the calibrated range is wide. **It buys safety at the cost of profit.** A trader who isn't borrowing may prefer the spread rule.
- **RED is informative after tuning.** On Tomato, 41.8% of RED days lose money against 21.2% on an average day. On Beans it's 59.1% against 36.5%.

### 4.4 Synthetic sanity check

`python src/backtest.py --synthetic` runs the same pipeline on simulated prices with a known 2022 shock (`src/make_fake_market.py`). It reaches 90.1% coverage. Those numbers are **only** a check that the code behaves as designed. Earlier drafts of this README showed them as if they were real; they were not.

---

## 5. Plan vs. what was built

| Plan module | Status |
| :--- | :--- |
| M1 Scraper, parser, SQLite | ✅ Full HARTI archive. ❌ CBSL not scraped. ❌ No daily scheduler (run the scripts manually) |
| M2 Feature store, baselines | ⚠️ Price features only (no weather, fuel or holidays). ✅ Naive and ARIMA baselines |
| M3 LightGBM quantiles | ✅ τ = .05/.5/.95, pinball loss logged in each summary |
| M4 CQR + ACI | ✅ Built. Coverage tested on real data. Matches MAPIE exactly |
| M5 Breakdown + decision rule | ✅ Built. Thresholds tuned on 2016–19; breakdown trigger ends up advisory |
| M6 Walk-forward backtest | ✅ 2020–2026 test, 2022 included, γ = 0 vs ACI comparison, threshold grid |
| M7 Interfaces | ✅ Streamlit dashboard on real results. ⚠️ `ui/` web/Electron app is a **design prototype with illustrative values**. ❌ FastAPI service not built. Not deployed |
| Cut list applied | Cut 1 (TFT), Cut 2 (multi-day), Cut 3 (SMS), Cut 4 (Dambulla → Colombo only) |

---

## 6. How to run

```bash
pip install -r requirements.txt
```

```bash
python src/db.py                            # create prices.db
python src/harti_scraper.py                 # index the HARTI archive and download a sample
python -c "import sys; sys.path.insert(0,'src'); from harti_scraper import run_download_batch; run_download_batch()"   # full archive (~1.5 h)
python src/harti_parser.py --workers 8      # parse all PDFs (~15 min)
python src/data_quality.py                  # gap and quality report -> results/data_quality.json
python src/backtest.py                      # walk-forward, tuning, results/ (~10 min)
streamlit run app.py                        # dashboard
```

```bash
python tests/test_harti.py                  # parser tests
python src/decision.py                      # decision-rule tests
python src/backtest.py --synthetic          # synthetic sanity check
```

`run_web.bat` / `run_desktop.bat` open the design prototype in `ui/`.

## 7. Repository layout

```
app.py                     Streamlit dashboard (reads results/)
src/harti_scraper.py       archive index + polite downloader
src/harti_parser.py        multi-layout PDF table parser (PyMuPDF)
src/db.py                  prices.db schema
src/build_real_features.py Dambulla -> Colombo corridor builder
src/data_quality.py        validation checks and gap report
src/walk_forward.py        leak-free train / calibration / test splits
src/cqr.py  src/aci.py     quantile models, CQR, ACI
src/verify_mapie.py        check against MAPIE
src/breakdown.py           transmission breakdown detector
src/decision.py            break-even and GREEN / AMBER / RED rule
src/backtest.py            forecasts, baselines, threshold tuning, P&L
results/                   summaries, per-day backtests, tuning grid, quality report
tests/                     parser unit tests
ui/  electron/             design prototype (illustrative values)
```

## 8. Limitations

- **Single route, four crops, prices only.** Weather, fuel and supply news would likely narrow the range.
- **Fixed costs.** Transport is a fixed Rs. 6/kg and interest a fixed 0.3% per trip. Real costs vary by trader and season.
- **Colombo side is wholesale.** The trader is assumed to sell at the Colombo wholesale quote, ignoring volume limits and spoilage beyond $C$.
- **Thresholds tuned on 2016–2019.** Markets changed after 2022, so they should be re-tuned periodically on a rolling window.
