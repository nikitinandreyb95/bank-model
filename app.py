import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import io
from model.engine import run_model, to_dataframe
from model.assumptions import YEARS, BASE_ASSUMPTIONS

st.set_page_config(
    page_title="Bank Model · MX & CO",
    page_icon="🏦",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 16px 20px;
        border: 1px solid #e9ecef;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 6px 6px 0 0; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar: Scenario & Overrides ────────────────────────────────────────────
with st.sidebar:
    st.title("🏦 Bank Model")
    st.caption("Mexico & Colombia · Credit Product · 2025–2029")

    st.divider()

    scenario = st.selectbox("Scenario", ["Base", "Bull", "Bear"], index=0)

    st.divider()
    st.subheader("🇲🇽 Mexico overrides")
    mx_yield = st.slider("Yield rate, % (MX)", 20, 55,
        {yr: BASE_ASSUMPTIONS["MX"]["product"]["yield_rate"][yr] for yr in YEARS}[2025],
        help="Lending rate in 2025 — model tapers down over 5 years")
    mx_cof = st.slider("Cost of funds, % (MX)", 5, 20,
        BASE_ASSUMPTIONS["MX"]["product"]["cost_of_funds"][2025])
    mx_cor = st.slider("Cost of risk, % (MX)", 1, 15,
        int(BASE_ASSUMPTIONS["MX"]["product"]["cost_of_risk"][2025]))
    mx_port = st.number_input("Starting portfolio, $mn (MX)", 100, 2000,
        BASE_ASSUMPTIONS["MX"]["product"]["portfolio_start"], step=50)

    st.divider()
    st.subheader("🇨🇴 Colombia overrides")
    co_yield = st.slider("Yield rate, % (CO)", 20, 55,
        BASE_ASSUMPTIONS["CO"]["product"]["yield_rate"][2025])
    co_cof = st.slider("Cost of funds, % (CO)", 5, 20,
        BASE_ASSUMPTIONS["CO"]["product"]["cost_of_funds"][2025])
    co_cor = st.slider("Cost of risk, % (CO)", 1, 15,
        int(BASE_ASSUMPTIONS["CO"]["product"]["cost_of_risk"][2025]))
    co_port = st.number_input("Starting portfolio, $mn (CO)", 50, 1000,
        BASE_ASSUMPTIONS["CO"]["product"]["portfolio_start"], step=25)


# ── Build overrides dict ──────────────────────────────────────────────────────
def _taper(start_val, base_dict):
    """Keep relative changes from base, shift by override delta."""
    base_start = list(base_dict.values())[0]
    delta = start_val - base_start
    return {yr: round(v + delta, 1) for yr, v in base_dict.items()}

overrides = {
    "MX": {
        "yield_rate":    _taper(mx_yield, BASE_ASSUMPTIONS["MX"]["product"]["yield_rate"]),
        "cost_of_funds": _taper(mx_cof,   BASE_ASSUMPTIONS["MX"]["product"]["cost_of_funds"]),
        "cost_of_risk":  _taper(mx_cor,   BASE_ASSUMPTIONS["MX"]["product"]["cost_of_risk"]),
        "portfolio_start": mx_port,
    },
    "CO": {
        "yield_rate":    _taper(co_yield, BASE_ASSUMPTIONS["CO"]["product"]["yield_rate"]),
        "cost_of_funds": _taper(co_cof,   BASE_ASSUMPTIONS["CO"]["product"]["cost_of_funds"]),
        "cost_of_risk":  _taper(co_cor,   BASE_ASSUMPTIONS["CO"]["product"]["cost_of_risk"]),
        "portfolio_start": co_port,
    }
}

results = run_model(overrides=overrides, scenario=scenario)
mx_pnl  = results["MX"]["pnl"]
co_pnl  = results["CO"]["pnl"]
grp     = results["Group"]

COLORS = {"MX": "#5B6AF5", "CO": "#F5875B", "Group": "#2DBD8F"}

# ── Helper: plotly line chart ─────────────────────────────────────────────────
def line_chart(series: dict, title: str, yformat="$,.0f", suffix="$mn") -> go.Figure:
    fig = go.Figure()
    for name, data in series.items():
        fig.add_trace(go.Scatter(
            x=list(data.keys()), y=list(data.values()),
            name=name, mode="lines+markers",
            line=dict(color=COLORS.get(name, "#888"), width=2.5),
            marker=dict(size=7),
        ))
    fig.update_layout(
        title=dict(text=title, font_size=14),
        height=300, margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", y=-0.2),
        yaxis=dict(tickformat=yformat),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickvals=YEARS),
    )
    return fig


