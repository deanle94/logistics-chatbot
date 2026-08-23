## Business definitions (the rulebook)

The calculator module owns these. They are the only definitions in the system.

| KPI                   | Rule                                                                     | Value    |
| --------------------- | ------------------------------------------------------------------------ | -------- |
| Total orders          | every row                                                                | 400      |
| Delivered orders      | `status = delivered`                                                     | 304      |
| Delayed orders        | `status = delayed`                                                       | 55       |
| On-time delivery rate | delivered ÷ (delivered + delayed)                                        | 84.7%    |
| Average delivery time | mean(`delivery_date` − `order_date`) over rows that have a delivery date | 370 rows |
| Demand                | `quantity` per SKU per month                                             | —        |

### How each status is treated

| status       | rows | In the on-time rate? |
| ------------ | ---- | -------------------- |
| `delivered`  | 304  | Yes — on time        |
| `delayed`    | 55   | Yes — late           |
| `exception`  | 11   | No                   |
| `in_transit` | 27   | No                   |
| `canceled`   | 3    | No                   |

**One rule behind all three exclusions:** the row does not state a delivery outcome. `in_transit` has not finished, `canceled` never shipped, and `exception` says something went wrong — not whether it arrived late. All three still count in Total orders.
