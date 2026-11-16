-- Lakeflow Declarative Pipeline: raw syndicated-style CSV drops -> governed Delta tables.
-- Source : /Volumes/ar_dpcatalog/brand_performance/raw_data/landing/<table>/*.csv
-- Target : ar_dpcatalog.brand_performance.<table>  (the tables the Genie spaces and the app read)
-- Auto Loader (read_files in a STREAMING TABLE) picks up only new files on each update, so a new
-- weekly drop is incremental. Explicit schemas keep column types identical to the original tables.
-- Expectations are warn-only: violations are counted in the pipeline event log, rows are kept.

CREATE OR REFRESH STREAMING TABLE brand_topline_metrics (
  CONSTRAINT valid_week EXPECT (week_ending IS NOT NULL),
  CONSTRAINT valid_brand EXPECT (brand IS NOT NULL),
  CONSTRAINT share_in_range EXPECT (value_share_pct BETWEEN 0 AND 100)
)
COMMENT 'Weekly brand-level sales and share metrics (synthetic CPG data) - ingested by Lakeflow from raw CSV'
AS SELECT week_ending, brand, manufacturer, category, subcategory, retailer, region, dollar_sales, unit_sales, value_share_pct, volume_share_pct, yoy_dollar_chg_pct, yoy_volume_chg_pct, l4w_value_share, l12w_value_share, l52w_value_share
FROM STREAM read_files(
  '/Volumes/ar_dpcatalog/brand_performance/raw_data/landing/brand_topline_metrics/',
  format => 'csv',
  header => true,
  schema => 'week_ending DATE, brand STRING, manufacturer STRING, category STRING, subcategory STRING, retailer STRING, region STRING, dollar_sales DOUBLE, unit_sales BIGINT, value_share_pct DOUBLE, volume_share_pct DOUBLE, yoy_dollar_chg_pct DOUBLE, yoy_volume_chg_pct DOUBLE, l4w_value_share DOUBLE, l12w_value_share DOUBLE, l52w_value_share DOUBLE'
);

CREATE OR REFRESH STREAMING TABLE market_share_decomposition (
  CONSTRAINT valid_week EXPECT (week_ending IS NOT NULL),
  CONSTRAINT valid_brand EXPECT (brand IS NOT NULL)
)
COMMENT 'Weekly brand share change decomposition into rate and distribution drivers - ingested by Lakeflow from raw CSV'
AS SELECT week_ending, brand, category, retailer, region, share_change_ppt, distribution_contribution_ppt, rate_contribution_ppt, penetration_contribution_ppt, frequency_contribution_ppt, basket_size_contribution_ppt, price_index_vs_category, promotion_support_pct
FROM STREAM read_files(
  '/Volumes/ar_dpcatalog/brand_performance/raw_data/landing/market_share_decomposition/',
  format => 'csv',
  header => true,
  schema => 'week_ending DATE, brand STRING, category STRING, retailer STRING, region STRING, share_change_ppt DOUBLE, distribution_contribution_ppt DOUBLE, rate_contribution_ppt DOUBLE, penetration_contribution_ppt DOUBLE, frequency_contribution_ppt DOUBLE, basket_size_contribution_ppt DOUBLE, price_index_vs_category DOUBLE, promotion_support_pct DOUBLE'
);

CREATE OR REFRESH STREAMING TABLE insurgent_brand_tracker (
  CONSTRAINT valid_week EXPECT (week_ending IS NOT NULL),
  CONSTRAINT valid_brand EXPECT (brand IS NOT NULL),
  CONSTRAINT share_in_range EXPECT (value_share_pct BETWEEN 0 AND 100)
)
COMMENT 'Weekly insurgent and challenger brand performance tracker - ingested by Lakeflow from raw CSV'
AS SELECT week_ending, brand, parent_company, category, subcategory, retailer, region, value_share_pct, volume_share_pct, acv_pct, velocity_per_mm_acv, share_gain_4w_ppt, share_gain_12w_ppt, share_gain_52w_ppt, is_direct_competitor, threat_score
FROM STREAM read_files(
  '/Volumes/ar_dpcatalog/brand_performance/raw_data/landing/insurgent_brand_tracker/',
  format => 'csv',
  header => true,
  schema => 'week_ending DATE, brand STRING, parent_company STRING, category STRING, subcategory STRING, retailer STRING, region STRING, value_share_pct DOUBLE, volume_share_pct DOUBLE, acv_pct DOUBLE, velocity_per_mm_acv DOUBLE, share_gain_4w_ppt DOUBLE, share_gain_12w_ppt DOUBLE, share_gain_52w_ppt DOUBLE, is_direct_competitor BOOLEAN, threat_score DOUBLE'
);

CREATE OR REFRESH STREAMING TABLE distribution_velocity (
  CONSTRAINT valid_week EXPECT (week_ending IS NOT NULL),
  CONSTRAINT valid_sku EXPECT (sku_id IS NOT NULL),
  CONSTRAINT acv_in_range EXPECT (acv_pct BETWEEN 0 AND 100)
)
COMMENT 'Weekly SKU-level ACV distribution and velocity metrics - ingested by Lakeflow from raw CSV'
AS SELECT week_ending, sku_id, sku_name, brand, category, retailer, region, acv_pct, stores_selling, total_stores, velocity_per_mm_acv, out_of_stock_rate_pct, yoy_acv_chg_ppt, yoy_velocity_chg_pct, facings, shelf_position
FROM STREAM read_files(
  '/Volumes/ar_dpcatalog/brand_performance/raw_data/landing/distribution_velocity/',
  format => 'csv',
  header => true,
  schema => 'week_ending DATE, sku_id STRING, sku_name STRING, brand STRING, category STRING, retailer STRING, region STRING, acv_pct DOUBLE, stores_selling BIGINT, total_stores BIGINT, velocity_per_mm_acv DOUBLE, out_of_stock_rate_pct DOUBLE, yoy_acv_chg_ppt DOUBLE, yoy_velocity_chg_pct DOUBLE, facings BIGINT, shelf_position STRING'
);

CREATE OR REFRESH STREAMING TABLE category_benchmarks (
  CONSTRAINT valid_week EXPECT (week_ending IS NOT NULL),
  CONSTRAINT valid_category EXPECT (category IS NOT NULL)
)
COMMENT 'Weekly category-level benchmarks and norms - ingested by Lakeflow from raw CSV'
AS SELECT week_ending, category, retailer, region, total_category_dollar_sales, yoy_category_growth_pct, avg_velocity_per_mm_acv, leader_value_share_pct, top3_concentration_pct, private_label_share_pct, avg_price_per_unit, promotional_pressure_pct
FROM STREAM read_files(
  '/Volumes/ar_dpcatalog/brand_performance/raw_data/landing/category_benchmarks/',
  format => 'csv',
  header => true,
  schema => 'week_ending DATE, category STRING, retailer STRING, region STRING, total_category_dollar_sales DOUBLE, yoy_category_growth_pct DOUBLE, avg_velocity_per_mm_acv DOUBLE, leader_value_share_pct DOUBLE, top3_concentration_pct DOUBLE, private_label_share_pct DOUBLE, avg_price_per_unit DOUBLE, promotional_pressure_pct DOUBLE'
);
