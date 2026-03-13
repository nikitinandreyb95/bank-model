# engine.py
import pandas as pd
from model.assumptions import (
    YEARS, PRODUCTS, CREDIT_PRODUCTS, FEE_PRODUCTS,
    AVG_BALANCE, CHURN, VINTAGE_LOSS_CURVE, VINTAGE_BALANCE_CURVE,
    SCENARIO_MULTIPLIERS, BASE_ASSUMPTIONS,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _apply_scenario(prod: dict, mult: dict) -> dict:
    p = {k: v.copy() if isinstance(v, dict) else v for k, v in prod.items()}
    for yr in YEARS:
        p["new_clients"][yr]  = round(prod["new_clients"][yr]  * mult["new_clients"])
        p["yield_rate"][yr]   = round(prod["yield_rate"][yr]   * mult["yield_rate"], 2)
        p["cost_of_risk"][yr] = round(prod["cost_of_risk"][yr] * mult["cost_of_risk"], 2)
        p["cac"][yr]          = round(prod["cac"][yr]          * mult["cac"], 1)
    return p


def _active_clients(new_clients: dict) -> dict:
    """Build active client stock using cohort churn per product."""
    return new_clients  # called per-product; churn applied in product calc


# ── Vintage engine ────────────────────────────────────────────────────────────

def calc_vintage(product: str, country: str, params: dict, scenario_mult: dict) -> dict:
    """
    Returns vintage matrix: cohort_year → {age → {balance, cum_loss, revenue, ltv}}
    Each cohort = clients acquired in a given year.
    """
    loss_curve    = VINTAGE_LOSS_CURVE[product]
    balance_curve = VINTAGE_BALANCE_CURVE[product]
    avg_bal       = AVG_BALANCE[product]
    vintages = {}

    for i, cohort_yr in enumerate(YEARS):
        nc = params["new_clients"][cohort_yr]
        cac_cost = params["cac"][cohort_yr] * nc / 1e6  # $mn total CAC

        cohort = {}
        cum_revenue = 0.0
        for age in range(1, 6):
            cal_yr_idx = i + age - 1
            if cal_yr_idx >= len(YEARS):
                break
            cal_yr = YEARS[cal_yr_idx]

            bal_remaining = nc * avg_bal * balance_curve[age - 1] / 1e6  # $mn
            spread = (params["yield_rate"][cal_yr] - params["cost_of_debt"][cal_yr]) / 100
            nii    = bal_remaining * spread
            svc    = nc * balance_curve[age - 1] * params["service_cost"][cal_yr] / 1e6
            loss   = nc * avg_bal * (loss_curve[age - 1] - (loss_curve[age - 2] if age > 1 else 0)) / 100 / 1e6

            cum_revenue += nii - svc - loss
            ltv = cum_revenue  # cumulative net revenue vs CAC

            cohort[age] = {
                "calendar_year":  cal_yr,
                "balance_mn":     round(bal_remaining, 2),
                "nii_mn":         round(nii, 2),
                "service_cost_mn":round(svc, 2),
                "incremental_loss_mn": round(loss, 2),
                "cum_loss_pct":   loss_curve[age - 1],
                "cum_revenue_mn": round(cum_revenue, 2),
                "ltv_vs_cac":     round(ltv / cac_cost, 2) if cac_cost > 0 else 0,
            }
        vintages[cohort_yr] = {"cohort": cohort, "cac_mn": round(cac_cost, 2), "new_clients": nc}

    return vintages


# ── Product P&L ───────────────────────────────────────────────────────────────

def calc_product(product: str, params: dict) -> dict:
    """Annual P&L for one product, building active client stock year-by-year."""
    churn_rate = CHURN[product] / 100
    avg_bal    = AVG_BALANCE.get(product, 0)
    active     = 0
    result     = {}

    for yr in YEARS:
        new_cl = params["new_clients"][yr]
        active = active * (1 - churn_rate) + new_cl

        if product == "Invest":
            # Pure fee-based: revenue = active clients × fee per client
            fee_mn  = round(active * params["fee_per_client"][yr] / 1e6, 2)
            svc_mn  = round(active * params["service_cost"][yr] / 1e6, 2)
            cac_mn  = round(new_cl * params["cac"][yr] / 1e6, 2)
            result[yr] = {
                "active_clients":  round(active),
                "new_clients":     new_cl,
                "balance_mn":      0.0,
                "nii_mn":          0.0,
                "fee_mn":          fee_mn,
                "revenue_mn":      fee_mn,
                "service_cost_mn": svc_mn,
                "cac_mn":          cac_mn,
                "cost_of_risk_mn": 0.0,
                "gross_profit_mn": round(fee_mn - svc_mn - cac_mn, 2),
                "nim_pct":         0.0,
                "spread_pct":      0.0,
            }
        else:
            # Spread-based (CC, SCC, BNPL, PL, Deposit)
            bal_mn  = round(active * avg_bal / 1e6, 2)
            spread  = (params["yield_rate"][yr] - params["cost_of_debt"][yr]) / 100
            nii     = round(bal_mn * spread, 2)
            svc_mn  = round(active * params["service_cost"][yr] / 1e6, 2)
            cac_mn  = round(new_cl * params["cac"][yr] / 1e6, 2)
            cor_mn  = round(bal_mn * params["cost_of_risk"][yr] / 100, 2) if product in CREDIT_PRODUCTS else 0.0
            nim     = round(nii / bal_mn * 100, 2) if bal_mn > 0 else 0.0

            result[yr] = {
                "active_clients":  round(active),
                "new_clients":     new_cl,
                "balance_mn":      bal_mn,
                "nii_mn":          nii,
                "fee_mn":          0.0,
                "revenue_mn":      nii,
                "service_cost_mn": svc_mn,
                "cac_mn":          cac_mn,
                "cost_of_risk_mn": cor_mn,
                "gross_profit_mn": round(nii - svc_mn - cac_mn - cor_mn, 2),
                "nim_pct":         nim,
                "spread_pct":      round(params["yield_rate"][yr] - params["cost_of_debt"][yr], 2),
            }
    return result


# ── Country P&L ───────────────────────────────────────────────────────────────

def calc_country(country: str, overrides: dict = None, scenario: str = "Base") -> dict:
    mult  = SCENARIO_MULTIPLIERS[scenario]
    base  = BASE_ASSUMPTIONS[country]
    products_pnl  = {}
    products_vint = {}

    for prod in PRODUCTS:
        p = _apply_scenario(base["products"][prod], mult)
        if overrides and prod in overrides:
            for key, val in overrides[prod].items():
                if isinstance(val, dict):
                    p[key] = val
                else:
                    p[key] = val
        products_pnl[prod] = calc_product(prod, p)
        if prod in CREDIT_PRODUCTS:
            products_vint[prod] = calc_vintage(prod, country, p, mult)

    # Aggregate country P&L
    country_pnl = {}
    for yr in YEARS:
        total_rev   = sum(products_pnl[pr][yr]["revenue_mn"]      for pr in PRODUCTS)
        total_svc   = sum(products_pnl[pr][yr]["service_cost_mn"] for pr in PRODUCTS)
        total_cac   = sum(products_pnl[pr][yr]["cac_mn"]          for pr in PRODUCTS)
        total_cor   = sum(products_pnl[pr][yr]["cost_of_risk_mn"] for pr in PRODUCTS)
        hq          = base["hq_cost"][yr]
        ebt         = round(total_rev - total_svc - total_cac - total_cor - hq, 2)
        tax         = round(max(ebt, 0) * base["tax_rate"] / 100, 2)
        ni          = round(ebt - tax, 2)
        total_bal   = sum(products_pnl[pr][yr]["balance_mn"] for pr in PRODUCTS)
        total_nii   = sum(products_pnl[pr][yr]["nii_mn"]     for pr in PRODUCTS)
        total_cl    = sum(products_pnl[pr][yr]["active_clients"] for pr in PRODUCTS)

        country_pnl[yr] = {
            "total_revenue_mn":   round(total_rev, 2),
            "service_cost_mn":    round(total_svc, 2),
            "cac_mn":             round(total_cac, 2),
            "cost_of_risk_mn":    round(total_cor, 2),
            "hq_cost_mn":         round(hq, 2),
            "ebt_mn":             ebt,
            "tax_mn":             tax,
            "net_income_mn":      ni,
            "total_balance_mn":   round(total_bal, 2),
            "total_nii_mn":       round(total_nii, 2),
            "total_clients":      total_cl,
            "nim_pct":            round(total_nii / total_bal * 100, 2) if total_bal > 0 else 0,
        }

    return {
        "pnl":      country_pnl,
        "products": products_pnl,
        "vintages": products_vint,
        "tax_rate": base["tax_rate"],
    }


# ── Full model ────────────────────────────────────────────────────────────────

def run_model(overrides: dict = None, scenario: str = "Base") -> dict:
    """
    overrides: {"MX": {"CC": {"new_clients": {2025: 55000, ...}, ...}}, "CO": {...}}
    """
    results = {}
    for country in ["MX", "CO"]:
        co = overrides.get(country, {}) if overrides else {}
        results[country] = calc_country(country, co, scenario)

    # Group consolidation
    group = {}
    for yr in YEARS:
        ni   = sum(results[c]["pnl"][yr]["net_income_mn"]    for c in ["MX", "CO"])
        rev  = sum(results[c]["pnl"][yr]["total_revenue_mn"] for c in ["MX", "CO"])
        bal  = sum(results[c]["pnl"][yr]["total_balance_mn"] for c in ["MX", "CO"])
        nii  = sum(results[c]["pnl"][yr]["total_nii_mn"]     for c in ["MX", "CO"])
        cl   = sum(results[c]["pnl"][yr]["total_clients"]    for c in ["MX", "CO"])
        group[yr] = {
            "net_income_mn":    round(ni,  2),
            "total_revenue_mn": round(rev, 2),
            "total_balance_mn": round(bal, 2),
            "total_nii_mn":     round(nii, 2),
            "total_clients":    cl,
            "nim_pct":          round(nii / bal * 100, 2) if bal > 0 else 0,
        }
    results["Group"] = group
    return results


# ── DataFrame helpers ─────────────────────────────────────────────────────────

def country_pnl_df(pnl: dict, country: str) -> pd.DataFrame:
    rows = {
        "Total Revenue ($mn)":   {yr: pnl[yr]["total_revenue_mn"]   for yr in YEARS},
        "  NII ($mn)":           {yr: pnl[yr]["total_nii_mn"]       for yr in YEARS},
        "Service Cost ($mn)":    {yr: pnl[yr]["service_cost_mn"]    for yr in YEARS},
        "CAC ($mn)":             {yr: pnl[yr]["cac_mn"]             for yr in YEARS},
        "Cost of Risk ($mn)":    {yr: pnl[yr]["cost_of_risk_mn"]    for yr in YEARS},
        "HQ Cost ($mn)":         {yr: pnl[yr]["hq_cost_mn"]         for yr in YEARS},
        "EBT ($mn)":             {yr: pnl[yr]["ebt_mn"]             for yr in YEARS},
        "Tax ($mn)":             {yr: pnl[yr]["tax_mn"]             for yr in YEARS},
        "Net Income ($mn)":      {yr: pnl[yr]["net_income_mn"]      for yr in YEARS},
        "Total Balance ($mn)":   {yr: pnl[yr]["total_balance_mn"]   for yr in YEARS},
        "NIM (%)":               {yr: pnl[yr]["nim_pct"]            for yr in YEARS},
        "Active Clients":        {yr: pnl[yr]["total_clients"]      for yr in YEARS},
    }
    df = pd.DataFrame(rows).T
    df.columns = [str(y) for y in YEARS]
    df.index.name = country
    return df.round(2)


def product_breakdown_df(products: dict, metric: str) -> pd.DataFrame:
    data = {prod: {yr: products[prod][yr][metric] for yr in YEARS} for prod in PRODUCTS}
    df = pd.DataFrame(data).T
    df.columns = [str(y) for y in YEARS]
    return df.round(2)


def vintage_df(vintages: dict, product: str, metric: str = "cum_loss_pct") -> pd.DataFrame:
    """
    Returns cohort × age matrix for a given metric.
    metric: cum_loss_pct | balance_mn | cum_revenue_mn | ltv_vs_cac
    """
    rows = {}
    for cohort_yr, vdata in vintages[product].items():
        row = {}
        for age, vals in vdata["cohort"].items():
            row[f"Age {age}"] = vals[metric]
        rows[str(cohort_yr)] = row
    df = pd.DataFrame(rows).T
    df.index.name = f"{product} vintage"
    return df.round(3)
