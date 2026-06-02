# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a quantitative finance research project that builds and analyzes a **Limit Order Book (LOB)** from Market-by-Order (MBO / L3) data sourced via the Databento API. The goal is probabilistic modelling of trade arrival and trade size to generate a quote-placement trading strategy for high-frequency trading on NASDAQ SPDR SPY.

The full research write-up is in `Paper/Limex_Quantum_Project.pdf`.

## Running the Code

All analysis runs in `Code/test.ipynb`. There is no build system or test suite — open the notebook in Jupyter and run cells sequentially:

```bash
cd Code
jupyter notebook test.ipynb
```

Before running, update the data path in cell 4:
```python
paths = ['/YOUR_DATA_PATH']  # path to a .dbn file from Databento
```

Data is loaded as a Databento DBN file (MBO schema) for a single trading day. The notebook expects ~16 hours of order book data for SPY.

## Dependencies

Key packages (install via pip):
- `databento` — API client and DBN data format parser
- `sortedcontainers` — `SortedDict` used for O(log n) price-level access in the LOB
- `pandas`, `numpy`, `scikit-learn`, `matplotlib`

## Architecture

The pipeline flows in this order:

```
Raw .dbn file
  → mbo_schema_to_dataframe.py   (load into DataFrame)
  → build_limit_order_book.py    (reconstruct LOB tick-by-tick)
  → limit_order_book_metrics.py  (imbalance, slope, quantiles per snapshot)
  → probability_model.py         (Poisson arrivals + Pareto trade sizes)
  → high_frequency_returns.py    (backtest equity curve)
```

### `build_limit_order_book.py`

Core LOB engine. Key classes:
- `PriceLevel` — L2 view: price, aggregated size, order count
- `LevelOrders` — L3 view: price + list of individual `MBOMsg` orders
- `Book` — the LOB itself; `asks` and `bids` are `SortedDict[price → LevelOrders]`, enabling O(log n) best-price lookup via `peekitem(0)` / `peekitem(-1)`
- `pandas_to_MBOMsg` — shim that duck-types a DataFrame row to look like `db.MBOMsg` for `Book.apply()`

`Book.apply()` handles all MBO actions: `A` (add), `C` (cancel), `M` (modify), `R` (reset). Actions `T`, `F`, `N` are skipped (they do not modify the book).

The `lob()` function iterates the full MBO DataFrame, replaying all events. When `snapshots=True`, it emits periodic L2 snapshots at the given `frequency` (default `'1min'`), along with micro-prices, trade/fill counts, and full `Book` objects.

**Important conventions:**
- Prices are stored as integers scaled by `db.FIXED_PRICE_SCALE` (divide by this to get decimal price)
- LOB snapshot dicts use `'s'` for supply/ask side and `'d'` for demand/bid side throughout all modules
- `deepcopy` is required when saving snapshots because `SortedDict` is mutated in-place

### `probability_model.py`

Fits three stochastic models to the LOB data:
- **Poisson process** — models trade arrival rate (λ) for each side independently
- **Pareto Type I (power series)** — models trade size distribution; α estimated via MLE
- **Exponential CDF** — models waiting time until the next quote-clearing trade given trade intensity λ

The trading signal (`strategy_signals` in the notebook) compares `P(wait_ask < wait_bid)` — it goes long on the side with the higher probability of being filled first.

### `limit_order_book_metrics.py`

- `get_imbalance()` — computes (weighted) order book imbalance across N levels
- `lob_side_slope()` — log-linear regression of volume on price level (convexity proxy)
- `book_snapshot_metrics` — percentile volume and min/max order counts across all snapshots

### `high_frequency_returns.py`

Computes cumulative equity curve: `E_t = E_{t-1} * exp(r_t * position_t) - fee`. Supports buy-and-hold benchmark (`bnh=True`) and per-share dollar fees.