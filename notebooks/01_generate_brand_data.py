# Databricks notebook source
# MAGIC %md
# MAGIC # Brand Performance Manager — Step 1: Generate Brand Performance Data
# MAGIC
# MAGIC Generates 2 years (104 weeks) of synthetic CPG brand performance data for the
# MAGIC Brand Performance Manager multi-agent demo. Creates five Delta tables in
# MAGIC `{CATALOG}.brand_performance`:
# MAGIC
# MAGIC | Table | Rows | Description |
# MAGIC |-------|------|-------------|
# MAGIC | `brand_topline_metrics` | ~12,500 | Weekly brand sales, value/volume share by retailer & region |
# MAGIC | `market_share_decomposition` | ~12,500 | Share change decomposition into rate & distribution drivers |
# MAGIC | `insurgent_brand_tracker` | ~16,600 | Emerging competitor brand performance signals |
# MAGIC | `distribution_velocity` | ~41,600 | SKU-level ACV distribution & velocity metrics |
# MAGIC | `category_benchmarks` | ~6,200 | Category-level norms and benchmarks |

# COMMAND ----------

# MAGIC %md ## Configuration

# COMMAND ----------

CATALOG = "ar_dpcatalog"   # Update to your catalog
SCHEMA  = "brand_performance"

import random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from pyspark.sql import functions as F

random.seed(42)
np.random.seed(42)

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"Schema ready: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md ## Dimension Definitions

# COMMAND ----------

# 104 Saturdays of weekly data (2 years ending ~today)
_anchor = date(2025, 5, 17)  # most recent Saturday
WEEKS = [_anchor - timedelta(weeks=w) for w in range(103, -1, -1)]

RETAILERS = ["Walmart", "Target", "Kroger", "Total US"]
REGIONS   = ["Total US", "Northeast", "Southeast", "Midwest", "West"]
CATEGORIES = ["Infant Formula", "Baby Food", "Toddler Snacks"]

# Manufacturer portfolio brands
MFR_BRANDS = [
    {"brand": "NovaBaby",          "manufacturer": "NovaLife Nutrition", "category_shares": {"Infant Formula": 0.35, "Baby Food": 0.22, "Toddler Snacks": 0.28}},
    {"brand": "NovaBaby Organics", "manufacturer": "NovaLife Nutrition", "category_shares": {"Infant Formula": 0.08, "Baby Food": 0.12, "Toddler Snacks": 0.09}},
    {"brand": "NovaBaby Gentle",   "manufacturer": "NovaLife Nutrition", "category_shares": {"Infant Formula": 0.12, "Baby Food": 0.06, "Toddler Snacks": 0.05}},
    {"brand": "PuraMilk",          "manufacturer": "PuraMilk Corp",      "category_shares": {"Infant Formula": 0.28, "Baby Food": 0.19, "Toddler Snacks": 0.22}},
    {"brand": "BabyFirst",         "manufacturer": "BabyFirst Foods",    "category_shares": {"Infant Formula": 0.10, "Baby Food": 0.18, "Toddler Snacks": 0.14}},
    {"brand": "BabyEssentials",    "manufacturer": "Retailer PL",        "category_shares": {"Infant Formula": 0.07, "Baby Food": 0.23, "Toddler Snacks": 0.22}},
]

# Insurgent / challenger brands (fast-growing naturals / DTC)
INSURGENT_BRANDS = [
    {"brand": "Happy Roots",      "parent_company": "Happy Roots Inc",      "direct_competitor": True},
    {"brand": "TinyStart Organic","parent_company": "TinyStart Co",         "direct_competitor": True},
    {"brand": "Bobbie Natural",   "parent_company": "Bobbie Natural LLC",   "direct_competitor": True},
    {"brand": "ByGrain",          "parent_company": "ByGrain Nutrition",    "direct_competitor": False},
    {"brand": "Pure Petal",       "parent_company": "Pure Petal Foods",     "direct_competitor": True},
    {"brand": "Earthborn Baby",   "parent_company": "Earthborn Family",     "direct_competitor": False},
    {"brand": "Good Origins",     "parent_company": "Good Origins LLC",     "direct_competitor": True},
    {"brand": "Little Sprouts",   "parent_company": "Little Sprouts Co",    "direct_competitor": False},
]

