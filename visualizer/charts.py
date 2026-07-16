import numpy as np
import pandas as pd
import plotly.graph_objects as go

BLUE = "#2a78d6"
GREEN = "#008300"
YELLOW = "#eda100"
ORANGE = "#eb6834"
VIOLET = "#4a3aa7"
MUTED = "#898781"
GRIDLINE = "#e1e0d9"
GOOD = "#0ca30c"
CRITICAL = "#d03b3b"

SEQUENTIAL_BLUE = [[0.0, "#cde2fb"], [0.5, "#3987e5"], [1.0, "#0d366b"]]

EXIT_COLORS = {"time_stop": BLUE, "adverse_move": YELLOW, "take_profit": GREEN}


def _layout(fig: go.Figure, title: str, yaxis_title: str, xaxis_title: str = "Date") -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=40, r=20, t=60, b=40),
    )
    fig.update_xaxes(title_text=xaxis_title, gridcolor=GRIDLINE, showline=True, linecolor=MUTED)
    fig.update_yaxes(title_text=yaxis_title, gridcolor=GRIDLINE, showline=True, linecolor=MUTED)
    return fig


def price_chart(index, price_a: np.ndarray, price_b: np.ndarray, ticker_a: str, ticker_b: str) -> go.Figure:
    """Both legs indexed to 100 at the start of the window — a single shared axis
    instead of a dual-axis chart, since price_a/price_b are on different scales."""
    idx_a = 100 * np.exp(price_a - price_a[0])
    idx_b = 100 * np.exp(price_b - price_b[0])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=index, y=idx_a, name=ticker_a, line=dict(color=BLUE, width=2)))
    fig.add_trace(go.Scatter(x=index, y=idx_b, name=ticker_b, line=dict(color=GREEN, width=2)))
    return _layout(fig, f"{ticker_a} vs {ticker_b} — indexed to 100", "Indexed level (start = 100)")


def zscore_chart(
    index, zscore: np.ndarray, ticker_a: str, ticker_b: str,
    mu_z: float | None = None, upper_z: float | None = None, lower_z: float | None = None,
    entry_z: float | None = None, entry_x=None, tp_z: float | None = None,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=index, y=zscore, name="Z-score", line=dict(color=BLUE, width=1.5)))
    fig.add_hline(y=0, line=dict(color=MUTED, width=1, dash="dot"))
    if mu_z is not None:
        fig.add_hline(y=mu_z, line=dict(color=MUTED, width=1.5, dash="dash"),
                      annotation_text="μ", annotation_position="right")
        fig.add_hline(y=upper_z, line=dict(color=ORANGE, width=1, dash="dash"),
                      annotation_text="+2σ (stationary)", annotation_position="right")
        fig.add_hline(y=lower_z, line=dict(color=ORANGE, width=1, dash="dash"),
                      annotation_text="-2σ (stationary)", annotation_position="right")
    if tp_z is not None:
        fig.add_hline(y=tp_z, line=dict(color=GOOD, width=1.5, dash="dashdot"),
                      annotation_text="take-profit", annotation_position="right")
    if entry_z is not None and entry_x is not None:
        fig.add_trace(go.Scatter(
            x=[entry_x], y=[entry_z], mode="markers", name="Entry signal",
            marker=dict(color=VIOLET, size=12, symbol="diamond",
                        line=dict(width=1, color="rgba(11,11,11,0.10)")),
        ))
    return _layout(fig, f"{ticker_a}/{ticker_b} spread z-score", "Z-score")


def rolling_beta_chart(index, roll_beta: pd.Series, ticker_a: str, ticker_b: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=index, y=roll_beta.values, name="Hedge ratio (β)",
                              line=dict(color=BLUE, width=1.5)))
    return _layout(fig, f"{ticker_a}/{ticker_b} rolling hedge ratio", "β")


def rolling_coint_chart(index, roll_p: pd.Series, ticker_a: str, ticker_b: str, threshold: float = 0.05) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=index, y=roll_p.values, name="Cointegration p-value",
                              mode="lines+markers", line=dict(color=BLUE, width=1.5)))
    fig.add_hline(y=threshold, line=dict(color=CRITICAL, width=1, dash="dot"),
                  annotation_text=f"p={threshold}", annotation_position="right")
    return _layout(fig, f"{ticker_a}/{ticker_b} rolling cointegration stability", "p-value")


def screening_scatter(summary: pd.DataFrame, tradeable: pd.Series) -> go.Figure:
    symbols = np.where(tradeable.values, "circle", "x")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=summary["hurst"], y=summary["half_life_hours"],
        mode="markers",
        marker=dict(
            color=summary["coint_stability"], colorscale=SEQUENTIAL_BLUE, cmin=0, cmax=1,
            size=13, symbol=symbols, line=dict(width=1, color="rgba(11,11,11,0.15)"),
            colorbar=dict(title="Coint.<br>stability"),
        ),
        text=[f"{a}/{b}" for a, b in zip(summary.ticker_a, summary.ticker_b)],
        hovertemplate="%{text}<br>Hurst=%{x:.3f}<br>Half-life=%{y:.1f}h<br>"
                      "Coint. stability=%{marker.color:.2f}<extra></extra>",
        showlegend=False,
    ))
    fig.add_vline(x=0.48, line=dict(color=MUTED, dash="dot"))
    fig = _layout(fig, "Pair screen — half-life vs. Hurst (● tradeable · × filtered out)",
                  "Half-life (hours)", "Hurst exponent")
    fig.update_yaxes(type="log")
    return fig


def equity_curve_chart(trades: pd.DataFrame) -> go.Figure:
    marker_colors = [EXIT_COLORS.get(r, MUTED) for r in trades["exit_reason"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trades["exit_time"], y=trades["cumulative_pnl"], mode="lines+markers",
        name="Cumulative P&L", line=dict(color=BLUE, width=2),
        marker=dict(color=marker_colors, size=11, line=dict(width=1, color="rgba(11,11,11,0.10)")),
        text=trades["exit_reason"], hovertemplate="%{x}<br>Cum. P&L=%{y:.2f}<br>Exit: %{text}<extra></extra>",
        showlegend=False,
    ))
    fig.add_hline(y=0, line=dict(color=MUTED, width=1, dash="dot"))
    return _layout(fig, "Cumulative realized P&L", "USDT", "Exit time")


def exit_reason_bar(trades: pd.DataFrame) -> go.Figure:
    counts = trades["exit_reason"].value_counts()
    fig = go.Figure()
    for reason in ["time_stop", "adverse_move", "take_profit"]:
        if reason in counts.index:
            fig.add_trace(go.Bar(
                x=[reason], y=[int(counts[reason])], marker_color=EXIT_COLORS[reason],
                showlegend=False, text=[int(counts[reason])], textposition="outside",
            ))
    return _layout(fig, "Exit reason breakdown", "Number of trades", "Exit reason")


def pnl_distribution_chart(trades: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=trades["pnl_pct"], marker_color=BLUE, nbinsx=10, showlegend=False))
    fig.add_vline(x=0, line=dict(color=MUTED, width=1, dash="dot"))
    return _layout(fig, "Distribution of pnl_pct across closed trades", "Count", "pnl_pct")
