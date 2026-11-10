# ModelX 2.0 — Team Model Y

Uncertainty-aware vegetable price forecasting and trade-decision engine.

## Data Engineering modules (M1–M2) — Tharusha

| File | Module | What it does |
|---|---|---|
| `src/db.py` | M1/M2 | SQLite schema (`data/prices.db`) for bulletins, commodities, markets, and prices |
| `src/harti_scraper.py` | M1 | Scrapes index (3,141 bulletins, 2015–2026) and batch downloads PDF reports |
| `src/harti_parser.py` | M1 | PyMuPDF table parser for Page 2 wholesale tables; canonical entity mapping |
| `src/build_real_features.py` | M2 | Builds Dambulla → Peliyagoda corridor dataset with lags, spreads, and rolling margins |
| `tests/test_harti.py` | M1 | Unit tests for price range parsing and canonical name resolution |

## Jude's modules (M4–M6)

| File | Module | What it does |
|---|---|---|
| `src/walk_forward.py` | M6 | Train / calibration / test splits with no look-ahead |
| `src/cqr.py` | M4 | Conformalized Quantile Regression (Eq. 3–4) |
| `src/aci.py` | M4 | Adaptive Conformal Inference (Eq. 5), rolling 90-day window |
| `src/verify_mapie.py` | M4 | Checks our CQR against MAPIE (exact match) |
| `src/breakdown.py` | M5 | Market breakdown detector (Eq. 6) |
| `src/decision.py` | M5 | Break-even price and Green / Amber / Red rule |
| `src/backtest.py` | M6 | Full walk-forward backtest vs. benchmark strategies |

## How to run (synthetic data)

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install numpy pandas lightgbm mapie matplotlib
python src/make_fake_data.py
python src/cqr.py
python src/aci.py
python src/verify_mapie.py
python src/make_fake_pair.py
python src/breakdown.py
python src/make_fake_market.py
python src/backtest.py
```

## Design decisions (beyond the Phase 2 plan)

1. **Models predict a ratio, not the raw price** (tomorrow's price ÷ today's
   price). Tree models cannot predict values outside their training range.
2. **Symmetric CQR**, matching Eq. 3–4. MAPIE's default is asymmetric, so the
   check uses `symmetric_correction=True`.
3. **ACI uses a rolling 90-day window**, updated daily. γ = 0.02 on synthetic
   data; re-tune γ on 2019–2020 only.
4. **Breakdown detector skips flagged days when refitting Eq. 6**, so it does
   not "learn" a broken relationship. Synthetic result: detection 58% → 82%,
   false alarms 6.7% → 8.9%.
5. **No look-ahead in the backtest:** today's wholesale price is known (the
   trader buys at it), retail only up to yesterday, breakdown flag from yesterday.
6. **Amber = half the normal quantity** in the P&L simulation.

## Open questions for the team

- **β** (Red if interval width > β × m̄): placeholder β = 3. Choose on early years.
- **m̄**: proposed as the 90-day average of (Colombo retail − Dambulla wholesale), past only.
- Interest **r** and transport **C**: placeholders r = 0.3%, C = Rs. 6/kg. Need real values.

## Status

- **M4–M6:** Fully operational and tested on synthetic data.
- **M1:** Scraper index synced (3,141 daily bulletins across 2015–2026), SQLite database initialized (`data/prices.db`), and table parser verified on recent bulletins with 2,000 real price records populated.
- **M2:** Corridor feature extraction script (`build_real_features.py`) working and producing clean tabular feature sets (`real_beans_dambulla_peliyagoda.csv`, etc.).
- **Next step:** Run full historical backfill download (or selected years e.g. 2021–2026) and execute `backtest.py` directly on real prices.