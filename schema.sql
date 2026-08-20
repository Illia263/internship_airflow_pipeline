-- Схема, яку залишив стажер.
CREATE TABLE trips (
    vendor  INTEGER,
    pickup  TIMESTAMP,
    dist    NUMERIC,
    total   NUMERIC,
    UNIQUE (vendor, pickup, dist)
);

-- Дашборд читає ЦЕ. Ламати не можна.
CREATE VIEW dashboard_daily_revenue AS
SELECT pickup::date AS d, count(*) AS trips, sum(total) AS revenue
FROM trips GROUP BY 1;
