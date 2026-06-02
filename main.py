#!/usr/bin/env python3
"""
main.py  –  Agricultural Outlook Scenario Explorer
===================================================
Run this script to execute the full pipeline:
  1. Load / download OECD-FAO wheat data
  2. Compute baseline + 3 shock scenarios
  3. Export all figures to ./figures/

Usage
-----
    python main.py                          # default: html + png output
    python main.py --formats html           # HTML only (no kaleido needed)
    python main.py --scenarios baseline low_yield high_yield
    python main.py --horizon 2035           # extend projection to 2035

Options
-------
  --formats      Space-separated list: html png svg  (default: html png)
  --scenarios    Which scenarios to include (default: all four)
  --horizon      Final projection year, e.g. 2032 or 2035 (default: 2032)
  --outdir       Output directory for figures  (default: figures)
"""

import argparse
import sys
import pandas as pd

from data_loader import load_oecd_fao_wheat
from scenario_engine import build_all_scenarios, SCENARIOS
from visualise import save_all_figures


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="OECD-FAO Wheat Outlook Scenario Explorer"
    )
    p.add_argument(
        "--formats", nargs="+", default=["html", "png"],
        choices=["html", "png", "svg"],
        help="Output figure formats (default: html png)",
    )
    p.add_argument(
        "--scenarios", nargs="+",
        default=list(SCENARIOS.keys()),
        choices=list(SCENARIOS.keys()),
        help="Scenarios to run (default: all)",
    )
    p.add_argument(
        "--horizon", type=int, default=2032,
        help="Final projection year (default: 2032)",
    )
    p.add_argument(
        "--outdir", default="figures",
        help="Directory to write figures into (default: figures)",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    print("=" * 62)
    print("  Agricultural Outlook Scenario Explorer")
    print("  Commodity: World Wheat")
    print("=" * 62)

    # ── Step 1: Load data ──────────────────────────────────────────
    print("\n[1/3] Loading OECD-FAO Agricultural Outlook data …")
    df_raw = load_oecd_fao_wheat()
    n_hist = (df_raw["year"] < 2023).sum()
    n_proj = (df_raw["year"] >= 2023).sum()
    print(f"      {n_hist} historical years  |  {n_proj} baseline projection years")

    # ── Step 2: Run scenarios ──────────────────────────────────────
    print(f"\n[2/3] Running scenarios: {', '.join(args.scenarios)} "
          f"(horizon: {args.horizon}) …")
    all_df = build_all_scenarios(
        df_raw,
        scenario_keys=args.scenarios,
        projection_end=args.horizon,
    )

    # Quick summary table
    summary = (
        all_df[all_df["year"] == args.horizon]
        [[  "scenario_label", "production_kt", "consumption_kt",
            "closing_stocks_kt", "stock_use_pct", "world_price_usd_t"]]
        .copy()
    )
    for col in ["production_kt", "consumption_kt", "closing_stocks_kt"]:
        summary[col.replace("_kt", "_mt")] = (summary[col] / 1_000).round(1)
    print(f"\n  Scenario outcomes at {args.horizon}:")
    print(
        summary[[
            "scenario_label",
            "production_mt", "consumption_mt", "closing_stocks_mt",
            "stock_use_pct", "world_price_usd_t",
        ]].rename(columns={
            "scenario_label":    "Scenario",
            "production_mt":     "Prod (Mt)",
            "consumption_mt":    "Cons (Mt)",
            "closing_stocks_mt": "Stocks (Mt)",
            "stock_use_pct":     "S/U (%)",
            "world_price_usd_t": "Price ($/t)",
        }).to_string(index=False)
    )

    # ── Step 3: Save figures ───────────────────────────────────────
    print(f"\n[3/3] Saving figures to ./{args.outdir}/ …")
    saved = save_all_figures(
        all_df, output_dir=args.outdir, formats=args.formats
    )

    print(f"\n✅  Done. {len(saved)} file(s) written.")
    print(f"   Open figures/{args.outdir.split('/')[-1]}/"
          f"06_scenario_dashboard.html for the briefing dashboard.\n")
    return all_df


if __name__ == "__main__":
    main()
