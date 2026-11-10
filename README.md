# Knowing When Not to Trade

**Uncertainty-aware price forecasting to protect debt-financed vegetable traders in Sri Lanka**

[![ModelX 2.0](https://img.shields.io/badge/Competition-ModelX%202.0-006850?style=for-the-badge)](https://modelx2.pages.dev)
[![Domain](https://img.shields.io/badge/Domain%2001-Cost%20of%20living%20%26%20everyday%20economics-10b981?style=for-the-badge)](https://modelx2.pages.dev)
[![Daily live run](https://github.com/Jannahan/modelx/actions/workflows/daily.yml/badge.svg)](https://github.com/Jannahan/modelx/actions/workflows/daily.yml)

### 📱 Live app: **https://jannahan.github.io/modelx/ui/**

It updates itself every morning from the newest HARTI and CBSL bulletins. You can add it to a phone's home screen, and it keeps working offline.

Team Model Y (Informatics Institute of Technology): Tharusha Liyanagama · Sethuli Tinara Harischandra · Janakan Jude

---

## 1. The problem

A small trader borrows before dawn, buys vegetables at the **Dambulla Dedicated Economic Centre** at price $P^w_t$, trucks them to the **Colombo terminal market** and sells the next day at $P^r_{t+1}$. With transport and spoilage $C$ (Rs./kg) and loan interest $r$ per trip:

$$\Pi_t = P^r_{t+1} - P^w_t - C - r\,P^w_t \qquad\text{break-even } B_t = P^w_t(1+r) + C$$

The lender is repaid whatever happens. The trader carries all of the price risk. **Model Y answers one question every morning, for each crop: should I borrow today?**

| Signal | Rule | What the trader is told |
| :--- | :--- | :--- |
| 🟢 **OK to trade** | 5th-percentile price $L_t \ge B_t$ | Even a bad day covers loan and transport. Buy the usual amount. |
| 🟡 **Buy less, use your own cash** | median $M_t \ge B_t > L_t$ | Profit is likely, but a loss is possible. Buy half. |
| 🔴 **Do not borrow today** | $M_t < B_t$, or the route lost money on average over the last 90 days, or prices are more than 4 days old | **The price range is hidden** so it can't anchor the trader. |

The app uses **the trader's own** loan rate and transport cost, saved on their phone only, and shows:
- the range on a price ruler with their break-even marked,
- the chance of selling below break-even,
- the last two weeks of prices against the forecast ranges,
- how often recent ranges were right,
- the Central Bank's latest reason for the price move,
- rainfall in the growing areas.

---

## 2. Data

### Sources (all public, all collected)

| Source | What we use it for | Volume |
| :--- | :--- | :--- |
| **HARTI Daily Food Commodities Bulletin** ([harti.gov.lk](https://www.harti.gov.lk/daily-price.php)) | Main prices: Dambulla wholesale (buy) and Colombo terminal wholesale (sell) | 3,140 listed, 3,101 downloaded, **3,097 parsed**, Jun 2015 – Nov 2026. 376,152 price cells |
| **CBSL Daily Price Report** ([cbsl.gov.lk](https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report)) | Second source: cross-checks HARTI, and its one-line **reasons for price moves** are shown to traders | 2,420 listed, 2,419 downloaded, **2,415 parsed**, Aug 2016 – Nov 2026. 52,060 prices, **4,764 supply-reason sentences** |
| **Open-Meteo** ([open-meteo.com](https://open-meteo.com)) | Rainfall over the last 3, 7 and 14 days at Nuwara Eliya, Welimada, Bandarawela (growing areas) and Dambulla, as model features and a trader note | 4 stations × 4,182 days, complete |

**Crops:** Beans, Carrot, Tomato, Leeks and Green Chilli, each with 3,019 aligned bulletin days on Dambulla → Colombo. Cabbage was dropped because its HARTI series is too patchy (746 days, ending July 2025).

**Not collected** (cut for time): WFP monthly prices, the CPC diesel series (transport is a fixed Rs. 6/kg), and a holiday calendar (market gaps are handled directly instead).

### Time handling: no look-ahead

On day $t$ at 06:00 the model knows only:
- today's Dambulla price,
- Colombo prices **up to yesterday**,
- rainfall **up to yesterday**.

It forecasts the Colombo price on the **next bulletin day**. Every split in `src/walk_forward.py` asserts train < calibration < test. The ARIMA baseline is held to the same rule (a 2-step forecast).

### Colombo market naming

HARTI's Colombo column is headed **"Pettah Market" until 2021 and "Peliyagoda Market" afterwards**, and switches back and forth during 2021 (91 days Pettah, 121 Peliyagoda). We treat it as one Colombo terminal series and keep the original label in `retail_market`.

### Gaps, reported rather than filled

| Gap | Cause | Handling |
| :--- | :--- | :--- |
| 39 HARTI bulletins return HTTP 404, including most of **February 2017** | Missing at source | Not filled. Listed in `results/data_quality.json` |
| 4 HARTI bulletins (2019) are Sinhala-only in a legacy font | No English labels | Marked `EMPTY`, not guessed |
| 4 CBSL reports have no price table; 1 failed to download (2022-09-14) | Source | Skipped |
| **94 days**, 13 Mar – 15 Jun 2020 (COVID-19 lockdown); 57 days Oct–Dec 2020; 18 days May–Jun 2021 | No bulletins | No forward-fill. Day-gap is a model feature, and a gap over 4 days forces **RED** |
| 28% of HARTI price cells are "–" | No trade that day | Stored as `NULL`, **never 0** |
| Leeks are not in CBSL reports; Green Chilli appears there from 2021 | Source coverage | Cross-check only where both exist |

### Quality checks (`src/data_quality.py`)

| Check (Dataset Gathering Guide §7) | Result |
| :--- | :--- |
| low ≤ high | 0 violations |
| Zero prices | 0 |
| More than 60% move between bulletins (core corridor) | 390 flagged in `results/flagged_jumps.csv` and **kept**. Spot checks show real moves, e.g. after the April New Year closure |
| **HARTI vs CBSL on the same day** (guide target r ≥ 0.90) | **r = 0.951 – 0.988** over about 2,200 matching days for Beans, Carrot, Tomato and Green Chilli. The typical level difference is 7–12% (HARTI quotes the midpoint of a range, CBSL a single price) |

### Parsing

Both parsers handle every layout from 2015 to 2026:
- **HARTI** (`src/harti_parser.py`):
  - range cells (`"180.00 - 220.00"`), and the 2022 min/max columns with truncated headers,
  - spelling variants ("Petha", "Megoda", "Kappetipola"),
  - "Long Beans" and "Wing Beans" are not read as Beans.
- **CBSL** (`src/cbsl_parser.py`):
  - its table changed column order three times (by market in 2016, by wholesale/retail from 2019, Narahenpita added from 2020), so numbers are matched to headers **by position on the page**, never by a fixed order.

### Ethics and licensing

- **Sources:** all are free, public government or open-data sources.
- **What the repo contains:** raw PDFs and `prices.db` are not committed; the scrapers rebuild them with polite delays. The repo holds only the derived series in `data/history/` (about 4.5 MB) and results.
- **Personal data:** none is collected. A trader's loan rate and costs stay in their own browser.
- **Decision support only:** this is not financial advice. Every screen says ranges are right "about 9 times in 10, not always".

---

## 3. Method

```
HARTI PDFs ─► harti_scraper ─► harti_parser ─┐
CBSL PDFs  ─► cbsl_scraper  ─► cbsl_parser  ─┼─► prices.db ─► data/history/*.csv (tracked)
Open-Meteo ─► weather.py ────────────────────┘                     │
                                                                   ▼
        walk_forward ─► LightGBM quantiles τ∈{.05,.5,.95} (+ rain features)
                                       │
                         CQR + ACI calibration (γ = 0.02, 90-day window)
                                       │
                 breakdown.py (advisory) ─► decision.py: GREEN / AMBER / RED
                                       │
        backtest.py ─► results/ ─► export_app_data.py ─► ui/ (live web app)
                                       ▲
        daily_update.py + GitHub Actions, 06:00 and 10:00 Sri Lanka time
```

- **Quantile model:** LightGBM predicts tomorrow's Colombo price as a ratio to today's Dambulla price. It retrains every 30 bulletin days. Features:
  - yesterday's Colombo/Dambulla ratio
  - the Dambulla change since the last bulletin
  - the 7-bulletin lag
  - 7-day volatility
  - weekday
  - days since the last bulletin
  - rain over 3, 7 and 14 days in the growing areas
- **CQR:** the score $s_i=\max\{\hat q_{lo}-y_i,\;y_i-\hat q_{hi}\}$ over the last 90 days widens or narrows the range.
- **ACI** (Gibbs & Candès 2021): $\alpha_{t+1}=\alpha_t+\gamma(\alpha-\mathbb 1\{y_t\notin C_t\})$.
- **Check against MAPIE:** `src/verify_mapie.py` gives the same quantile models to our CQR and to MAPIE 1.6. The intervals are **identical** (largest difference 0.0 over 270 test days).

---

## 4. Results (walk-forward test 1 Jan 2020 – 8 Nov 2026, 1,971 days per crop)

Reproduce with `python src/backtest.py`. Every number is in `results/summary_<crop>.json`, and the app's Analysis tab shows them per crop.

### 4.1 Is the 90% range honest?

| Method | Beans | Carrot | Tomato | Leeks | Green Chilli | Width (% of price) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Naive (last-90-day ratio quantiles) | 86.3% | 88.0% | 86.1% | 86.8% | 86.5% | 54–71% |
| ARIMA(1,1,1) | 90.6% | 90.2% | 90.1% | 90.4% | 90.1% | 63–79% |
| Raw LightGBM quantiles | 78.5% | 77.5% | 78.1% | 76.1% | 78.0% | 39–48% |
| Rolling CQR (γ = 0) | 90.0% | 89.9% | 89.9% | 90.2% | 89.6% | 56–69% |
| **CQR + ACI (γ = 0.02)** | **90.0%** | **89.9%** | **90.2%** | **90.0%** | **90.0%** | 57–71% |

- **Raw LightGBM is overconfident.** Its "90%" range holds only 76–79% of outcomes.
- **CQR + ACI hits the target on every crop**, including **2022**, the crisis year: 88.1–91.1% against 78.6–83.2% for raw LightGBM.
- ARIMA is also calibrated, but its ranges are wider.
- **Point accuracy** (median error, Rs./kg): LightGBM beats both naive baselines on all five crops. For Beans it's 48 vs 57 (yesterday's price) and 80 (same day last week).
- **Rainfall helps a little.** With the Open-Meteo features, ranges are 0.6–2.3 points narrower and median error slightly lower for Beans, Carrot and Tomato, at the same coverage. It makes no real difference for Leeks or Green Chilli (`results/ablation_weather.json`).
- **Honest caveat:** next-day prices are very volatile. A calibrated 90% range is about ±30% of the price, which is why GREEN days are rare.

### 4.2 Decision thresholds were tuned without seeing the test period

The plan fixed three extra RED triggers before any data existed:
- range wider than 3 × the average margin,
- breakdown residual z > 2.5,
- 14-day correlation < 0.35.

On real data they fired on most days, and RED carried no information. So the thresholds were **chosen on 2016-07 – 2019-12 only**: one shared setting for all crops, maximising pooled profit over 140 combinations (`results/tuning_grid.csv`, `results/thresholds.json`). Then 2020–2026 was tested untouched.

Tuning switched off both the width rule and the breakdown trigger. **The breakdown detector still runs as an advisory warning in the app.**

- **Beans, Carrot, Leeks:** it rose before the 2022 fuel crisis, flagging 71–93% of the 30 days before it against a usual 42–60%.
- **Tomato and Green Chilli:** it did not rise (21–32% against a usual 32–46%).

### 4.3 Would following it have protected a borrower? (100 kg/day, 0.3% interest per trip, Rs. 6/kg transport)

| Crop | Always trade | Yesterday's spread rule | **Model Y** | Ruinous days (always / spread / **Model Y**) | Worst day (always / **Model Y**) |
| :--- | ---: | ---: | ---: | :---: | :---: |
| Beans | 5,075,938 | 4,494,858 | 3,085,309 | 43 / 28 / **20** | −40,848 / **−12,905** |
| Carrot | **−1,404,118** | 89,319 | **315,368** | 64 / 19 / **2** | −76,155 / **−7,894** |
| Tomato | 6,153,725 | 5,501,877 | 3,293,189 | 17 / 13 / **12** | −15,780 / **−7,890** |
| Leeks | **−1,692,692** | −200,748 | **101,495** | 121 / 35 / **2** | −68,385 / **−4,086** |
| Green Chilli | 1,597,679 | 1,994,036 | 1,220,482 | 80 / 33 / **16** | −45,960 / **−17,980** |
| **All five** | 9,730,532 | 11,879,342 | 8,015,843 | 325 / 128 / **52** | |

A "ruinous day" loses more than 30% of the money spent.

**Reading this honestly:**
- **Model Y is the only strategy that makes money on all five routes.** Always-trade loses Rs. 1.4M on Carrot and Rs. 1.7M on Leeks.
- **Ruinous days fall from 325 to 52 (−84%)**, and the worst single day is 50–94% smaller.
- **It earns less than the simple spread rule** (Rs. 8.0M vs 11.9M). Most trades are AMBER (half quantity) because the honest range is wide. It buys safety with profit, which suits someone repaying a loan.
- **RED days are justified.** Loss rate on RED days vs an average day:

  | Beans | Carrot | Tomato | Leeks | Green Chilli |
  | :---: | :---: | :---: | :---: | :---: |
  | 62% vs 37% | 65% vs 59% | 43% vs 21% | 67% vs 64% | 59% vs 47% |

  The price of safety is also reported: for Beans, 38% of RED days would have made money (Rs. 0.86M forgone), against Rs. 1.51M of losses avoided.
- **The interest rate where trading stops paying:**
  - about **8.3% per trip** for Beans,
  - **15.5%** for Tomato,
  - **2.5%** for Green Chilli,
  - **never profitable on average** for Carrot and Leeks, even at 0%.

### 4.4 Synthetic sanity check

`python src/backtest.py --synthetic` runs the same code on simulated prices with a known 2022 shock and reaches 90.1% coverage. It is only a check that the code behaves as designed. Earlier drafts of this README presented synthetic numbers as real; they were not.

---

## 5. Plan vs. what was built

| Plan module | Status |
| :--- | :--- |
| M1 Scrapers, parsers, price store | ✅ HARTI full archive. ✅ CBSL full archive. ✅ Open-Meteo. ✅ **Scheduler: GitHub Actions at 06:00 and 10:00** |
| M2 Features, baselines | ✅ Price lags, volatility, gaps, rainfall. ✅ Naive, seasonal-naive, ARIMA. ⚠️ No diesel/FX/holiday features |
| M3 LightGBM quantiles | ✅ τ = .05/.5/.95, pinball loss and MAE reported |
| M4 CQR + ACI | ✅ Matches MAPIE exactly. Coverage tested per crop and per year |
| M5 Breakdown + decision rule | ✅ Built. Thresholds tuned on 2016–19. Breakdown flag is advisory |
| M6 Walk-forward backtest | ✅ 2020–2026 test, 2022 included. Ablations: γ = 0 vs ACI, with/without rain, plan vs tuned thresholds. Profit at 7 interest rates |
| M7 Interfaces | ✅ **Live mobile web app (PWA) on GitHub Pages.** ✅ Streamlit analyst dashboard (`app.py`). ⚠️ No FastAPI server: the static app reads `ui/data/app-data.js`, which plays the API's role |
| Cut list applied | Cut 1 (TFT), Cut 2 (multi-day), Cut 3 (SMS), Cut 4 (Dambulla → Colombo only) |

---

## 6. How to run

```bash
pip install -r requirements.txt
```

Full rebuild from the sources:

```bash
python src/db.py                              # create prices.db
python -c "import sys; sys.path.insert(0,'src'); from harti_scraper import *; init_db(); sync_bulletins_to_db(fetch_bulletin_index()); run_download_batch()"   # HARTI (~1.5 h)
python src/harti_parser.py --workers 8        # ~15 min
python src/history.py                         # -> data/history/harti_corridor.csv
python src/cbsl_scraper.py                    # CBSL (~45 min)
python src/cbsl_parser.py --workers 8         # -> data/history/cbsl_*.csv
python src/weather.py                         # -> data/history/weather_daily.csv
python src/data_quality.py                    # gaps, checks, HARTI vs CBSL cross-check
python src/backtest.py                        # walk-forward, tuning, ablations (~15 min)
python src/export_app_data.py                 # -> ui/data/app-data.js
```

Daily update (what GitHub Actions runs; needs only the committed CSVs):

```bash
python src/daily_update.py
```

Apps and tests:

```bash
python -m http.server 3000 --directory ui     # web app at http://localhost:3000
streamlit run app.py                          # analyst dashboard
python tests/test_harti.py                    # parser tests
python src/decision.py                        # decision-rule tests
python src/verify_mapie.py                    # CQR vs MAPIE
```

## 7. Repository layout

```
ui/                        live trader web app (GitHub Pages), PWA, data/app-data.js
app.py                     Streamlit analyst dashboard
.github/workflows/daily.yml  06:00 and 10:00 live run
src/harti_scraper.py  src/harti_parser.py   HARTI archive + multi-layout parser
src/cbsl_scraper.py   src/cbsl_parser.py    CBSL archive + position-based table parser
src/weather.py             Open-Meteo rainfall
src/history.py             committed corridor history (data/history/)
src/data_quality.py        validation checks, gaps, HARTI vs CBSL cross-check
src/walk_forward.py  src/cqr.py  src/aci.py  src/verify_mapie.py
src/breakdown.py  src/decision.py
src/backtest.py            forecasts, baselines, tuning, ablations, P&L
src/daily_update.py  src/export_app_data.py
data/history/              HARTI corridor, CBSL prices + reasons, weather (tracked)
results/                   summaries, per-day backtests, live forecasts, quality report
```

## 8. Limitations

- **One route, five crops.** Diesel, FX and holiday features from the plan were not added.
- **Fixed backtest costs.** Rs. 6/kg and 0.3%/trip. The app uses each trader's own costs, but the backtest doesn't.
- **Wholesale both ends.** The trader is assumed to sell at the Colombo wholesale quote, ignoring volume limits.
- **Re-tune periodically.** Thresholds were tuned on 2016–2019 and markets changed after 2022, so they should be re-tuned on a rolling window.
- **Daily run depends on the sources.** If HARTI or CBSL is unreachable from GitHub's servers, the app shows the data's real age and turns RED after 4 days.