# 20 SKUs for distribution_velocity
SKUS = [
    {"sku_id": "NB-IF-001", "sku_name": "NovaBaby Infant Formula 12oz",    "brand": "NovaBaby"},
    {"sku_id": "NB-IF-002", "sku_name": "NovaBaby Infant Formula 24oz",    "brand": "NovaBaby"},
    {"sku_id": "NB-IF-003", "sku_name": "NovaBaby Infant Formula 36oz",    "brand": "NovaBaby"},
    {"sku_id": "NB-OR-001", "sku_name": "NovaBaby Organics Infant 12oz",   "brand": "NovaBaby Organics"},
    {"sku_id": "NB-OR-002", "sku_name": "NovaBaby Organics Stage 2 16oz",  "brand": "NovaBaby Organics"},
    {"sku_id": "NB-GT-001", "sku_name": "NovaBaby Gentle Sensitive 12oz",  "brand": "NovaBaby Gentle"},
    {"sku_id": "NB-GT-002", "sku_name": "NovaBaby Gentle Sensitive 24oz",  "brand": "NovaBaby Gentle"},
    {"sku_id": "PM-IF-001", "sku_name": "PuraMilk Infant Formula 12oz",    "brand": "PuraMilk"},
    {"sku_id": "PM-IF-002", "sku_name": "PuraMilk Infant Formula 28oz",    "brand": "PuraMilk"},
    {"sku_id": "PM-PR-001", "sku_name": "PuraMilk Pro Advanced 16oz",      "brand": "PuraMilk"},
    {"sku_id": "BF-IF-001", "sku_name": "BabyFirst Infant Formula 12oz",   "brand": "BabyFirst"},
    {"sku_id": "BF-IF-002", "sku_name": "BabyFirst Organic Stage 1 20oz",  "brand": "BabyFirst"},
    {"sku_id": "BE-IF-001", "sku_name": "BabyEssentials Formula 18oz",     "brand": "BabyEssentials"},
    {"sku_id": "BE-BF-001", "sku_name": "BabyEssentials Baby Food 4oz",    "brand": "BabyEssentials"},
    {"sku_id": "HR-IF-001", "sku_name": "Happy Roots Organic Formula 12oz","brand": "Happy Roots"},
    {"sku_id": "TS-OR-001", "sku_name": "TinyStart Organic Stage 1 16oz",  "brand": "TinyStart Organic"},
    {"sku_id": "BN-IF-001", "sku_name": "Bobbie Natural Infant Formula",   "brand": "Bobbie Natural"},
    {"sku_id": "GP-SN-001", "sku_name": "ByGrain Puffs Multipack 8oz",     "brand": "ByGrain"},
    {"sku_id": "PP-BF-001", "sku_name": "Pure Petal Stage 2 Pouches 4oz",  "brand": "Pure Petal"},
    {"sku_id": "LS-BF-001", "sku_name": "Little Sprouts Organic 4oz",      "brand": "Little Sprouts"},
]

# COMMAND ----------

# MAGIC %md ## 1. brand_topline_metrics

# COMMAND ----------

def _share_trend(week_idx: int, base: float, drift: float, volatility: float) -> float:
    """Simulate a realistic share trend with drift and noise."""
    trend = base + drift * (week_idx / 103)
    noise = np.random.normal(0, volatility)
    return max(0.5, min(95.0, round(trend + noise, 3)))


def _retailer_multiplier(retailer: str) -> float:
    return {"Walmart": 3.2, "Target": 1.8, "Kroger": 1.5, "Total US": 1.0}[retailer]


def _region_multiplier(region: str) -> float:
    return {"Total US": 2.5, "Northeast": 0.6, "Southeast": 0.65, "Midwest": 0.55, "West": 0.7}[region]


