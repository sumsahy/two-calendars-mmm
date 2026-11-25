# Data specification: Brand sales

Source: brand finance, refreshed monthly.
File: sales_monthly.csv

## Grain and calendar
Monthly, calendar month. Net revenue booked in the calendar month.
The `month` column is the first day of the calendar month.

## Columns
| column | type | notes |
|---|---|---|
| month | date | first day of calendar month |
| net_revenue | decimal | net revenue in USD after rebates |
