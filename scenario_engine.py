"""
scenario_engine.py
==================
Extends the OECD-FAO baseline balance sheet forward under user-defined shocks.

Three built-in scenarios
------------------------
1. HIGH_YIELD   : production trend grows faster (+1 pp/yr above baseline CAGR)
2. LOW_YIELD    : production trend grows slower (−1 pp/yr below baseline CAGR)
3. DEMAND_SURGE : consumption accelerates (e.g. biofuel mandate / population shock)
                  +0.5 pp/yr above baseline consumption growth

Each scenario recomputes:
  - production_kt
  - consumption_kt
  - closing_stocks_kt  (cumulative stock balance)
  - trade_balance_kt   (residual, constant trade share)
  - stock_use_pct

Design philosophy
-----------------
We keep the model deliberately simple and transparent:
  • Production and consumption are grown from the last historical year
    using the baseline OECD CAGR, then shocked additively.
  • Stocks update as: stocks_t = stocks_{t-1} + production_t − consumption_t
  • Trade balance is the residual (world net = 0 by identity; here it tracks
    a representative large exporter's net position as a fraction of the baseline).
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Scenario definition
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    name: str
    label: str                          # short human-readable label
    color: str                          # Plotly color string
    # Production shocks
    yield_delta_pp: float = 0.0         # percentage-point shift in annual production growth
    # Consumption shocks
    demand_delta_pp: float = 0.0        # pp shift in annual consumption growth
    # Price elasticity (rough): if supply surplus, price falls proportionally
    price_elasticity: float = -0.4      # % price change per 1% change in s/u ratio


SCENARIOS: dict[str, Scenario] = {
    "baseline": Scenario(
        name="baseline",
        label="Baseline (OECD-FAO Outlook)",
        color="#1f4e79",
        yield_delta_pp=0.0,
        demand_delta_pp=0.0,
    ),
    "high_yield": Scenario(
        name="high_yield",
        label="High Yield (+1 pp/yr production growth)",
        color="#2e7d32",
        yield_delta_pp=1.0,
        demand_delta_pp=0.0,
    ),
    "low_yield": Scenario(
        name="low_yield",
        label="Low Yield (−1 pp/yr production growth)",
        color="#b71c1c",
        yield_delta_pp=-1.0,
        demand_delta_pp=0.0,
    ),
    "demand_surge": Scenario(
        name="demand_surge",
        label="Demand Surge (+0.5 pp/yr consumption growth)",
        color="#e65100",
        yield_delta_pp=0.0,
        demand_delta_pp=0.5,
    ),
}


# ---------------------------------------------------------------------------
# Projection engine
# ---------------------------------------------------------------------------

def compute_baseline_cagr(df: pd.DataFrame, start_year: int = 2015,
                           end_year: int = 2022) -> dict:
    """Compute compound annual growth rates from the historical slice."""
    hist = df[df["year"].between(start_year, end_year)].copy()
    n = len(hist) - 1

    def cagr(col: str) -> float:
        v0, v1 = hist[col].iloc[0], hist[col].iloc[-1]
        return (v1 / v0) ** (1 / n) - 1 if v0 > 0 else 0.0

    return {
        "production": cagr("production_kt"),
        "consumption": cagr("consumption_kt"),
        "exports":     cagr("exports_kt"),
    }


def project_scenario(
    df: pd.DataFrame,
    scenario: Scenario,
    projection_start: int = 2023,
    projection_end:   int = 2032,
    use_embedded_baseline: bool = True,
) -> pd.DataFrame:
    """
    Build a full time series (historical + projected) for a given scenario.

    Parameters
    ----------
    df                     : the raw dataframe from data_loader
    scenario               : Scenario object describing the shock
    projection_start/end   : horizon
    use_embedded_baseline  : if True, use the embedded OECD projection as the
                             baseline trajectory and apply deltas on top of it

    Returns
    -------
    pd.DataFrame with same columns as input, covering 2015–projection_end
    """
    hist = df[df["year"] < projection_start].copy()
    base_proj = df[df["year"].between(projection_start, projection_end)].copy()

    # Seed values (last historical year)
    seed = hist.iloc[-1]
    prod_0  = seed["production_kt"]
    cons_0  = seed["consumption_kt"]
    stck_0  = seed["closing_stocks_kt"]
    exp_0   = seed["exports_kt"]
    imp_0   = seed["imports_kt"]
    px_0    = seed["world_price_usd_t"]

    # CAGRs from historical data
    cagrs = compute_baseline_cagr(df)

    rows = []
    for i, yr in enumerate(range(projection_start, projection_end + 1), start=1):

        if use_embedded_baseline and not base_proj.empty:
            # Use OECD embedded trajectory as anchor; apply scenario delta on top
            base_row = base_proj[base_proj["year"] == yr].iloc[0]
            prod_base = base_row["production_kt"]
            cons_base = base_row["consumption_kt"]
        else:
            # Pure CAGR extrapolation from seed
            prod_base = prod_0 * (1 + cagrs["production"]) ** i
            cons_base = cons_0 * (1 + cagrs["consumption"]) ** i

        # Apply scenario shocks (additive on growth rate)
        prod_kt = prod_base * (1 + scenario.yield_delta_pp / 100) ** i
        cons_kt = cons_base * (1 + scenario.demand_delta_pp / 100) ** i

        # Stock balance (simple accumulation)
        if i == 1:
            stck_kt = stck_0 + prod_kt - cons_kt
        else:
            stck_kt = rows[-1]["closing_stocks_kt"] + prod_kt - cons_kt
        stck_kt = max(stck_kt, 0)  # floor at zero

        # Trade: assume exports/imports scale with production surplus/deficit
        # relative to baseline
        exp_share_base = exp_0 / prod_0
        trade_adj = (prod_kt - cons_kt) / max(prod_kt, 1)
        exp_kt = exp_0 * (1 + cagrs["exports"]) ** i + max(prod_kt - cons_kt, 0) * 0.3
        imp_kt = exp_kt  # world identity (simplified)

        # Stock-to-use ratio
        su_pct = stck_kt / cons_kt * 100

        # Rough price signal: price inversely linked to s/u ratio
        su_base_pct = (stck_0 / cons_0 * 100)
        su_delta_pp = su_pct - su_base_pct
        px_t = px_0 * (1 + scenario.price_elasticity * su_delta_pp / 100)

        rows.append({
            "year":               yr,
            "production_kt":      round(prod_kt),
            "consumption_kt":     round(cons_kt),
            "exports_kt":         round(exp_kt),
            "imports_kt":         round(imp_kt),
            "closing_stocks_kt":  round(stck_kt),
            "trade_balance_kt":   round(prod_kt - cons_kt),
            "stock_use_pct":      round(su_pct, 1),
            "world_price_usd_t":  round(px_t, 1),
            "is_projection":      True,
        })

    proj = pd.DataFrame(rows)

    # Combine historical + projected
    hist = hist.copy()
    hist["is_projection"] = False
    hist["trade_balance_kt"] = hist["exports_kt"] - hist["imports_kt"]
    hist["stock_use_pct"] = (
        hist["closing_stocks_kt"] / hist["consumption_kt"] * 100
    ).round(1)

    result = pd.concat([hist, proj], ignore_index=True)
    result["scenario"] = scenario.name
    result["scenario_label"] = scenario.label
    return result


def build_all_scenarios(df: pd.DataFrame,
                        scenario_keys: Optional[list[str]] = None,
                        **kwargs) -> pd.DataFrame:
    """Run project_scenario for each requested scenario and stack results."""
    keys = scenario_keys or list(SCENARIOS.keys())
    frames = [project_scenario(df, SCENARIOS[k], **kwargs) for k in keys]
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    from data_loader import load_oecd_fao_wheat
    df_raw = load_oecd_fao_wheat()
    all_df = build_all_scenarios(df_raw)
    print(all_df[all_df["scenario"] == "baseline"][
        ["year", "production_kt", "consumption_kt", "closing_stocks_kt", "stock_use_pct"]
    ].to_string(index=False))