# Share drift per brand (over 104 weeks) in ppt
SHARE_DRIFT = {
    "NovaBaby":          -2.5,   # losing to insurgents
    "NovaBaby Organics": +0.8,   # premium growing
    "NovaBaby Gentle":   -0.5,   # flat/slight decline
    "PuraMilk":          -2.0,   # losing share
    "BabyFirst":         -0.3,   # roughly flat
    "BabyEssentials":    +1.5,   # private label growing
}

rows = []
for category in CATEGORIES:
    for retailer in RETAILERS:
        for region in REGIONS:
            for w_idx, week_end in enumerate(WEEKS):
                # Calculate shares for all brands in this week/retailer/region/category
                base_shares = {b["brand"]: b["category_shares"][category] * 100 for b in MFR_BRANDS}
                week_shares = {}
                total = 0.0
                for b in MFR_BRANDS:
                    bn = b["brand"]
                    drift = SHARE_DRIFT.get(bn, 0.0)
                    vol = 0.4 if "Organics" in bn else 0.6
                    s = _share_trend(w_idx, base_shares[bn], drift, vol)
                    # Regional variation
                    if region == "Northeast" and bn in ("NovaBaby Organics", "PuraMilk"):
                        s *= 1.08
                    elif region == "Southeast" and bn == "NovaBaby":
                        s *= 1.06
                    week_shares[bn] = s
                    total += s

                # Normalize to ~100%
                for bn in week_shares:
                    week_shares[bn] = round(week_shares[bn] / total * 100, 3)

                # Seasonal index: slight Q4 bump (Oct-Dec)
                seasonal = 1.04 if week_end.month in (10, 11, 12) else 1.0

                for b in MFR_BRANDS:
                    bn = b["brand"]
                    vs = week_shares[bn]
                    vol_share = round(vs * np.random.uniform(0.93, 1.07), 3)
                    base_dollars = b["category_shares"][category] * 18_000_000
                    dollars = base_dollars * _retailer_multiplier(retailer) * _region_multiplier(region) * seasonal * np.random.uniform(0.92, 1.08)
                    units = int(dollars / np.random.uniform(18, 32))
                    yoy_dollar = round(np.random.normal(SHARE_DRIFT.get(bn, 0) * 0.4, 2.5), 2)
                    yoy_vol    = round(yoy_dollar - np.random.uniform(-1, 2), 2)
                    rows.append({
                        "week_ending":       week_end,
                        "brand":             bn,
                        "manufacturer":      b["manufacturer"],
                        "category":          category,
                        "subcategory":       f"{category} Stage 1",
                        "retailer":          retailer,
                        "region":            region,
                        "dollar_sales":      round(dollars, 2),
                        "unit_sales":        units,
                        "value_share_pct":   vs,
                        "volume_share_pct":  vol_share,
                        "yoy_dollar_chg_pct": yoy_dollar,
                        "yoy_volume_chg_pct": yoy_vol,
                        "l4w_value_share":   None,  # computed below
                        "l12w_value_share":  None,
                        "l52w_value_share":  None,
                    })

btm_df = pd.DataFrame(rows)

# Compute rolling share averages per brand/category/retailer/region
btm_df = btm_df.sort_values(["brand","category","retailer","region","week_ending"])
for col, window in [("l4w_value_share", 4), ("l12w_value_share", 12), ("l52w_value_share", 52)]:
    btm_df[col] = (
        btm_df.groupby(["brand","category","retailer","region"])["value_share_pct"]
        .transform(lambda x: x.rolling(window, min_periods=1).mean())
        .round(3)
    )

spark_btm = spark.createDataFrame(btm_df)
spark_btm.write.format("delta").mode("overwrite").option("overwriteSchema","true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.brand_topline_metrics")

n = spark.table(f"{CATALOG}.{SCHEMA}.brand_topline_metrics").count()
print(f"brand_topline_metrics: {n:,} rows")
assert n >= 10_000, f"Expected >=10,000 rows, got {n}"

# COMMAND ----------

# MAGIC %md ## 2. market_share_decomposition

