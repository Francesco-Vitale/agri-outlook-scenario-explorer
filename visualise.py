"""
visualise.py
============
Produces publication-quality figures in the style of the OECD-FAO
Agricultural Outlook.  All charts are built with Plotly so they are
interactive in a notebook / browser and can be exported as static PNG/SVG
for policy briefs.

Chart catalogue
---------------
1. supply_demand_balance   – stacked-bar production vs. consumption line
2. stock_use_ratio         – area/line showing stock-to-use % by scenario
3. trade_balance           – net export balance by scenario (line)
4. price_outlook           – world price index by scenario (line)
5. scenario_dashboard      – 2×2 combined figure for briefing one-pager
"""

from __future__ import annotations
import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from scenario_engine import SCENARIOS

# ── Style constants (mirrors OECD Outlook palette) ──────────────────────────
OECD_BLUE   = "#1f4e79"
OECD_LGBLUE = "#2e75b6"
OECD_GREY   = "#767171"
OECD_AMBER  = "#bf8f00"
SCENARIO_COLORS = {s.name: s.color for s in SCENARIOS.values()}

FONT_FAMILY = "Arial, sans-serif"
TITLE_SIZE  = 15
AXIS_SIZE   = 11
LEGEND_SIZE = 10
FIG_WIDTH   = 900
FIG_HEIGHT  = 480
UNIT_LABEL  = "Million tonnes"


def _kt_to_mt(series: pd.Series) -> pd.Series:
    return (series / 1_000).round(1)


def _base_layout(title: str, yaxis_title: str,
                 footnote: str = "") -> dict:
    """Shared Plotly layout dict."""
    annotations = []
    if footnote:
        annotations.append(dict(
            xref="paper", yref="paper", x=0, y=-0.13,
            text=footnote, showarrow=False,
            font=dict(size=9, color=OECD_GREY),
            align="left",
        ))
    return dict(
        title=dict(text=title, font=dict(size=TITLE_SIZE, family=FONT_FAMILY,
                                         color="#1a1a1a"), x=0.03),
        font=dict(family=FONT_FAMILY, size=AXIS_SIZE),
        xaxis=dict(title="", tickfont=dict(size=AXIS_SIZE),
                   showgrid=False, zeroline=False,
                   rangeslider=dict(visible=False)),
        yaxis=dict(title=yaxis_title, tickfont=dict(size=AXIS_SIZE),
                   gridcolor="#e8e8e8", zeroline=True,
                   zerolinecolor="#cccccc"),
        legend=dict(font=dict(size=LEGEND_SIZE), bgcolor="rgba(255,255,255,0.9)",
                    bordercolor="#dddddd", borderwidth=1,
                    orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=60, r=30, t=90, b=70),
        annotations=annotations,
        width=FIG_WIDTH,
        height=FIG_HEIGHT,
    )


def _add_projection_band(fig, df_scen: pd.DataFrame, row=None, col=None):
    """Shade the projection period with a light grey rectangle."""
    proj_start = df_scen[df_scen["is_projection"]]["year"].min()
    proj_end   = df_scen["year"].max()
    kwargs = dict(row=row, col=col) if row else {}
    fig.add_vrect(
        x0=proj_start - 0.5, x1=proj_end + 0.5,
        fillcolor="rgba(200,200,200,0.15)", line_width=0,
        annotation_text="Projection →", annotation_position="top left",
        annotation_font_size=9, annotation_font_color=OECD_GREY,
        **kwargs,
    )


# ── Individual chart functions ───────────────────────────────────────────────