def bar_chart(series: dict, title: str) -> go.Figure:
    fig = go.Figure()
    for name, data in series.items():
        fig.add_trace(go.Bar(
            x=list(data.keys()), y=list(data.values()),
            name=name, marker_color=COLORS.get(name, "#888"),
        ))
    fig.update_layout(
        title=dict(text=title, font_size=14),
        barmode="group", height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", y=-0.2),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickvals=YEARS),
    )
    return fig


# ── Scenario badge ────────────────────────────────────────────────────────────
badge_color = {"Base": "🔵", "Bull": "🟢", "Bear": "🔴"}
st.markdown(f"## {badge_color[scenario]} Scenario: **{scenario}**")

# ── Top KPI metrics ───────────────────────────────────────────────────────────
last_yr = YEARS[-1]
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Group Net Income '29", f"${grp[last_yr]['net_income']:.0f}mn")
col2.metric("Group Revenue '29",    f"${grp[last_yr]['revenue']:.0f}mn")
col3.metric("Group Portfolio '29",  f"${grp[last_yr]['portfolio']:.0f}mn")
col4.metric("Group NIM '29",        f"{grp[last_yr]['nim']:.1f}%")
col5.metric("MX Net Income '29",    f"${mx_pnl[last_yr]['net_income']:.0f}mn",
            delta=f"CO: ${co_pnl[last_yr]['net_income']:.0f}mn")

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_group, tab_mx, tab_co, tab_compare = st.tabs(
    ["🌎 Group", "🇲🇽 Mexico", "🇨🇴 Colombia", "⚖️ MX vs CO"]
)