# COMMAND ----------

DECOMP_DRIFT = {
    "NovaBaby":          {"dist": -0.8, "rate": -0.5, "pen": -0.6, "freq": -0.4, "basket": -0.2},
    "NovaBaby Organics": {"dist": +0.3, "rate": +0.2, "pen": +0.1, "freq": +0.1, "basket": +0.1},
    "NovaBaby Gentle":   {"dist": -0.1, "rate": -0.1, "pen": -0.1, "freq": -0.1, "basket": +0.0},
    "PuraMilk":          {"dist": -0.6, "rate": -0.5, "pen": -0.4, "freq": -0.3, "basket": -0.2},
    "BabyFirst":         {"dist": -0.1, "rate": +0.0, "pen": -0.1, "freq": +0.0, "basket": +0.0},
    "BabyEssentials":    {"dist": +0.5, "rate": +0.3, "pen": +0.2, "freq": +0.2, "basket": +0.3},
}

decomp_rows = []
for category in CATEGORIES:
    for retailer in RETAILERS:
        for region in REGIONS:
            for w_idx, week_end in enumerate(WEEKS):
                for b in MFR_BRANDS:
                    bn = b["brand"]
                    d = DECOMP_DRIFT.get(bn, {"dist":0,"rate":0,"pen":0,"freq":0,"basket":0})
                    factor = w_idx / 103

                    dist_c  = round(d["dist"]  * factor + np.random.normal(0, 0.15), 4)
                    rate_c  = round(d["rate"]  * factor + np.random.normal(0, 0.12), 4)
                    pen_c   = round(d["pen"]   * factor + np.random.normal(0, 0.10), 4)
                    freq_c  = round(d["freq"]  * factor + np.random.normal(0, 0.08), 4)
                    basket_c= round(d["basket"]* factor + np.random.normal(0, 0.06), 4)
                    total_chg = round(dist_c + rate_c + pen_c + freq_c + basket_c, 4)

                    price_idx = round(100 + np.random.normal(0, 3), 1)
                    promo_pct  = round(np.random.uniform(12, 38), 2)

                    decomp_rows.append({
                        "week_ending":                    week_end,
                        "brand":                          bn,
                        "category":                       category,
                        "retailer":                       retailer,
                        "region":                         region,
                        "share_change_ppt":               total_chg,
                        "distribution_contribution_ppt":  dist_c,
                        "rate_contribution_ppt":          rate_c,
                        "penetration_contribution_ppt":   pen_c,
                        "frequency_contribution_ppt":     freq_c,
                        "basket_size_contribution_ppt":   basket_c,
                        "price_index_vs_category":        price_idx,
                        "promotion_support_pct":          promo_pct,
                    })

msd_df = spark.createDataFrame(pd.DataFrame(decomp_rows))
msd_df.write.format("delta").mode("overwrite").option("overwriteSchema","true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.market_share_decomposition")

n = spark.table(f"{CATALOG}.{SCHEMA}.market_share_decomposition").count()
print(f"market_share_decomposition: {n:,} rows")
assert n >= 5_000, f"Expected >=5,000 rows, got {n}"

# COMMAND ----------

# MAGIC %md ## 3. insurgent_brand_tracker

# COMMAND ----------

# Insurgent share gain trajectories (ppt over 2 years)
INS_TRAJECTORY = {
    "Happy Roots":       {"base_share": 2.5,  "gain_52w": 1.8,  "base_acv": 45},
    "TinyStart Organic": {"base_share": 1.8,  "gain_52w": 1.5,  "base_acv": 38},
    "Bobbie Natural":    {"base_share": 2.1,  "gain_52w": 1.2,  "base_acv": 55},
    "ByGrain":           {"base_share": 0.8,  "gain_52w": 0.6,  "base_acv": 25},
    "Pure Petal":        {"base_share": 1.2,  "gain_52w": 0.9,  "base_acv": 30},
    "Earthborn Baby":    {"base_share": 0.5,  "gain_52w": 0.4,  "base_acv": 18},
    "Good Origins":      {"base_share": 0.9,  "gain_52w": 0.7,  "base_acv": 22},
    "Little Sprouts":    {"base_share": 0.6,  "gain_52w": 0.3,  "base_acv": 15},
}

