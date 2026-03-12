YEARS = [2025, 2026, 2027, 2028, 2029]

# FX: local currency per 1 USD
FX = {
    "MX": {2025: 17.5, 2026: 17.8, 2027: 18.1, 2028: 18.4, 2029: 18.7},
    "CO": {2025: 4100, 2026: 4200, 2027: 4300, 2028: 4400, 2029: 4500},
}

# Scenario multipliers applied on top of base assumptions
SCENARIO_MULTIPLIERS = {
    "Base":  {"portfolio_growth": 1.0, "yield_rate": 1.0, "cost_of_risk": 1.0},
    "Bull":  {"portfolio_growth": 1.3, "yield_rate": 1.05, "cost_of_risk": 0.75},
    "Bear":  {"portfolio_growth": 0.6, "yield_rate": 0.95, "cost_of_risk": 1.5},
}

BASE_ASSUMPTIONS = {
    "MX": {
        "tax_rate": 30.0,
        "opex_ratio": 35.0,
        "product": {
            "portfolio_start": 500,
            "portfolio_growth": {2025: 10, 2026: 12, 2027: 10, 2028: 8,  2029: 7},
            "yield_rate":       {2025: 38, 2026: 36, 2027: 34, 2028: 32, 2029: 31},
            "cost_of_funds":    {2025: 11, 2026: 10, 2027: 9,  2028: 8,  2029: 8},
            "fee_rate":         {2025: 3,  2026: 3,  2027: 3,  2028: 3,  2029: 3},
            "cost_of_risk":     {2025: 6,  2026: 5.5,2027: 5,  2028: 4.5,2029: 4},
        }
    },
    "CO": {
        "tax_rate": 35.0,
        "opex_ratio": 38.0,
        "product": {
            "portfolio_start": 200,
            "portfolio_growth": {2025: 12, 2026: 14, 2027: 12, 2028: 10, 2029: 8},
            "yield_rate":       {2025: 35, 2026: 33, 2027: 31, 2028: 29, 2029: 28},
            "cost_of_funds":    {2025: 10, 2026: 9,  2027: 8,  2028: 7.5,2029: 7},
            "fee_rate":         {2025: 3,  2026: 3,  2027: 3,  2028: 3,  2029: 3},
            "cost_of_risk":     {2025: 6.5,2026: 6,  2027: 5.5,2028: 5,  2029: 4.5},
        }
    }
}
