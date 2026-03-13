import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import io

from model.engine import run_model, country_pnl_df, product_breakdown_df, vintage_df
from model.assumptions import (
    YEARS, PRODUCTS, CREDIT_PRODUCTS, BASE_ASSUMPTIONS
)

st.set_page_config(page_title="Bank Model · MX & CO", page_icon="🏦", layout="wide")

st.markdown("""
<style>
div[data-testid="stMetricValue"] { font-size: 1.5rem; }
.stTabs [data-baseweb="tab"] { border-radius: 6px 6px 0 0; }
</style>
""", unsafe_allow_html=True)

COLORS = {
    "MX": "#5B6AF5", "CO": "#F5875B", "Group": "#2DBD8F",
    "CC": "#5B6AF5", "SCC": "#F5875B", "BNPL": "#2DBD8F",
    "PL": "#F5C518", "Deposit": "#A855F7", "Invest": "#EC4899",
}

PRODUCT_LABELS = {
    "CC": "Credit Card", "SCC": "Secured CC", "BNPL": "BNPL",
    "PL": "Personal Loan", "Deposit": "Deposit", "Invest": "Invest",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏦 Bank Model")
    st.caption("Mexico & Colombia · 6 Products · 2025–2029")
    st.divider()

    scenario = st.selectbox("Scenario", ["Base", "Bull", "Bear"])
    country_tab = st.radio("Edit inputs for", ["🇲🇽 Mexico", "🇨🇴 Colombia"], horizontal=True)
    c = "MX" if "Mexico" in country_tab else "CO"

    st.divider()
    st.subheader(f"{'🇲🇽' if c == 'MX' else '🇨🇴'} {c} — select product")
    sel_prod = st.selectbox("Product", PRODUCTS, format_func=lambda x: PRODUCT_LABELS[x])

    base_p = BASE_ASSUMPTIONS[c]["products"][sel_prod]

    st.caption("New clients per year")
    nc_cols = st.columns(5)
    new_clients_ov = {}
    for i, yr in enumerate(YEARS):
        new_clients_ov[yr] = nc_cols[i].number_input(
            str(yr), value=base_p["new_clients"][yr],
            step=1000, key=f"nc_{c}_{sel_prod}_{yr}", label_visibility="visible"
        )

    if sel_prod == "Invest":
        st.caption("Fee per client $/yr")
        fee_cols = st.columns(5)
        fee_ov = {}
        for i, yr in enumerate(YEARS):
            fee_ov[yr] = fee_cols[i].number_input(
                str(yr), value=float(base_p["fee_per_client"][yr]),
                step=5.0, key=f"fee_{c}_{sel_prod}_{yr}", label_visibility="visible"
            )
        yield_ov = base_p["yield_rate"]
        cod_ov   = base_p["cost_of_debt"]
    else:
        fee_ov = base_p.get("fee_per_client", {yr: 0 for yr in YEARS})
        st.caption("Yield rate % per year")
        yr_cols = st.columns(5)
        yield_ov = {}
        for i, yr in enumerate(YEARS):
            yield_ov[yr] = yr_cols[i].number_input(
                str(yr), value=float(base_p["yield_rate"][yr]),
                step=0.5, key=f"yr_{c}_{sel_prod}_{yr}", label_visibility="visible"
            )
        st.caption("Cost of Debt % per year")
        cd_cols = st.columns(5)
        cod_ov = {}
        for i, yr in enumerate(YEARS):
            cod_ov[yr] = cd_cols[i].number_input(
                str(yr), value=float(base_p["cost_of_debt"][yr]),
                step=0.5, key=f"cd_{c}_{sel_prod}_{yr}", label_visibility="visible"
            )

    st.caption("Service Cost $/client/yr")
    sc_cols = st.columns(5)
    svc_ov = {}
    for i, yr in enumerate(YEARS):
        svc_ov[yr] = sc_cols[i].number_input(
            str(yr), value=float(base_p["service_cost"][yr]),
            step=5.0, key=f"sc_{c}_{sel_prod}_{yr}", label_visibility="visible"
        )

    st.caption("CAC $/new client")
    cac_cols = st.columns(5)
    cac_ov = {}
    for i, yr in enumerate(YEARS):
        cac_ov[yr] = cac_cols[i].number_input(
            str(yr), value=float(base_p["cac"][yr]),
            step=5.0, key=f"cac_{c}_{sel_prod}_{yr}", label_visibility="visible"
        )

    if sel_prod in CREDIT_PRODUCTS:
        st.caption("Cost of Risk % per year")
        cr_cols = st.columns(5)
        cor_ov = {}
        for i, yr in enumerate(YEARS):
            cor_ov[yr] = cr_cols[i].number_input(
                str(yr), value=float(base_p["cost_of_risk"][yr]),
                step=0.5, key=f"cr_{c}_{sel_prod}_{yr}", label_visibility="visible"
            )
    else:
        cor_ov = base_p["cost_of_risk"]

    st.divider()
    st.caption("HQ Cost allocation ($mn/yr)")
    hq_base = BASE_ASSUMPTIONS[c]["hq_cost"]
    hq_cols = st.columns(5)
    hq_ov = {}
    for i, yr in enumerate(YEARS):
        hq_ov[yr] = hq_cols[i].number_input(
            str(yr), value=float(hq_base[yr]),
            step=0.1, key=f"hq_{c}_{yr}", label_visibility="visible"
        )


# ── Build overrides ───────────────────────────────────────────────────────────
overrides = {
    c: {
        sel_prod: {
            "new_clients":   new_clients_ov,
            "yield_rate":    yield_ov,
            "cost_of_debt":  cod_ov,
            "service_cost":  svc_ov,
            "cac":           cac_ov,
            "cost_of_risk":  cor_ov,
            "fee_per_client":fee_ov,
        }
    }
}

# patch HQ override into BASE_ASSUMPTIONS copy at runtime
import copy
patched = copy.deepcopy(BASE_ASSUMPTIONS)
patched[c]["hq_cost"] = hq_ov

# Temporarily patch — monkey-patch for this run
import model.assumptions as _assum
_orig_hq = {cc: _assum.BASE_ASSUMPTIONS[cc]["hq_cost"] for cc in ["MX", "CO"]}
_assum.BASE_ASSUMPTIONS[c]["hq_cost"] = hq_ov

results = run_model(overrides=overrides, scenario=scenario)

# Restore
for cc in ["MX", "CO"]:
    _assum.BASE_ASSUMPTIONS[cc]["hq_cost"] = _orig_hq[cc]

mx = results["MX"]
co = results["CO"]
grp = results["Group"]

# ── Charts helpers ────────────────────────────────────────────────────────────
def line_fig(series: dict, title: str, pct=False) -> go.Figure:
    fig = go.Figure()
    for name, data in series.items():
        fig.add_trace(go.Scatter(
            x=list(data.keys()), y=list(data.values()),
            name=name, mode="lines+markers",
            line=dict(color=COLORS.get(name, "#888"), width=2.5),
            marker=dict(size=7),
        ))
    fig.update_layout(
        title=dict(text=title, font_size=13), height=280,
        margin=dict(l=0, r=0, t=36, b=0),
        legend=dict(orientation="h", y=-0.25),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickvals=YEARS),
        yaxis=dict(ticksuffix="%" if pct else ""),
    )
    return fig