ins_rows = []
for ib in INSURGENT_BRANDS:
    bn = ib["brand"]
    traj = INS_TRAJECTORY[bn]
    for category in CATEGORIES:
        for retailer in RETAILERS:
            for region in REGIONS:
                for w_idx, week_end in enumerate(WEEKS):
                    progress = w_idx / 103
                    base_s = traj["base_share"]
                    gain = traj["gain_52w"]
                    share_val   = round(max(0.1, base_s + gain * progress + np.random.normal(0, 0.12)), 3)
                    vol_share   = round(share_val * np.random.uniform(0.90, 1.10), 3)
                    acv         = round(min(98, traj["base_acv"] + gain * progress * 15 + np.random.normal(0, 1.5)), 1)
                    velocity    = round(np.random.uniform(800, 3500) * (1 + progress * 0.3), 2)
                    gain_4w     = round(np.random.normal(gain / 52 * 4, 0.08), 4)
                    gain_12w    = round(np.random.normal(gain / 52 * 12, 0.15), 4)
                    gain_52w_v  = round(np.random.normal(gain * progress, 0.25), 4)
                    threat      = round(min(100, (acv / 100 * 40) + (share_val * 10) + (gain * 15)), 1)

                    ins_rows.append({
                        "week_ending":           week_end,
                        "brand":                 bn,
                        "parent_company":        ib["parent_company"],
                        "category":              category,
                        "subcategory":           f"{category} Organic",
                        "retailer":              retailer,
                        "region":                region,
                        "value_share_pct":       share_val,
                        "volume_share_pct":      vol_share,
                        "acv_pct":               acv,
                        "velocity_per_mm_acv":   velocity,
                        "share_gain_4w_ppt":     gain_4w,
                        "share_gain_12w_ppt":    gain_12w,
                        "share_gain_52w_ppt":    gain_52w_v,
                        "is_direct_competitor":  ib["direct_competitor"],
                        "threat_score":          threat,
                    })

ibt_df = spark.createDataFrame(pd.DataFrame(ins_rows))
ibt_df.write.format("delta").mode("overwrite").option("overwriteSchema","true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.insurgent_brand_tracker")

n = spark.table(f"{CATALOG}.{SCHEMA}.insurgent_brand_tracker").count()
print(f"insurgent_brand_tracker: {n:,} rows")
assert n >= 15_000, f"Expected >=15,000 rows, got {n}"

# COMMAND ----------

# MAGIC %md ## 4. distribution_velocity

# COMMAND ----------

# Base ACV% and velocity per SKU (starting values)
SKU_BASE = {
    "NB-IF-001": {"acv": 88, "vel": 4200, "facings": 3, "shelf": "Eye Level"},
    "NB-IF-002": {"acv": 82, "vel": 5800, "facings": 4, "shelf": "Eye Level"},
    "NB-IF-003": {"acv": 65, "vel": 6900, "facings": 3, "shelf": "Eye Level"},
    "NB-OR-001": {"acv": 55, "vel": 2800, "facings": 2, "shelf": "Top Shelf"},
    "NB-OR-002": {"acv": 42, "vel": 1900, "facings": 2, "shelf": "Top Shelf"},
    "NB-GT-001": {"acv": 72, "vel": 3100, "facings": 2, "shelf": "Eye Level"},
    "NB-GT-002": {"acv": 58, "vel": 3600, "facings": 2, "shelf": "Eye Level"},
    "PM-IF-001": {"acv": 84, "vel": 3800, "facings": 3, "shelf": "Eye Level"},
    "PM-IF-002": {"acv": 76, "vel": 4900, "facings": 3, "shelf": "Eye Level"},
    "PM-PR-001": {"acv": 48, "vel": 2100, "facings": 2, "shelf": "Top Shelf"},
    "BF-IF-001": {"acv": 62, "vel": 2400, "facings": 2, "shelf": "Bottom Shelf"},
    "BF-IF-002": {"acv": 45, "vel": 1800, "facings": 1, "shelf": "Bottom Shelf"},
    "BE-IF-001": {"acv": 91, "vel": 5200, "facings": 3, "shelf": "Eye Level"},
    "BE-BF-001": {"acv": 85, "vel": 3400, "facings": 2, "shelf": "Eye Level"},
    "HR-IF-001": {"acv": 28, "vel": 1100, "facings": 1, "shelf": "Top Shelf"},
    "TS-OR-001": {"acv": 22, "vel":  900, "facings": 1, "shelf": "Top Shelf"},
    "BN-IF-001": {"acv": 35, "vel": 1400, "facings": 1, "shelf": "Top Shelf"},
    "GP-SN-001": {"acv": 18, "vel":  620, "facings": 1, "shelf": "Bottom Shelf"},
    "PP-BF-001": {"acv": 25, "vel":  780, "facings": 1, "shelf": "Top Shelf"},
    "LS-BF-001": {"acv": 14, "vel":  490, "facings": 1, "shelf": "Bottom Shelf"},
}

