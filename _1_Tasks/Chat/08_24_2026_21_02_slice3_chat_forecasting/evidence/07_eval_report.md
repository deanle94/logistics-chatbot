# Slice 2 routing eval (S2.7)

- Run: 2026-08-26T00:58:27+00:00
- Model: `anthropic:claude-haiku-4-5-20251001`
- Score: **18/18** correct tool + parameters (pass bar: at most 1 miss)
- Invented digits across the set: **0**
- Each question asked once, no retry: a retried eval measures its best attempt rather than its behaviour.

| # | Question | Expected | Verdict | Detail |
| --- | --- | --- | --- | --- |
| 1 | How many orders do we have in total? | stat · order_count · none | PASS | ['order_count'] by none, rows match the CSV |
| 2 | Show delayed orders by week from October to December 2025 | line · delayed_orders · week | PASS | ['delayed_orders'] by week, rows match the CSV |
| 3 | Which carrier has the highest delay rate? | bar · delay_rate · carrier | PASS | ['delay_rate'] by carrier, rows match the CSV |
| 4 | Compare on-time vs delayed orders per month | stacked · delayed_orders, delivered_orders · month | PASS | ['delivered_orders', 'delayed_orders'] by month, rows match the CSV |
| 5 | How many orders were delivered? | stat · delivered_orders · none | PASS | ['delivered_orders'] by none, rows match the CSV |
| 6 | What is the average delivery time? | stat · avg_delivery_time · none | PASS | ['avg_delivery_time'] by none, rows match the CSV |
| 7 | Show order volume per month in 2025 | line · order_count · month | PASS | ['order_count'] by month, rows match the CSV |
| 8 | Total quantity shipped by product category | bar · quantity · product_category | PASS | ['quantity'] by product_category, rows match the CSV |
| 9 | Delay rate by warehouse | bar · delay_rate · warehouse | PASS | ['delay_rate'] by warehouse, rows match the CSV |
| 10 | How many orders from US-E in July 2025? | stat · order_count · none | PASS | ['order_count'] by none, rows match the CSV |
| 11 | What's the weather in Hong Kong? | unsupported | PASS | refused, no figure stated |
| 12 | Write a poem about logistics | unsupported | PASS | refused, no figure stated |
| 13 | Delayed orders by destination city | unsupported | PASS | refused, no figure stated |
| 14 | Show me the delayed orders trend | follow_up | PASS | asked for the time_bucket |
| 15 | Predict demand for PENCIL-0213 for the next 4 months | forecast_line | PASS | forecast for PENCIL-0213, history matches the CSV |
| 16 | Forecast demand for CRAYON-0017 over the next 2 months | forecast_line | PASS | forecast for CRAYON-0017, history matches the CSV |
| 17 | How much inventory should I plan? | follow_up | PASS | asked for the sku |
| 18 | Predict demand for PAPER-0197 for the next 4 months | unsupported | PASS | refused, no figure stated |