def supply_demand_balance(all_df: pd.DataFrame,
                          scenario: str = "baseline") -> go.Figure:
    """
    Grouped bar (production) + line (consumption) for one scenario.
    Closely mirrors the standard Outlook supply/demand figure.
    """
    df = all_df[all_df["scenario"] == scenario].copy()
    df["production_mt"] = _kt_to_mt(df["production_kt"])
    df["consumption_mt"] = _kt_to_mt(df["consumption_kt"])
    df["stocks_mt"]      = _kt_to_mt(df["closing_stocks_kt"])

    fig = go.Figure()

    # Production bars coloured by historical / projection
    fig.add_bar(
        x=df[~df["is_projection"]]["year"],
        y=df[~df["is_projection"]]["production_mt"],
        name="Production (historical)",
        marker_color=OECD_LGBLUE,
        marker_opacity=0.85,
        width=0.6,
    )
    fig.add_bar(
        x=df[df["is_projection"]]["year"],
        y=df[df["is_projection"]]["production_mt"],
        name="Production (projected)",
        marker_color=OECD_LGBLUE,
        marker_opacity=0.45,
        marker_pattern_shape="/",
        width=0.6,
    )
    # Consumption line
    fig.add_scatter(
        x=df["year"], y=df["consumption_mt"],
        mode="lines+markers",
        name="Consumption",
        line=dict(color="#c0392b", width=2.5),
        marker=dict(size=5),
    )
    # Stock overlay (secondary y)
    fig.add_scatter(
        x=df["year"], y=df["stocks_mt"],
        mode="lines",
        name="Closing stocks",
        line=dict(color=OECD_AMBER, width=2, dash="dot"),
        yaxis="y2",
    )

    _add_projection_band(fig, df)
    scen_label = SCENARIOS[scenario].label
    fig.update_layout(
        **_base_layout(
            f"World Wheat: Supply & Demand Balance — {scen_label}",
            UNIT_LABEL,
            "Source: OECD-FAO Agricultural Outlook 2023-2032, author's projections."
        ),
        barmode="overlay",
        yaxis2=dict(
            title=dict(text="Stocks (Mt)", font=dict(color=OECD_AMBER)),
            overlaying="y", side="right",
            showgrid=False, tickfont=dict(size=AXIS_SIZE, color=OECD_AMBER),
        ),
    )
    return fig


def stock_use_comparison(all_df: pd.DataFrame,
                         scenarios: list[str] | None = None) -> go.Figure:
    """Stock-to-use ratio across scenarios — key food security indicator."""
    keys = scenarios or list(SCENARIOS.keys())
    fig = go.Figure()

    for key in keys:
        df = all_df[all_df["scenario"] == key].copy()
        is_base = key == "baseline"
        fig.add_scatter(
            x=df["year"], y=df["stock_use_pct"],
            mode="lines+markers",
            name=SCENARIOS[key].label,
            line=dict(
                color=SCENARIO_COLORS[key],
                width=3 if is_base else 2,
                dash="solid" if is_base else "dash",
            ),
            marker=dict(size=5 if is_base else 4),
        )

    # Reference line: "comfortable" stock level (FAO ~17-18%)
    df0 = all_df[all_df["scenario"] == "baseline"]
    fig.add_hline(y=17.5, line_dash="dot", line_color="#999999",
                  annotation_text="FAO comfort threshold ≈ 17.5%",
                  annotation_font_size=9,
                  annotation_position="bottom right")
    _add_projection_band(fig, df0)

    fig.update_layout(**_base_layout(
        "World Wheat Stock-to-Use Ratio by Scenario",
        "Stock-to-Use (%)",
        "Source: Author's scenario analysis based on OECD-FAO Agricultural Outlook 2023-2032.",
    ))
    return fig


def trade_balance_comparison(all_df: pd.DataFrame,
                              scenarios: list[str] | None = None) -> go.Figure:
    """Net trade balance (production minus consumption) by scenario."""
    keys = scenarios or list(SCENARIOS.keys())
    fig = go.Figure()

    for key in keys:
        df = all_df[all_df["scenario"] == key].copy()
        df["balance_mt"] = _kt_to_mt(df["trade_balance_kt"])
        is_base = key == "baseline"
        fig.add_scatter(
            x=df["year"], y=df["balance_mt"],
            mode="lines+markers",
            name=SCENARIOS[key].label,
            line=dict(
                color=SCENARIO_COLORS[key],
                width=3 if is_base else 2,
                dash="solid" if is_base else "dash",
            ),
            marker=dict(size=5),
        )

    fig.add_hline(y=0, line_dash="solid", line_color="#aaaaaa", line_width=1)
    df0 = all_df[all_df["scenario"] == "baseline"]
    _add_projection_band(fig, df0)

    fig.update_layout(**_base_layout(
        "World Wheat Net Balance (Production − Consumption) by Scenario",
        "Million tonnes",
        "Note: Positive = global surplus; Negative = global deficit.",
    ))
    return fig