dist_rows = []
total_store_map = {"Walmart": 4700, "Target": 1900, "Kroger": 2800, "Total US": 28000}

for sku in SKUS:
    sid = sku["sku_id"]
    base = SKU_BASE[sid]
    category = (
        "Infant Formula" if "IF" in sid or "OR" in sid or "GT" in sid or "PR" in sid else
        "Toddler Snacks" if "SN" in sid else
        "Baby Food"
    )
    # insurgent SKUs grow in ACV; manufacturer mature SKUs may decline or stay flat
    is_insurgent = sku["brand"] in [ib["brand"] for ib in INSURGENT_BRANDS]
    acv_drift = +12 if is_insurgent else -2 if sku["brand"] in ("NovaBaby", "PuraMilk") else 0

    for retailer in RETAILERS:
        for region in REGIONS:
            total_stores = total_store_map[retailer]
            for w_idx, week_end in enumerate(WEEKS):
                progress = w_idx / 103
                acv_v  = round(max(10, min(98, base["acv"] + acv_drift * progress + np.random.normal(0, 1.2))), 1)
                vel_v  = round(max(200, base["vel"] * (1 + (0.08 if is_insurgent else -0.03) * progress) * np.random.uniform(0.92, 1.08)), 2)
                stores = int(acv_v / 100 * total_stores)
                oos    = round(max(0, np.random.normal(4 if is_insurgent else 2.5, 1.5)), 2)
                yoy_acv = round(np.random.normal(acv_drift * 0.5, 1.5), 2)
                yoy_vel = round(np.random.normal(6 if is_insurgent else -1.5, 4), 2)

                dist_rows.append({
                    "week_ending":           week_end,
                    "sku_id":                sid,
                    "sku_name":              sku["sku_name"],
                    "brand":                 sku["brand"],
                    "category":              category,
                    "retailer":              retailer,
                    "region":                region,
                    "acv_pct":               acv_v,
                    "stores_selling":        stores,
                    "total_stores":          total_stores,
                    "velocity_per_mm_acv":   vel_v,
                    "out_of_stock_rate_pct": oos,
                    "yoy_acv_chg_ppt":       yoy_acv,
                    "yoy_velocity_chg_pct":  yoy_vel,
                    "facings":               base["facings"],
                    "shelf_position":        base["shelf"],
                })

dv_df = spark.createDataFrame(pd.DataFrame(dist_rows))
dv_df.write.format("delta").mode("overwrite").option("overwriteSchema","true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.distribution_velocity")

n = spark.table(f"{CATALOG}.{SCHEMA}.distribution_velocity").count()
print(f"distribution_velocity: {n:,} rows")
assert n >= 40_000, f"Expected >=40,000 rows, got {n}"

# COMMAND ----------

# MAGIC %md ## 5. category_benchmarks

# COMMAND ----------

