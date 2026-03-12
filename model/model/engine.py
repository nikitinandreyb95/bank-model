import pandas as pd
from model.assumptions import YEARS, FX, SCENARIO_MULTIPLIERS, BASE_ASSUMPTIONS


def _apply_scenario(base: dict, multipliers: dict) -> dict:
    p = base.copy()
    p["portfolio_growth"] = {yr: v * multipliers["portfolio_growth"] for yr, v in base["portfolio_growth"].items()}
    p["yield_rate"]       = {yr: v * multipliers["yield_rate"]       for yr, v in base["yield_rate"].items()}
    p["cost_of_risk"]     = {yr: v * multipliers["cost_of_risk"]     for yr, v in base["cost_of_risk"].items()}
    return p


def _build_product(params: dict) -> dict:
    result = {}
    bal = params["portfolio_start"]
    for yr in YEARS:
        g = params["portfolio_growth"][yr] / 100
        new_bal = bal * (1 + g)
        avg_port = (bal + new_bal) / 2
        nii  = avg_port * (params["yield_rate"][yr] - params["cost_of_funds"][yr]) / 100
        fees = avg_port * params["fee_rate"][yr] / 100
        prov = avg_port * params["cost_of_risk"][yr] / 100
        result[yr] = {
            "portfolio": round(avg_port, 1),
            "yield_rate": params["yield_rate"][yr],
            "cost_of_funds": params["cost_of_funds"][yr],
            "nii": round(nii, 1),
            "fees": round(fees, 1),
            "revenue": round(nii + fees, 1),
            "provisions": round(prov, 1),
        }
        bal = new_bal
    return result


def _build_pnl(country: str, product: dict, tax_rate: float, opex_ratio: float) -> dict:
    pnl = {}
    for yr in YEARS:
        p = product[yr]
        opex = round(p["revenue"] * opex_ratio / 100, 1)
        ebt  = round(p["revenue"] - p["provisions"] - opex, 1)
        tax  = round(max(ebt, 0) * tax_rate / 100, 1)
        ni   = round(ebt - tax, 1)
        nim  = round(p["nii"] / p["portfolio"] * 100, 2) if p["portfolio"] else 0
        cti  = round(opex / p["revenue"] * 100, 1) if p["revenue"] else 0
        pnl[yr] = {**p, "opex": opex, "ebt": ebt, "tax": tax, "net_income": ni,
                   "nim": nim, "cost_to_income": cti}
    return pnl


def run_model(overrides: dict = None, scenario: str = "Base") -> dict:
    """
    overrides: dict like {"MX": {"yield_rate": {2025: 40, ...}, "cost_of_funds": {...}, ...}, "CO": {...}}
    Returns full model results by country + consolidated.
    """
    mult = SCENARIO_MULTIPLIERS[scenario]
    results = {}

    for country in ["MX", "CO"]:
        base  = BASE_ASSUMPTIONS[country]
        prod  = _apply_scenario(base["product"].copy(), mult)

        # Apply user overrides on top of scenario
        if overrides and country in overrides:
            for key, val in overrides[country].items():
                if isinstance(val, dict):
                    prod[key] = val
                else:
                    prod[key] = val

        product_data = _build_product(prod)
        pnl = _build_pnl(country, product_data, base["tax_rate"], base["opex_ratio"])
        results[country] = {
            "pnl": pnl,
            "tax_rate": base["tax_rate"],
            "opex_ratio": base["opex_ratio"],
        }

    # Consolidated (USD)
    consolidated = {}
    for yr in YEARS:
        ni_usd_total = sum(
            results[c]["pnl"][yr]["net_income"] for c in ["MX", "CO"]
        )
        rev_usd_total = sum(
            results[c]["pnl"][yr]["revenue"] for c in ["MX", "CO"]
        )
        port_usd_total = sum(
            results[c]["pnl"][yr]["portfolio"] for c in ["MX", "CO"]
        )
        nii_usd_total = sum(
            results[c]["pnl"][yr]["nii"] for c in ["MX", "CO"]
        )
        consolidated[yr] = {
            "net_income": round(ni_usd_total, 1),
            "revenue": round(rev_usd_total, 1),
            "portfolio": round(port_usd_total, 1),
            "nim": round(nii_usd_total / port_usd_total * 100, 2) if port_usd_total else 0,
        }

    results["Group"] = consolidated
    return results


def to_dataframe(pnl: dict, label: str) -> pd.DataFrame:
    rows = {
        "Portfolio (avg, $mn)": {yr: pnl[yr]["portfolio"] for yr in YEARS},
        "NII ($mn)":            {yr: pnl[yr]["nii"]        for yr in YEARS},
        "Fees ($mn)":           {yr: pnl[yr]["fees"]       for yr in YEARS},
        "Total Revenue ($mn)":  {yr: pnl[yr]["revenue"]    for yr in YEARS},
        "Provisions ($mn)":     {yr: pnl[yr]["provisions"] for yr in YEARS},
        "OpEx ($mn)":           {yr: pnl[yr]["opex"]       for yr in YEARS},
        "EBT ($mn)":            {yr: pnl[yr]["ebt"]        for yr in YEARS},
        "Tax ($mn)":            {yr: pnl[yr]["tax"]        for yr in YEARS},
        "Net Income ($mn)":     {yr: pnl[yr]["net_income"] for yr in YEARS},
        "NIM (%)":              {yr: pnl[yr]["nim"]        for yr in YEARS},
        "Cost-to-Income (%)":   {yr: pnl[yr]["cost_to_income"] for yr in YEARS},
    }
    df = pd.DataFrame(rows).T
    df.columns = [str(y) for y in YEARS]
    df.index.name = label
    return df