# GROUP TAB
with tab_group:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(line_chart(
            {"Group": {yr: grp[yr]["net_income"] for yr in YEARS}},
            "Group Net Income ($mn)"
        ), use_container_width=True)
    with c2:
        st.plotly_chart(line_chart(
            {"Group": {yr: grp[yr]["revenue"] for yr in YEARS}},
            "Group Total Revenue ($mn)"
        ), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(line_chart(
            {"Group": {yr: grp[yr]["portfolio"] for yr in YEARS}},
            "Group Portfolio ($mn)"
        ), use_container_width=True)
    with c4:
        st.plotly_chart(line_chart(
            {"Group": {yr: grp[yr]["nim"] for yr in YEARS}},
            "Group NIM (%)", yformat=".1f"
        ), use_container_width=True)


def country_tab(pnl: dict, country: str, flag: str):
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(line_chart(
            {country: {yr: pnl[yr]["net_income"] for yr in YEARS}},
            f"{flag} Net Income ($mn)"
        ), use_container_width=True)
        st.plotly_chart(line_chart(
            {country: {yr: pnl[yr]["portfolio"] for yr in YEARS}},
            f"{flag} Portfolio ($mn)"
        ), use_container_width=True)
    with c2:
        st.plotly_chart(line_chart(
            {country: {yr: pnl[yr]["nii"] for yr in YEARS}},
            f"{flag} NII ($mn)"
        ), use_container_width=True)
        st.plotly_chart(line_chart(
            {country: {yr: pnl[yr]["nim"] for yr in YEARS}},
            f"{flag} NIM (%)", yformat=".1f"
        ), use_container_width=True)

    st.subheader(f"{flag} Full P&L table")
    df = to_dataframe(pnl, country)
    st.dataframe(df.style.format("{:.1f}"), use_container_width=True)


with tab_mx:
    country_tab(mx_pnl, "MX", "🇲🇽")

with tab_co:
    country_tab(co_pnl, "CO", "🇨🇴")

# COMPARE TAB
with tab_compare:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(bar_chart(
            {
                "MX": {yr: mx_pnl[yr]["net_income"] for yr in YEARS},
                "CO": {yr: co_pnl[yr]["net_income"] for yr in YEARS},
            },
            "Net Income: MX vs CO ($mn)"
        ), use_container_width=True)
        st.plotly_chart(bar_chart(
            {
                "MX": {yr: mx_pnl[yr]["revenue"] for yr in YEARS},
                "CO": {yr: co_pnl[yr]["revenue"] for yr in YEARS},
            },
            "Total Revenue: MX vs CO ($mn)"
        ), use_container_width=True)
    with c2:
        st.plotly_chart(bar_chart(
            {
                "MX": {yr: mx_pnl[yr]["portfolio"] for yr in YEARS},
                "CO": {yr: co_pnl[yr]["portfolio"] for yr in YEARS},
            },
            "Portfolio: MX vs CO ($mn)"
        ), use_container_width=True)

        # NIM comparison — line
        st.plotly_chart(line_chart(
            {
                "MX": {yr: mx_pnl[yr]["nim"] for yr in YEARS},
                "CO": {yr: co_pnl[yr]["nim"] for yr in YEARS},
            },
            "NIM: MX vs CO (%)", yformat=".1f"
        ), use_container_width=True)

    # Side-by-side summary table
    st.subheader("Summary comparison")
    rows = ["NII ($mn)", "Fees ($mn)", "Total Revenue ($mn)", "Provisions ($mn)",
            "OpEx ($mn)", "Net Income ($mn)", "NIM (%)", "Cost-to-Income (%)"]
    keys = ["nii", "fees", "revenue", "provisions", "opex", "net_income", "nim", "cost_to_income"]

    summary = {}
    for label, key in zip(rows, keys):
        for yr in YEARS:
            summary[(label, f"MX {yr}")] = mx_pnl[yr][key]
            summary[(label, f"CO {yr}")] = co_pnl[yr][key]

    df_comp = pd.DataFrame(
        {label: {yr: mx_pnl[yr][key] for yr in YEARS} for label, key in zip(rows, keys)},
    ).T
    df_comp.columns = [str(y) + " MX" for y in YEARS]
    df_comp2 = pd.DataFrame(
        {label: {yr: co_pnl[yr][key] for yr in YEARS} for label, key in zip(rows, keys)},
    ).T
    df_comp2.columns = [str(y) + " CO" for y in YEARS]

    combined = pd.concat([df_comp, df_comp2], axis=1)
    combined = combined.reindex(sorted(combined.columns), axis=1)
    st.dataframe(combined.style.format("{:.1f}"), use_container_width=True)

st.divider()

# ── Excel download ────────────────────────────────────────────────────────────
def build_excel() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        to_dataframe(mx_pnl, "Mexico").to_excel(writer, sheet_name="MX_PnL")
        to_dataframe(co_pnl, "Colombia").to_excel(writer, sheet_name="CO_PnL")

        grp_rows = {
            "Portfolio ($mn)":  {yr: grp[yr]["portfolio"]  for yr in YEARS},
            "Revenue ($mn)":    {yr: grp[yr]["revenue"]    for yr in YEARS},
            "Net Income ($mn)": {yr: grp[yr]["net_income"] for yr in YEARS},
            "NIM (%)":          {yr: grp[yr]["nim"]        for yr in YEARS},
        }
        pd.DataFrame(grp_rows).T.to_excel(writer, sheet_name="Group_PnL")

        # Assumptions snapshot
        assump_rows = {
            "MX Yield (2025)": mx_yield, "MX CoF (2025)": mx_cof,
            "MX CoR (2025)": mx_cor, "MX Portfolio start": mx_port,
            "CO Yield (2025)": co_yield, "CO CoF (2025)": co_cof,
            "CO CoR (2025)": co_cor, "CO Portfolio start": co_port,
            "Scenario": scenario,
        }
        pd.Series(assump_rows, name="Value").to_frame().to_excel(writer, sheet_name="Inputs")

    return buf.getvalue()


col_dl1, col_dl2 = st.columns([1, 4])
with col_dl1:
    st.download_button(
        label="📥 Download Excel",
        data=build_excel(),
        file_name=f"bank_model_{scenario.lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
with col_dl2:
    st.caption(f"Exports current scenario ({scenario}) with all P&L tables and inputs snapshot")