CAT_BASE = {
    "Infant Formula": {"total_sales": 420_000_000, "growth": 2.1, "leader_share": 35, "top3_conc": 75, "pl_share": 7,  "avg_price": 26.50, "promo": 18},
    "Baby Food":      {"total_sales": 280_000_000, "growth": 1.8, "leader_share": 28, "top3_conc": 68, "pl_share": 23, "avg_price": 3.20,  "promo": 22},
    "Toddler Snacks": {"total_sales": 190_000_000, "growth": 4.2, "leader_share": 24, "top3_conc": 60, "pl_share": 18, "avg_price": 5.80,  "promo": 25},
}

cb_rows = []
for category in CATEGORIES:
    base = CAT_BASE[category]
    for retailer in RETAILERS:
        for region in REGIONS:
            for w_idx, week_end in enumerate(WEEKS):
                size_mult = {"Total US": 1.0, "Northeast": 0.20, "Southeast": 0.22, "Midwest": 0.19, "West": 0.21}[region]
                ret_mult  = {"Total US": 1.0, "Walmart": 0.35, "Target": 0.18, "Kroger": 0.15}[retailer]
                sales = base["total_sales"] * size_mult * ret_mult * np.random.uniform(0.97, 1.03) / 52
                vel   = round(np.random.normal(3200, 350), 2)

                cb_rows.append({
                    "week_ending":                 week_end,
                    "category":                    category,
                    "retailer":                    retailer,
                    "region":                      region,
                    "total_category_dollar_sales": round(sales, 2),
                    "yoy_category_growth_pct":     round(base["growth"] + np.random.normal(0, 0.5), 2),
                    "avg_velocity_per_mm_acv":     vel,
                    "leader_value_share_pct":      round(base["leader_share"] + np.random.normal(0, 0.3), 2),
                    "top3_concentration_pct":      round(base["top3_conc"] + np.random.normal(0, 0.5), 2),
                    "private_label_share_pct":     round(base["pl_share"] + np.random.normal(0, 0.4), 2),
                    "avg_price_per_unit":          round(base["avg_price"] * np.random.uniform(0.97, 1.03), 2),
                    "promotional_pressure_pct":    round(base["promo"] + np.random.normal(0, 1.5), 2),
                })

cb_df = spark.createDataFrame(pd.DataFrame(cb_rows))
cb_df.write.format("delta").mode("overwrite").option("overwriteSchema","true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.category_benchmarks")

n = spark.table(f"{CATALOG}.{SCHEMA}.category_benchmarks").count()
print(f"category_benchmarks: {n:,} rows")
assert n >= 1_000, f"Expected >=1,000 rows, got {n}"

# COMMAND ----------

# MAGIC %md ## Validation Summary

# COMMAND ----------

print("=" * 65)
print("  BRAND PERFORMANCE DATA GENERATION COMPLETE")
print("=" * 65)

tables = [
    "brand_topline_metrics",
    "market_share_decomposition",
    "insurgent_brand_tracker",
    "distribution_velocity",
    "category_benchmarks",
]

for t in tables:
    n = spark.table(f"{CATALOG}.{SCHEMA}.{t}").count()
    print(f"  {CATALOG}.{SCHEMA}.{t:<35} → {n:>7,} rows")

# Validate share sum constraint
share_check = spark.sql(f"""
    SELECT week_ending, retailer, region, category,
           ROUND(SUM(value_share_pct), 1) AS total_share
    FROM {CATALOG}.{SCHEMA}.brand_topline_metrics
    WHERE week_ending = (SELECT MAX(week_ending) FROM {CATALOG}.{SCHEMA}.brand_topline_metrics)
    GROUP BY week_ending, retailer, region, category
    ORDER BY total_share DESC
    LIMIT 5
""")
print("\n  Sample share totals (should be ~100%):")
share_check.show()

print("""
Next steps:
  Run notebooks/02_generate_brand_docs.py to generate KA PDF documents.
  Then run notebooks/03_create_uc_functions.py to create UC Functions.
""")