def bar_fig(series: dict, title: str, stacked=False) -> go.Figure:
    fig = go.Figure()
    for name, data in series.items():
        fig.add_trace(go.Bar(
            x=list(data.keys()), y=list(data.values()),
            name=name, marker_color=COLORS.get(name, "#888"),
        ))
    fig.update_layout(
        title=dict(text=title, font_size=13),
        barmode="stack" if stacked else "group",
        height=280, margin=dict(l=0, r=0, t=36, b=0),
        legend=dict(orientation="h", y=-0.25),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickvals=YEARS),
    )
    return fig


def heatmap_fig(df: pd.DataFrame, title: str, colorscale="RdYlGn") -> go.Figure:
    fig = go.Figure(go.Heatmap(
        z=df.values.tolist(),
        x=list(df.columns),
        y=list(df.index),
        colorscale=colorscale,
        text=[[f"{v:.2f}" for v in row] for row in df.values],
        texttemplate="%{text}",
        showscale=True,
    ))
    fig.update_layout(
        title=dict(text=title, font_size=13),
        height=220, margin=dict(l=0, r=0, t=36, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ── Scenario badge ────────────────────────────────────────────────────────────
badge = {"Base": "🔵", "Bull": "🟢", "Bear": "🔴"}
st.markdown(f"## {badge[scenario]} {scenario} scenario &nbsp;·&nbsp; editing **{c} — {PRODUCT_LABELS[sel_prod]}**")

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)
last = YEARS[-1]
k1.metric("Group NI '29",       f"${grp[last]['net_income_mn']:.1f}mn")
k2.metric("Group Revenue '29",  f"${grp[last]['total_revenue_mn']:.1f}mn")
k3.metric("Group Portfolio '29",f"${grp[last]['total_balance_mn']:.0f}mn")
k4.metric("Group NIM '29",      f"{grp[last]['nim_pct']:.1f}%")
k5.metric("MX Net Income '29",  f"${mx['pnl'][last]['net_income_mn']:.1f}mn")
k6.metric("CO Net Income '29",  f"${co['pnl'][last]['net_income_mn']:.1f}mn")

st.divider()

# ── Main tabs ─────────────────────────────────────────────────────────────────
t_group, t_mx, t_co, t_compare, t_vintage = st.tabs(
    ["🌎 Group", "🇲🇽 Mexico", "🇨🇴 Colombia", "⚖️ MX vs CO", "📊 Vintage"]
)


def render_country(res: dict, country: str, flag: str):
    pnl  = res["pnl"]
    prods = res["products"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(line_fig(
            {country: {yr: pnl[yr]["net_income_mn"] for yr in YEARS}},
            "Net Income ($mn)"
        ), use_container_width=True)
    with c2:
        st.plotly_chart(line_fig(
            {country: {yr: pnl[yr]["total_revenue_mn"] for yr in YEARS}},
            "Total Revenue ($mn)"
        ), use_container_width=True)
    with c3:
        st.plotly_chart(line_fig(
            {country: {yr: pnl[yr]["nim_pct"] for yr in YEARS}},
            "NIM (%)", pct=True
        ), use_container_width=True)

    c4, c5 = st.columns(2)
    with c4:
        st.plotly_chart(bar_fig(
            {PRODUCT_LABELS[p]: {yr: prods[p][yr]["revenue_mn"] for yr in YEARS} for p in PRODUCTS},
            f"{flag} Revenue by product ($mn)", stacked=True
        ), use_container_width=True)
    with c5:
        st.plotly_chart(bar_fig(
            {PRODUCT_LABELS[p]: {yr: prods[p][yr]["active_clients"] for yr in YEARS} for p in PRODUCTS},
            f"{flag} Active clients by product", stacked=True
        ), use_container_width=True)

    st.subheader("P&L Summary")
    st.dataframe(country_pnl_df(pnl, country).style.format("{:.1f}"), use_container_width=True)

    st.subheader("Net Income by product ($mn)")
    st.dataframe(
        product_breakdown_df(prods, "gross_profit_mn").style.format("{:.2f}"),
        use_container_width=True
    )


with t_group:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(line_fig(
            {"Group": {yr: grp[yr]["net_income_mn"] for yr in YEARS}},
            "Group Net Income ($mn)"
        ), use_container_width=True)
        st.plotly_chart(line_fig(
            {"Group": {yr: grp[yr]["total_balance_mn"] for yr in YEARS}},
            "Group Portfolio ($mn)"
        ), use_container_width=True)
    with c2:
        st.plotly_chart(line_fig(
            {"Group": {yr: grp[yr]["total_revenue_mn"] for yr in YEARS}},
            "Group Revenue ($mn)"
        ), use_container_width=True)
        st.plotly_chart(line_fig(
            {"Group": {yr: grp[yr]["nim_pct"] for yr in YEARS}},
            "Group NIM (%)", pct=True
        ), use_container_width=True)

with t_mx:
    render_country(mx, "MX", "🇲🇽")

with t_co:
    render_country(co, "CO", "🇨🇴")

with t_compare:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(bar_fig(
            {"MX": {yr: mx["pnl"][yr]["net_income_mn"] for yr in YEARS},
             "CO": {yr: co["pnl"][yr]["net_income_mn"] for yr in YEARS}},
            "Net Income MX vs CO ($mn)"
        ), use_container_width=True)
        st.plotly_chart(bar_fig(
            {"MX": {yr: mx["pnl"][yr]["total_balance_mn"] for yr in YEARS},
             "CO": {yr: co["pnl"][yr]["total_balance_mn"] for yr in YEARS}},
            "Portfolio MX vs CO ($mn)"
        ), use_container_width=True)
    with c2:
        st.plotly_chart(bar_fig(
            {"MX": {yr: mx["pnl"][yr]["total_revenue_mn"] for yr in YEARS},
             "CO": {yr: co["pnl"][yr]["total_revenue_mn"] for yr in YEARS}},
            "Revenue MX vs CO ($mn)"
        ), use_container_width=True)
        st.plotly_chart(line_fig(
            {"MX": {yr: mx["pnl"][yr]["nim_pct"] for yr in YEARS},
             "CO": {yr: co["pnl"][yr]["nim_pct"] for yr in YEARS}},
            "NIM MX vs CO (%)", pct=True
        ), use_container_width=True)

    st.subheader("MX full P&L")
    st.dataframe(country_pnl_df(mx["pnl"], "MX").style.format("{:.1f}"), use_container_width=True)
    st.subheader("CO full P&L")
    st.dataframe(country_pnl_df(co["pnl"], "CO").style.format("{:.1f}"), use_container_width=True)

# ── Vintage tab ───────────────────────────────────────────────────────────────
with t_vintage:
    st.subheader("Vintage analysis — credit products")
    vint_country = st.radio("Country", ["MX", "CO"], horizontal=True, key="vint_c")
    vint_prod    = st.selectbox("Product", CREDIT_PRODUCTS,
                                format_func=lambda x: PRODUCT_LABELS[x], key="vint_p")
    vint_metric  = st.selectbox("Metric", [
        ("cum_loss_pct",    "Cumulative loss rate (%)"),
        ("balance_mn",      "Outstanding balance ($mn)"),
        ("cum_revenue_mn",  "Cumulative net revenue ($mn)"),
        ("ltv_vs_cac",      "LTV / CAC ratio"),
    ], format_func=lambda x: x[1], key="vint_m")

    vres = results[vint_country]["vintages"]
    df_v = vintage_df(vres, vint_prod, vint_metric[0])

    colorscale = "RdYlGn" if vint_metric[0] in ("cum_revenue_mn", "ltv_vs_cac", "balance_mn") else "RdYlGn_r"
    st.plotly_chart(
        heatmap_fig(df_v, f"{vint_country} {PRODUCT_LABELS[vint_prod]} — {vint_metric[1]}", colorscale),
        use_container_width=True
    )

    st.caption("Rows = acquisition cohort year · Columns = age of cohort (years since acquisition)")
    st.dataframe(df_v.style.format("{:.3f}"), use_container_width=True)

    # LTV vs CAC summary
    if vint_metric[0] == "ltv_vs_cac":
        st.subheader("LTV/CAC by cohort at maturity (Age 5)")
        ltv_summary = {}
        for prod in CREDIT_PRODUCTS:
            df_ltv = vintage_df(vres, prod, "ltv_vs_cac")
            if "Age 5" in df_ltv.columns:
                ltv_summary[PRODUCT_LABELS[prod]] = df_ltv["Age 5"].to_dict()
        if ltv_summary:
            st.dataframe(pd.DataFrame(ltv_summary).style.format("{:.2f}").background_gradient(
                cmap="RdYlGn", axis=None
            ), use_container_width=True)

st.divider()

# ── Excel export ──────────────────────────────────────────────────────────────
def build_excel() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        country_pnl_df(mx["pnl"], "MX").to_excel(writer, sheet_name="MX_PnL")
        country_pnl_df(co["pnl"], "CO").to_excel(writer, sheet_name="CO_PnL")

        for prod in PRODUCTS:
            product_breakdown_df(mx["products"], "gross_profit_mn").to_excel(
                writer, sheet_name="MX_Products")
            product_breakdown_df(co["products"], "gross_profit_mn").to_excel(
                writer, sheet_name="CO_Products")
            break  # one sheet per country is enough here

        # Vintage sheets
        for country_code, vres in [("MX", mx["vintages"]), ("CO", co["vintages"])]:
            for prod in CREDIT_PRODUCTS:
                for metric, label in [
                    ("cum_loss_pct",   "Loss"),
                    ("cum_revenue_mn", "Revenue"),
                    ("ltv_vs_cac",     "LTV_CAC"),
                ]:
                    sname = f"{country_code}_{prod}_{label}"[:31]
                    vintage_df(vres, prod, metric).to_excel(writer, sheet_name=sname)

        # Group summary
        pd.DataFrame({
            "Net Income ($mn)":   {yr: grp[yr]["net_income_mn"]    for yr in YEARS},
            "Revenue ($mn)":      {yr: grp[yr]["total_revenue_mn"] for yr in YEARS},
            "Portfolio ($mn)":    {yr: grp[yr]["total_balance_mn"] for yr in YEARS},
            "NIM (%)":            {yr: grp[yr]["nim_pct"]          for yr in YEARS},
            "Total Clients":      {yr: grp[yr]["total_clients"]    for yr in YEARS},
        }).to_excel(writer, sheet_name="Group")

    return buf.getvalue()


col1, col2 = st.columns([1, 5])
with col1:
    st.download_button(
        "📥 Download Excel",
        data=build_excel(),
        file_name=f"bank_model_{scenario.lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
with col2:
    st.caption(f"Exports {scenario} scenario: P&L tables + vintage matrices for all credit products")

