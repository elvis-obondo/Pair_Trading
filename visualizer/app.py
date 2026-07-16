import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import streamlit as st

from visualizer.data import (
    load_price_levels,
    run_screen,
    tradeable_mask,
    get_tradeable_pairs,
    compute_pair_diagnostics,
    evaluate_gates,
    load_trade_log,
)
from visualizer.charts import (
    price_chart,
    zscore_chart,
    rolling_beta_chart,
    rolling_coint_chart,
    screening_scatter,
    equity_curve_chart,
    exit_reason_bar,
    pnl_distribution_chart,
)
from research.signal_generator import generate_entry_signal
from research.position_sizer import compute_position_size

st.set_page_config(page_title="Pair Trading Visualizer", layout="wide")
st.title("Pair Trading Research Visualizer")
st.caption(
    "Interactive view over the research pipeline in research/*.py. "
    "Read-only — does not modify any research code, and does not run the "
    "Nautilus backtest (see README for its known data-layout issue)."
)

if "active_pair" not in st.session_state:
    st.session_state.active_pair = None
if "entry_signal" not in st.session_state:
    st.session_state.entry_signal = None

price_df = load_price_levels()
all_tickers = list(price_df.columns)


def pair_picker(key_prefix: str):
    default_a, default_b = st.session_state.active_pair or (all_tickers[0], all_tickers[1])
    idx_a = all_tickers.index(default_a) if default_a in all_tickers else 0
    idx_b = all_tickers.index(default_b) if default_b in all_tickers else 1
    c1, c2 = st.columns(2)
    ticker_a = c1.selectbox("Ticker A", all_tickers, index=idx_a, key=f"{key_prefix}_a")
    ticker_b = c2.selectbox("Ticker B", all_tickers, index=idx_b, key=f"{key_prefix}_b")
    if ticker_a == ticker_b:
        st.warning("Ticker A and Ticker B must differ.")
        st.stop()
    st.session_state.active_pair = (ticker_a, ticker_b)
    return ticker_a, ticker_b


tab_screen, tab_spread, tab_signal, tab_size, tab_trades = st.tabs(
    ["Screening", "Spread & OU", "Signal Gates", "Position Sizing", "Trade Log"]
)

with tab_screen:
    st.subheader("Cointegration screen")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    top_n = c1.number_input("Top N pairs", 5, 100, 10, key="top_n")
    lookback_days = c2.number_input("Lookback (days)", 7, 90, 30, key="lookback_days")
    window_days = c3.number_input("Rolling window (days)", 1, 14, 7, key="window_days")
    c4.write("")
    c4.write("")
    run_clicked = c4.button("Run scan", type="primary")

    if run_clicked:
        with st.spinner("Scanning pairs — this runs cointegration tests on every combination..."):
            st.session_state.screen_summary = run_screen(top_n, window_days, lookback_days)

    summary = st.session_state.get("screen_summary")
    if summary is None:
        st.info("Set parameters above and click **Run scan**.")
    elif summary.empty:
        st.warning("No pairs had enough bars for the requested lookback window.")
    else:
        mask = tradeable_mask(summary)
        st.plotly_chart(screening_scatter(summary, mask), use_container_width=True, key="chart_screen_scatter")
        st.dataframe(
            summary.style.apply(lambda row: ["background-color: rgba(10,163,10,0.12)" if mask.iloc[row.name] else "" for _ in row], axis=1),
            use_container_width=True,
        )
        tradeable = get_tradeable_pairs(summary)
        if tradeable.empty:
            st.warning("No pairs passed all tradeable filters (half-life, Hurst, coint. stability, β CV).")
        else:
            st.success(f"{len(tradeable)} tradeable pair(s) passed all filters.")
            options = [f"{r.ticker_a}/{r.ticker_b}" for r in tradeable.itertuples()]
            picked = st.selectbox("Inspect a pair in the other tabs", options)
            if st.button("Use this pair"):
                a, b = picked.split("/")
                st.session_state.active_pair = (a, b)
                st.success(f"Active pair set to {a}/{b} — see Spread & OU / Signal Gates tabs.")

