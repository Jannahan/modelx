# Knowing When Not to Trade

**Uncertainty-aware price forecasting to protect debt-financed vegetable traders in Sri Lanka**

[![ModelX 2.0](https://img.shields.io/badge/Competition-ModelX%202.0-006850?style=for-the-badge)](https://modelx2.pages.dev)
[![Domain](https://img.shields.io/badge/Domain%2001-Cost%20of%20living%20%26%20everyday%20economics-10b981?style=for-the-badge)](https://modelx2.pages.dev)
[![Daily live run](https://github.com/Jannahan/modelx/actions/workflows/daily.yml/badge.svg)](https://github.com/Jannahan/modelx/actions/workflows/daily.yml)

### 📱 Live app: **https://jannahan.github.io/modelx/ui/**  
### 📄 Official Technical Report: **[Download 2-Page Summary (PDF)](./ModelX_Technical_Report_Two_Page_Summary.pdf)**

It updates itself every morning at 06:00 and 10:00 Sri Lanka time from the newest HARTI and CBSL bulletins. On a phone it can be added to the home screen and works offline. It shows a light dashboard on desktop and a dark layout on phones.

Team Model Y (Informatics Institute of Technology): Tharusha Liyanagama · Sethuli Tinara Harischandra · Janakan Jude

---

## 1. The problem

A small trader borrows before dawn, buys vegetables at the **Dambulla Dedicated Economic Centre** at price $P^w_t$, trucks them to the **Colombo terminal market** and sells the next day at $P^r_{t+1}$. With transport and spoilage $C$ (Rs./kg) and loan interest $r$ per trip:

$$\Pi_t = P^r_{t+1} - P^w_t - C - r\,P^w_t \qquad\text{break-even } B_t = P^w_t(1+r) + C$$

The lender is repaid whatever happens. The trader carries all the price risk. **Model Y answers one question every morning, for each crop: should I borrow today?**

| Signal | Rule | What the trader is told |
| :--- | :--- | :--- |
| 🟢 **OK to trade** | 5th-percentile price $L_t \ge B_t$ | Even a bad day covers loan and transport. Buy the usual amount. |
| 🟡 **Buy less, use your own cash** | median $M_t \ge B_t > L_t$ | Profit is likely, but a loss is possible. Buy half. |
| 🔴 **Do not borrow** | $M_t < B_t$, or the route lost money on average over the last 90 days, or prices are more than 4 days old | **The price range is hidden** so it can't anchor the trader. |

### What the app gives each user

**Traders:**
- their own break-even, from their own loan rate and costs (saved on the phone only)
- tomorrow's 90% range on a price ruler
- the chance of selling below break-even
- the last two weeks of prices against the forecast ranges
- how often recent ranges were right
- the Central Bank's latest reason for the price move
- rainfall in the growing areas
- a quick profit calculator

**Lenders, cooperatives and NGOs** (the proposal's secondary user):
- a **market-risk index** across all crops, checked against real losses (§4.5)

**Analysts:**
- calibration over time
- the backtest
- loss rate by interest rate
- the breakdown timeline
- what each data source adds

---

## 2. Data

### Sources (all public)

| Source | Used for | Volume |
| :--- | :--- | :--- |
| **HARTI Daily Food Commodities Bulletin** ([harti.gov.lk](https://www.harti.gov.lk/daily-price.php)) | Main prices: Dambulla wholesale (buy) and Colombo terminal wholesale (sell) | 3,140 listed, **3,097 parsed**, Jun 2015 – Nov 2026. 376,152 price cells |
| **CBSL Daily Price Report** ([cbsl.gov.lk](https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report)) | Second source: cross-check, **supply-reason sentences** shown to traders, and **fallback** when HARTI is late | **2,415 of 2,419 parsed**, Aug 2016 – Nov 2026. 52,060 prices, 4,764 reason sentences |
| **Open-Meteo** ([open-meteo.com](https://open-meteo.com)) | Rain over 3, 7 and 14 days in Nuwara Eliya, Welimada, Bandarawela and Dambulla; temperature | 4 stations × 4,182 days, complete |
| **CBSL USD/LKR indicative rate** | 30-day exchange-rate change (import and inflation pressure) | 2,766 days, Jun 2015 – Nov 2026 |
| **CPC auto-diesel (LAD) price revisions** ([public archive](https://ceypetco.gov.lk/marketing-sales/historical-prices)) | 30-day diesel change and diesel cost relative to the crop price | 99 revisions, 2013 – Nov 2026, e.g. Rs. 95 (2015) → 460 (Jun 2022) → 397 |
| **Calendar** | Days to the next Poya, Poya tomorrow, holiday in the next 2 days, New Year and December seasons, month | Poya computed astronomically (Meeus' full-moon algorithm). The official Poya holiday can fall a day earlier |

**Crops:** Beans, Carrot, Tomato, Leeks and Green Chilli, each with 3,019 aligned days on Dambulla → Colombo. Cabbage was dropped because its HARTI series is too patchy (746 days, ending July 2025).

**Not collected:** WFP monthly prices (the long-run check is done against CBSL instead). The diesel archive is updated by hand when CPC revises prices; it is a public web page, not an API.

### Time handling: no look-ahead

On day $t$ at 06:00 the model knows only:
- today's Dambulla price,
- Colombo prices **up to yesterday**,
- rain and the exchange rate **up to yesterday**,
- the last diesel revision,
- the calendar.

It forecasts the Colombo price on the **next bulletin day**. Every split in `src/walk_forward.py` asserts train < calibration < test.

### Colombo market naming

HARTI headed the Colombo column **"Pettah Market" until 2021 and "Peliyagoda Market" afterwards**, switching back and forth in 2021. It is treated as one Colombo terminal series, and the original label is kept.

### Gaps, reported rather than filled

| Gap | Cause | Handling |
| :--- | :--- | :--- |
| 39 HARTI bulletins return HTTP 404, including most of **February 2017** | Missing at source | Not filled. Listed in `results/data_quality.json` |
| 4 HARTI bulletins (2019) are Sinhala-only in a legacy font | No English labels | Marked `EMPTY` |
| 4 CBSL reports have no price table; 1 failed to download | Source | Skipped |
| **94 days** in 2020 (COVID-19 lockdown); 57 days Oct–Dec 2020; 18 days May–Jun 2021 | No bulletins | No forward-fill. Day-gap is a feature, and a gap over 4 days forces **RED** |
| 28% of HARTI price cells are "–" | No trade that day | Stored as `NULL`, never 0 |
| Leeks are not in CBSL reports | Source coverage | No cross-check and no fallback for Leeks |

### Quality checks (`src/data_quality.py`)

| Check | Result |
| :--- | :--- |
| low ≤ high, zero prices | 0 violations, 0 zeros |
| More than 60% move between bulletins (core corridor) | 390 flagged in `results/flagged_jumps.csv`, **kept** after spot checks |
| **HARTI vs CBSL on the same day** (guide target r ≥ 0.90) | **r = 0.951 – 0.988** over about 2,200 days. Levels differ by 7–12% (range midpoint vs single quote) |

### When HARTI is late: CBSL fallback (proposal §5.3)

If CBSL has published a day that HARTI hasn't yet, the daily run fills that day from CBSL's Dambulla and Pettah wholesale quotes:
- **Scaling:** each crop is scaled by its median HARTI/CBSL ratio over the last 60 shared days.
- **Labelling:** the row is tagged `(CBSL)`, and the app says "prices from CBSL; HARTI not out yet".
- **Replacement:** HARTI's own bulletin replaces the row as soon as it appears.

On 10 Nov 2026 this filled Beans, Carrot, Tomato and Green Chilli. Leeks stayed on the 9th, because it isn't in CBSL.

### Ethics and licensing

- **Sources:** all are public.
- **What the repo contains:** raw PDFs and `prices.db` are not committed (the scrapers rebuild them with polite delays); only derived series in `data/history/` and the results are.
- **Personal data:** none is collected. Traders' costs stay in their own browser.
- **Decision support only:** this is not financial advice. Every screen says ranges are right "about 9 times in 10, not always".

---

## 3. Method

```
HARTI PDFs ─► harti_scraper ─► harti_parser ─┐
CBSL PDFs  ─► cbsl_scraper  ─► cbsl_parser  ─┼─► prices.db ─► data/history/*.csv (tracked)
Open-Meteo, CBSL USD/LKR, CPC diesel, calendar (weather.py, macro.py) ┘         │
                                                                            ▼
           walk_forward ─► LightGBM quantiles τ∈{.05,.5,.95} ─► CQR + ACI (γ = 0.02)
                                                                            │
                     breakdown.py (warning) ─► decision.py: GREEN / AMBER / RED
                                                                            │
     backtest.py ─► results/ ─► risk_index.py ─► export_app_data.py ─► ui/ (live app)
                                                                            ▲
     daily_update.py + GitHub Actions at 06:00 and 10:00 ─► results/last_run.json (run report)
```

- **Features**, all known by 06:00:
  - Colombo/Dambulla ratios at lags 1, 2, 7 and 14
  - the Dambulla change over 1 and 7 bulletins
  - 7-day volatility, weekday, days since the last bulletin
  - rain over 3, 7 and 14 days
  - the calendar features listed above
  - 30-day diesel and USD/LKR changes, and diesel cost relative to the price
- **Quantiles:** LightGBM pinball loss at the 5th, 50th and 95th percentile. It predicts the Colombo/Dambulla ratio and retrains every 30 bulletin days.
- **CQR and ACI:** CQR scores over the last 90 days, plus ACI, $\alpha_{t+1}=\alpha_t+\gamma(\alpha-\mathbb 1\{y_t\notin C_t\})$. `src/verify_mapie.py` shows our CQR is **identical** to MAPIE 1.6 (largest difference 0.0).

---

## 4. Results (walk-forward test 1 Jan 2020 – 8 Nov 2026, 1,971 days per crop)

Reproduce with `python src/backtest.py`. Numbers are in `results/summary_<crop>.json` and the app's Analysis tab.

### 4.1 Is the 90% range honest?

| Method | Beans | Carrot | Tomato | Leeks | Green Chilli | Width (% of price) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Naive (last-90-day ratio quantiles) | 86.3% | 88.0% | 86.1% | 86.8% | 86.5% | 54–71% |
| ARIMA(1,1,1) | 90.6% | 90.2% | 90.1% | 90.4% | 90.1% | 63–79% |
| Raw LightGBM quantiles | 78.1% | 77.6% | 78.3% | 75.7% | 77.0% | 39–48% |
| Rolling CQR (γ = 0) | 89.9% | 89.4% | 90.3% | 89.8% | 89.5% | 55–70% |
| **CQR + ACI (γ = 0.02)** | **90.0%** | **89.9%** | **90.2%** | **90.0%** | **90.0%** | 56–72% |

- **Raw LightGBM is overconfident** (76–78%).
- **CQR + ACI hits 90% on every crop**, including **2022** (89.9–91.4% vs 79.5–83.5% raw).
- **Point accuracy:** the median beats the naive baselines on every crop. For Beans the median error is Rs. 47 per kg, against Rs. 57 for yesterday's Colombo price and Rs. 80 for the same day last week.
- **Caveat:** next-day prices are very volatile, so a calibrated range is about ±30% of the price.

### 4.2 What each data source adds (`results/ablation_features.json`)

| Crop | All features | Without rainfall | Without calendar, diesel, FX, lags 2/14 |
| :--- | :---: | :---: | :---: |
| Beans | 65.0% wide, error Rs. 47.1 | 64.5%, 47.6 | 65.6%, 48.0 |
| Carrot | 56.3%, 32.9 | 55.3%, 33.0 | 56.9%, 32.9 |
| Tomato | **59.1%, 28.5** | 61.0%, 28.8 | 62.1%, 29.3 |
| Leeks | **61.7%, 24.5** | 62.8%, 24.4 | 64.2%, 24.8 |
| Green Chilli | 71.7%, **54.5** | 71.8%, 54.5 | 71.5%, 57.2 |

Coverage is 89.9–90.2% in every column.

- **Calendar, diesel, FX and the extra lags help on every crop.** Ranges are up to 3 points narrower, or the median error is up to Rs. 2.7 lower.
- **Rainfall helps Tomato and Leeks** but slightly widens Beans and Carrot once the other features are present. It's kept for all crops for simplicity, and the result is reported as is.

### 4.3 Decision thresholds were tuned without seeing the test period

The plan's extra RED triggers fired on most days on real data:
- range wider than 3 × the average margin,
- breakdown residual z > 2.5,
- 14-day correlation < 0.35.

Thresholds were therefore **chosen on 2016-07 – 2019-12 only**: one setting shared by all crops, chosen by pooled profit over 140 combinations (`results/tuning_grid.csv`). Tuning switched off the width rule and the breakdown trigger. The breakdown detector still runs as an **advisory warning**.

### 4.4 Would following it have protected a borrower? (100 kg/day, 0.3% interest per trip, Rs. 6/kg)

| Crop | Always trade | Yesterday's spread rule | **Model Y** | Ruinous days (always / spread / **Model Y**) | Worst day (always / **Model Y**) |
| :--- | ---: | ---: | ---: | :---: | :---: |
| Beans | 5,075,938 | 4,494,858 | 2,964,791 | 43 / 28 / **21** | −40,848 / **−12,905** |
| Carrot | **−1,404,118** | 89,319 | **318,952** | 64 / 19 / **2** | −76,155 / **−9,926** |
| Tomato | 6,153,725 | 5,501,877 | 3,226,784 | 17 / 13 / 14 | −15,780 / **−7,890** |
| Leeks | **−1,692,692** | −200,748 | **102,888** | 121 / 35 / **0** | −68,385 / **−3,086** |
| Green Chilli | 1,597,679 | 1,994,036 | 1,325,130 | 80 / 33 / **16** | −45,960 / **−21,657** |
| **All five** | 9,730,532 | 11,879,342 | 7,938,545 | 325 / 128 / **53** | |

A ruinous day loses more than 30% of what was spent.

**Reading this honestly:**
- **Model Y is the only strategy that makes money on all five routes.**
- **It cuts ruinous days from 325 to 53 (−84%)** and the worst single day by 50–95%.
- **On Tomato it has one more ruinous day than the spread rule** (14 vs 13).
- **It earns less than the simple spread rule** (Rs. 7.9M vs 11.9M), because most trades are AMBER (half quantity). It buys safety with profit.
- **Red is on 52.5% of all days.** That is just above the proposal's own warning sign ("red on more than half of days"). It is driven by Carrot (81%) and Leeks (91%), the two routes where always-trading **lost money** over 2020–2026, so refusing there is the right call. Beans is red on 29% of days and Tomato on 7%.
- **Red days are justified.** Loss rate on red days vs an average day:

  | Beans | Carrot | Tomato | Leeks | Green Chilli |
  | :---: | :---: | :---: | :---: | :---: |
  | 61% vs 37% | 65% vs 59% | 40% vs 21% | 67% vs 64% | 59% vs 47% |

  Each crop also reports what red days gave up. For Beans, 39% of red days would have made money (Rs. 0.91M forgone), against Rs. 1.57M of losses avoided.
- **The interest rate where trading stops paying:**
  - about **8.3% per trip** for Beans,
  - **15.5%** for Tomato,
  - **2.5%** for Green Chilli,
  - **never profitable on average** for Carrot and Leeks.

### 4.5 Market-risk index for lenders and NGOs (`results/risk_index.json`)

The index is the average over the five crops of the chance that a typical borrower sells below break-even tomorrow, on a 0–100 scale. Splitting 2020–2026 into five equal groups of days by index value, the share of trades that really lost money rises steadily:

| Index range | 17–40 | 40–44 | 44–48 | 48–52 | 52–74 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Trades that lost | 33.6% | 40.5% | 45.0% | 51.0% | **57.7%** |

So a high index is a usable signal to time lending, relief or member warnings. Daily correlation with the share of losing trades is 0.36.

### 4.6 Breakdown warning before known shocks: our detector vs correlation alone

| Share of the 30 days before the shock that were flagged | Our detector | Correlation alone |
| :--- | :---: | :---: |
| 2022 fuel crisis (Beans / Carrot / Leeks) | 86% / 93% / 71% (2.0× / 1.8× / 1.2× usual) | 54% / 93% / 68% (1.6× / 2.2× / 1.3× usual) |
| 2022 fuel crisis (Tomato / Green Chilli) | 21% / 32% (below usual) | 0% / 29% (below usual) |
| 2020 COVID lockdown (all crops) | below usual (0.2–0.7×) | below usual (0–0.8×) |

**Honest reading:**
- **2022 fuel crisis:** both methods rose beforehand for three of the five crops, and neither clearly beats the other.
- **2020 lockdown:** neither warned. A sudden government shutdown isn't something prices drift towards, so no price-based detector can see it coming.

### 4.7 Synthetic sanity check

`python src/backtest.py --synthetic` runs the same code on simulated prices with a known shock (90.1% coverage). It is only a code check. Earlier drafts of this README presented synthetic numbers as real; they were not.

---

## 5. Plan vs. what was built

| Proposal promise | Status |
| :--- | :--- |
| HARTI + CBSL scrapers and parsers, price store, validation | ✅ Full archives. HARTI vs CBSL cross-check r ≥ 0.95 |
| Weather, FX, fuel, calendar inputs | ✅ Open-Meteo, CBSL USD/LKR, CPC diesel, Poya/holiday calendar. ❌ WFP not used |
| Morning run at 06:00 and 10:00; stale data → red; CBSL ↔ HARTI fallback | ✅ GitHub Actions, run report in `results/last_run.json`, CBSL fallback. (HARTI → CBSL direction is not needed: HARTI is the main source) |
| Features: lags 1/2/7/14, spread, volatility, rain, fuel, FX, calendar | ✅ |
| LightGBM quantiles, CQR + ACI checked against MAPIE | ✅ Identical to MAPIE |
| Breakdown detector, decision rule, hidden forecast on red | ✅ Thresholds tuned on 2016–19; breakdown is advisory |
| Walk-forward backtest with ablations | ✅ 2020–2026 test (2016–19 used for tuning). Ablations: ACI, breakdown rule, rainfall, calendar/fuel/FX/lags |
| Trader app (PWA) with costs on device, card per crop, range scale, last 2 weeks, hit rate | ✅ Live on GitHub Pages |
| Analyst dashboard: calibration, backtest, loss rate by interest rate, breakdown timeline | ✅ In the app (Analysis) and in Streamlit (`app.py`) |
| Aggregate market-risk index for lenders and NGOs | ✅ Validated against real losses |
| FastAPI | ⚠️ No server. The app reads `ui/data/app-data.js`, rebuilt daily, which plays the API's role on free static hosting |
| 4–6 markets | ⚠️ Dambulla → Colombo only (Cut 4) |
| TFT comparison, two-day forecasts, SMS | ❌ Cuts 1–3 |
| Estimate of the number of traders | ❌ Needs contact with the DDEC and Peliyagoda traders' associations |

---

## 6. How to run

```bash
pip install -r requirements.txt
```

```bash
python src/db.py
python -c "import sys; sys.path.insert(0,'src'); from harti_scraper import *; init_db(); sync_bulletins_to_db(fetch_bulletin_index()); run_download_batch()"
python src/harti_parser.py --workers 8
python src/history.py
python src/cbsl_scraper.py
python src/cbsl_parser.py --workers 8
python src/weather.py
python src/macro.py
python src/data_quality.py
python src/backtest.py
python src/risk_index.py
python src/export_app_data.py
```

Daily update (what GitHub Actions runs; needs only the committed CSVs):

```bash
python src/daily_update.py
```

Apps and tests:

```bash
python -m http.server 3000 --directory ui
streamlit run app.py
python tests/test_harti.py
python src/decision.py
python src/verify_mapie.py
```

## 7. Repository layout

```
ui/                          live web app (GitHub Pages, PWA); data/app-data.js is rebuilt daily
app.py                       Streamlit analyst dashboard
.github/workflows/daily.yml  06:00 and 10:00 live run
src/harti_scraper.py  harti_parser.py   HARTI archive + multi-layout parser
src/cbsl_scraper.py   cbsl_parser.py    CBSL archive + position-based table parser
src/weather.py  src/macro.py            Open-Meteo; USD/LKR, diesel, Poya/holiday calendar
src/history.py  src/data_quality.py     committed history; checks, gaps, cross-check
src/walk_forward.py  cqr.py  aci.py  verify_mapie.py  breakdown.py  decision.py
src/backtest.py                         forecasts, baselines, tuning, ablations, P&L
src/risk_index.py                       market-risk index for lenders and NGOs
src/daily_update.py  export_app_data.py live run (with CBSL fallback and run report)
data/history/                           HARTI corridor, CBSL prices + reasons, weather, FX, diesel
results/                                summaries, backtests, live forecasts, risk index, run report
```

## 8. Limitations

- **Coverage:** one route and five crops.
- **Transport cost:** fixed at Rs. 6/kg in the backtest. Diesel is used as a feature, not as a moving cost.
- **Poya days:** astronomical; the official holiday can differ by a day.
- **Thresholds:** tuned on 2016–2019 and should be re-tuned on a rolling window.
- **Data access:** if HARTI and CBSL are both unreachable from GitHub's servers, the app shows the data's real age and turns red after 4 days.
