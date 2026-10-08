-- Example analyst-facing query over the Gold campaign table.
-- Adjust the table name for your target catalog / warehouse.

SELECT
    platform,
    campaign_name,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    ROUND(SUM(spend), 2) AS spend,
    SUM(conversions) AS conversions,
    ROUND(SUM(revenue), 2) AS revenue,
    ROUND(SUM(clicks) * 1.0 / NULLIF(SUM(impressions), 0), 4) AS ctr,
    ROUND(SUM(spend) / NULLIF(SUM(clicks), 0), 2) AS cpc,
    ROUND(SUM(spend) * 1000.0 / NULLIF(SUM(impressions), 0), 2) AS cpm,
    ROUND(SUM(spend) / NULLIF(SUM(conversions), 0), 2) AS cpa,
    ROUND(SUM(revenue) / NULLIF(SUM(spend), 0), 2) AS roas
FROM gold_campaign_performance
GROUP BY platform, campaign_name
ORDER BY roas DESC;