with tab_spread:
    st.subheader("Spread & OU diagnostics")
    ticker_a, ticker_b = pair_picker("spread")
    window_days_spread = st.slider("Rolling window (days) for β / cointegration stability", 1, 14, 7, key="spread_window")

    diag = compute_pair_diagnostics(price_df, ticker_a, ticker_b, window_days_spread)
    ou, resid = diag["ou"], diag["diag"]
    ou_ok = not np.isnan(ou.theta)

    st.plotly_chart(price_chart(diag["index"], diag["price_a"], diag["price_b"], ticker_a, ticker_b),
                     use_container_width=True, key="chart_spread_price")

    mu_z = upper_z = lower_z = None
    if ou_ok:
        mu_z = (ou.mu - diag["spread_mean"]) / diag["spread_std"]
        sigma_stationary = ou.sigma / np.sqrt(2.0 * ou.theta)
        upper_z = (ou.mu + 2.0 * sigma_stationary - diag["spread_mean"]) / diag["spread_std"]
        lower_z = (ou.mu - 2.0 * sigma_stationary - diag["spread_mean"]) / diag["spread_std"]
    st.plotly_chart(
        zscore_chart(diag["index"], diag["zscore"], ticker_a, ticker_b, mu_z, upper_z, lower_z),
        use_container_width=True, key="chart_spread_zscore",
    )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(rolling_beta_chart(diag["roll_beta_index"], diag["roll_beta"], ticker_a, ticker_b),
                         use_container_width=True, key="chart_spread_beta")
    with c2:
        st.plotly_chart(rolling_coint_chart(diag["roll_p_index"], diag["roll_p"], ticker_a, ticker_b),
                         use_container_width=True, key="chart_spread_coint")

    st.markdown("**OU parameters & residual diagnostics**")
    if not ou_ok:
        st.error("OU fit failed (theta <= 0 or insufficient data) — mean reversion not supported.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("θ (mean-reversion speed, /bar)", f"{ou.theta:.4f}")
        m2.metric("μ (long-run mean)", f"{ou.mu:.5f}")
        m3.metric("σ (spread vol, /√bar)", f"{ou.sigma:.5f}")
        m4, m5, m6 = st.columns(3)
        m4.metric("θ significance p-value", f"{resid.theta_p:.4f}", help="signal_generator gate threshold: <= 0.05")
        m5.metric("Jarque-Bera p (normality)", f"{resid.jb_p:.4f}")
        m6.metric("Ljung-Box p (autocorrelation)", f"{resid.lb_p:.4f}")

with tab_signal:
    st.subheader("Entry signal gates")
    ticker_a, ticker_b = pair_picker("signal")

    diag = compute_pair_diagnostics(price_df, ticker_a, ticker_b, 7)
    n_bars = len(diag["price_a"])
    min_bars = 200
    if n_bars < min_bars:
        st.warning(f"Only {n_bars} bars available for this pair — too few for a meaningful gate check.")
        st.stop()

    as_of = st.slider("As-of bar (time-travel through history)", min_bars, n_bars, n_bars, key="as_of")
    st.caption(f"As-of timestamp: {diag['index'][as_of - 1]}")

    with st.expander("Gate thresholds", expanded=False):
        t1, t2, t3 = st.columns(3)
        coint_p_threshold = t1.number_input("coint_p_threshold", 0.0, 1.0, 0.10, step=0.01)
        theta_p_threshold = t2.number_input("theta_p_threshold", 0.0, 1.0, 0.05, step=0.01)
        prob_threshold = t3.number_input("prob_threshold", 0.0, 1.0, 0.67, step=0.01)
        t4, t5, t6 = st.columns(3)
        regime_threshold = t4.number_input("regime_threshold", 0.0, 5.0, 1.1, step=0.1)
        min_deviation_sigma = t5.number_input("min_deviation_sigma", 0.0, 5.0, 1.0, step=0.1)
        f_param = t6.number_input("f (decay fraction)", 0.01, 1.0, 0.20, step=0.01)

    pa_slice = diag["price_a"][:as_of]
    pb_slice = diag["price_b"][:as_of]

    gates = evaluate_gates(
        pa_slice, pb_slice,
        coint_p_threshold=coint_p_threshold, regime_threshold=regime_threshold,
        prob_threshold=prob_threshold, theta_p_threshold=theta_p_threshold,
        f=f_param, min_deviation_sigma=min_deviation_sigma,
    )
    for gate in gates:
        if gate["passed"]:
            st.success(f"✓ {gate['name']} — {gate['detail']}")
        else:
            st.error(f"✗ {gate['name']} — {gate['detail']}")

    entry_signal = generate_entry_signal(
        pa_slice, pb_slice,
        coint_p_threshold=coint_p_threshold, regime_threshold=regime_threshold,
        prob_threshold=prob_threshold, theta_p_threshold=theta_p_threshold,
        f=f_param, min_deviation_sigma=min_deviation_sigma,
    )
    st.session_state.entry_signal = entry_signal

    if entry_signal is None:
        st.info("No entry signal at this bar — at least one gate above failed.")
    else:
        st.success("All gates passed — entry signal generated.")
        st.json(entry_signal)

    zscore_slice = diag["zscore"][:as_of]
    ou = diag["ou"]
    mu_z = upper_z = lower_z = tp_z = entry_z = None
    if not np.isnan(ou.theta):
        mu_z = (ou.mu - diag["spread_mean"]) / diag["spread_std"]
        sigma_stationary = ou.sigma / np.sqrt(2.0 * ou.theta)
        upper_z = (ou.mu + 2.0 * sigma_stationary - diag["spread_mean"]) / diag["spread_std"]
        lower_z = (ou.mu - 2.0 * sigma_stationary - diag["spread_mean"]) / diag["spread_std"]
    if entry_signal is not None:
        tp_z = (entry_signal["take_profit_level"] - diag["spread_mean"]) / diag["spread_std"]
        entry_z = zscore_slice[-1]
    st.plotly_chart(
        zscore_chart(
            diag["index"][:as_of], zscore_slice, ticker_a, ticker_b,
            mu_z, upper_z, lower_z, entry_z=entry_z,
            entry_x=diag["index"][as_of - 1] if entry_z is not None else None,
            tp_z=tp_z,
        ),
        use_container_width=True, key="chart_signal_zscore",
    )

with tab_size:
    st.subheader("Position sizing")
    entry_signal = st.session_state.entry_signal
    if entry_signal is None:
        st.info("No active entry signal — go to the **Signal Gates** tab and find a bar where all gates pass.")
    else:
        a, b = st.session_state.active_pair
        st.caption(f"Sizing an entry signal for {a}/{b} carried over from the Signal Gates tab.")
        c1, c2, c3 = st.columns(3)
        capital = c1.number_input("Capital (USDT)", min_value=1.0, value=1000.0, step=100.0)
        risk_budget_pct = c2.number_input("Risk budget per trade", min_value=0.001, max_value=1.0, value=0.01, step=0.001, format="%.3f")
        stop_sigma = c3.number_input("Stop distance (σ_stationary)", min_value=0.1, value=2.5, step=0.1)

        sizing = compute_position_size(entry_signal, capital, risk_budget_pct, stop_sigma)
        if sizing is None:
            st.error("compute_position_size returned None — check inputs (capital/risk/stop must be finite and positive).")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Leg A notional", f"${sizing['leg_a_notional']:.2f}")
            m2.metric("Leg B notional", f"${sizing['leg_b_notional']:.2f}")
            m3.metric("Total deployed", f"${sizing['total_deployed']:.2f}")
            st.caption(
                f"Fraction of capital on leg A: {sizing['fraction']:.4f} · "
                f"σ_stationary: {sizing['sigma_stationary']:.5f} spread units"
            )
            if sizing["leg_b_notional"] < 0:
                st.caption("Leg B notional is negative — that leg is short while leg A is long (β < 0). This is expected, not an error.")

with tab_trades:
    st.subheader("Trade log (existing backtest run)")
    st.caption(
        "Reads research/trade_log_dump.json directly — a single AVAX/LINK, 30-day "
        "backtest with 6 completed trades. Not re-run here (nautilus/run_backtest.py "
        "currently can't run against the 30m data on disk; see README). "
        "Directional only — not enough trades for statistical conclusions."
    )
    trades = load_trade_log()
    if trades.empty:
        st.warning("research/trade_log_dump.json not found or empty.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Trades", len(trades))
        m2.metric("Net realized P&L", f"{trades['realized_pnl_net'].sum():.2f} USDT")
        m3.metric("Win rate", f"{(trades['realized_pnl_net'] > 0).mean():.0%}")
        m4.metric("Avg hours held", f"{trades['hours_held'].mean():.1f}")

        st.plotly_chart(equity_curve_chart(trades), use_container_width=True, key="chart_trades_equity")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(exit_reason_bar(trades), use_container_width=True, key="chart_trades_exit_reason")
        with c2:
            st.plotly_chart(pnl_distribution_chart(trades), use_container_width=True, key="chart_trades_pnl_dist")
        st.dataframe(trades, use_container_width=True)