def price_outlook_comparison(all_df: pd.DataFrame,
                             scenarios: list[str] | None = None) -> go.Figure:
    """Indicative world wheat price by scenario."""
    keys = scenarios or list(SCENARIOS.keys())
    fig = go.Figure()

    for key in keys:
        df = all_df[all_df["scenario"] == key].copy()
        is_base = key == "baseline"
        fig.add_scatter(
            x=df["year"], y=df["world_price_usd_t"],
            mode="lines+markers",
            name=SCENARIOS[key].label,
            line=dict(
                color=SCENARIO_COLORS[key],
                width=3 if is_base else 2,
                dash="solid" if is_base else "dash",
            ),
            fill="tozeroy" if is_base else "none",
            fillcolor="rgba(31,78,121,0.07)" if is_base else "rgba(0,0,0,0)",
            marker=dict(size=5),
        )

    df0 = all_df[all_df["scenario"] == "baseline"]
    _add_projection_band(fig, df0)

    fig.update_layout(**_base_layout(
        "Indicative World Wheat Price by Scenario",
        "USD / tonne",
        "Note: Price projection is model-derived using stock-to-use elasticity; "
        "not an OECD-FAO official price forecast.",
    ))
    return fig


def scenario_dashboard(all_df: pd.DataFrame) -> go.Figure:
    """
    2×2 combined figure — the centrepiece for a policy briefing one-pager.
    """
    keys = list(SCENARIOS.keys())
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "Production vs. Consumption (Baseline)",
            "Stock-to-Use Ratio by Scenario",
            "Net Balance by Scenario",
            "Indicative Price by Scenario",
        ],
        vertical_spacing=0.13,
        horizontal_spacing=0.09,
    )

    # ── Panel A: supply/demand baseline ──────────────────────────────────
    df_base = all_df[all_df["scenario"] == "baseline"].copy()
    df_base["prod_mt"] = _kt_to_mt(df_base["production_kt"])
    df_base["cons_mt"] = _kt_to_mt(df_base["consumption_kt"])
    fig.add_bar(
        x=df_base[~df_base["is_projection"]]["year"],
        y=df_base[~df_base["is_projection"]]["prod_mt"],
        name="Production (hist.)", marker_color=OECD_LGBLUE,
        marker_opacity=0.85, width=0.6,
        row=1, col=1, showlegend=True,
    )
    fig.add_bar(
        x=df_base[df_base["is_projection"]]["year"],
        y=df_base[df_base["is_projection"]]["prod_mt"],
        name="Production (proj.)", marker_color=OECD_LGBLUE,
        marker_opacity=0.4, marker_pattern_shape="/", width=0.6,
        row=1, col=1, showlegend=True,
    )
    fig.add_scatter(
        x=df_base["year"], y=df_base["cons_mt"],
        mode="lines+markers", name="Consumption",
        line=dict(color="#c0392b", width=2),
        marker=dict(size=4),
        row=1, col=1,
    )

    # ── Panels B, C, D ───────────────────────────────────────────────────
    for key in keys:
        df = all_df[all_df["scenario"] == key].copy()
        is_base = key == "baseline"
        lw = 2.5 if is_base else 1.8
        ld = "solid" if is_base else "dash"
        col = SCENARIO_COLORS[key]
        short_label = {
            "baseline":     "Baseline",
            "high_yield":   "High yield",
            "low_yield":    "Low yield",
            "demand_surge": "Demand surge",
        }[key]

        # Panel B – stock-to-use
        fig.add_scatter(
            x=df["year"], y=df["stock_use_pct"],
            mode="lines", name=short_label,
            line=dict(color=col, width=lw, dash=ld),
            row=1, col=2, showlegend=False,
        )
        # Panel C – net balance
        fig.add_scatter(
            x=df["year"], y=_kt_to_mt(df["trade_balance_kt"]),
            mode="lines", name=short_label,
            line=dict(color=col, width=lw, dash=ld),
            row=2, col=1, showlegend=False,
        )
        # Panel D – price
        fig.add_scatter(
            x=df["year"], y=df["world_price_usd_t"],
            mode="lines", name=short_label,
            line=dict(color=col, width=lw, dash=ld),
            row=2, col=2, showlegend=False,
        )

    # Reference lines
    fig.add_hline(y=17.5, line_dash="dot", line_color="#aaa",
                  line_width=1, row=1, col=2)
    fig.add_hline(y=0, line_dash="solid", line_color="#ccc",
                  line_width=1, row=2, col=1)

    # Projection bands (all panels)
    proj_start = df_base[df_base["is_projection"]]["year"].min()
    proj_end   = df_base["year"].max()
    for r, c in [(1, 1), (1, 2), (2, 1), (2, 2)]:
        fig.add_vrect(
            x0=proj_start - 0.5, x1=proj_end + 0.5,
            fillcolor="rgba(200,200,200,0.13)", line_width=0,
            row=r, col=c,
        )

    # Colour-coded scenario legend (manual annotation strip)
    legend_items = [
        ("Baseline",      OECD_BLUE),
        ("High yield",    "#2e7d32"),
        ("Low yield",     "#b71c1c"),
        ("Demand surge",  "#e65100"),
    ]
    for i, (lbl, clr) in enumerate(legend_items):
        fig.add_annotation(
            x=0.505 + i * 0.125, y=0.495,
            xref="paper", yref="paper",
            text=f"<span style='color:{clr}'>●</span> {lbl}",
            showarrow=False, font=dict(size=9, family=FONT_FAMILY),
            align="left",
        )

    fig.update_layout(
        title=dict(
            text="World Wheat Outlook 2023–2032: Baseline & Scenario Analysis",
            font=dict(size=16, family=FONT_FAMILY, color="#1a1a1a"), x=0.03,
        ),
        font=dict(family=FONT_FAMILY, size=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
        barmode="overlay",
        showlegend=False,
        margin=dict(l=55, r=30, t=90, b=55),
        width=1100,
        height=700,
    )

    # Axis labels
    for r, c, ytitle in [
        (1, 1, "Million tonnes"),
        (1, 2, "Stock-to-Use (%)"),
        (2, 1, "Million tonnes"),
        (2, 2, "USD / tonne"),
    ]:
        fig.update_yaxes(
            title_text=ytitle, gridcolor="#eeeeee",
            zeroline=True, zerolinecolor="#cccccc",
            row=r, col=c,
        )
        fig.update_xaxes(showgrid=False, row=r, col=c)

    # Source note
    fig.add_annotation(
        xref="paper", yref="paper", x=0, y=-0.06,
        text="Source: OECD-FAO Agricultural Outlook 2023-2032; author's scenario modelling. "
             "Projection band shaded.",
        showarrow=False, font=dict(size=8, color=OECD_GREY), align="left",
    )

    return fig


# ── Export helpers ───────────────────────────────────────────────────────────

def save_all_figures(all_df: pd.DataFrame,
                     output_dir: str = "figures",
                     formats: list[str] | None = None) -> list[str]:
    """
    Save all charts to output_dir.  Returns list of written file paths.
    formats: list containing any of ["html", "png", "svg"]
    Default: ["html"] (always works without kaleido); png/svg require kaleido.
    """
    os.makedirs(output_dir, exist_ok=True)
    fmts = formats or ["html", "png"]
    saved = []

    charts = {
        "01_supply_demand_baseline":  supply_demand_balance(all_df, "baseline"),
        "02_supply_demand_low_yield": supply_demand_balance(all_df, "low_yield"),
        "03_stock_use_ratio":         stock_use_comparison(all_df),
        "04_trade_balance":           trade_balance_comparison(all_df),
        "05_price_outlook":           price_outlook_comparison(all_df),
        "06_scenario_dashboard":      scenario_dashboard(all_df),
    }

    for name, fig in charts.items():
        for fmt in fmts:
            path = os.path.join(output_dir, f"{name}.{fmt}")
            try:
                if fmt == "html":
                    fig.write_html(path, include_plotlyjs="cdn")
                elif fmt in ("png", "svg", "pdf"):
                    fig.write_image(path)
                saved.append(path)
                print(f"  Saved: {path}")
            except Exception as e:
                print(f"  ⚠️  Could not save {path}: {e}")

    return saved


if __name__ == "__main__":
    from data_loader import load_oecd_fao_wheat
    from scenario_engine import build_all_scenarios

    df_raw  = load_oecd_fao_wheat()
    all_df  = build_all_scenarios(df_raw)
    saved   = save_all_figures(all_df, output_dir="figures", formats=["html", "png"])
    print(f"\n{len(saved)} figure files written.")
