# Vendor file specification: Email (HCP and patient CRM) spend

Delivered by: CRM vendor, refreshed monthly.
File: email_monthly.csv

## Grain and calendar
Monthly, calendar month. Costs are summed over all sends in the calendar month.
The `month` column is the first day of the calendar month.

## Columns
| column | type | notes |
|---|---|---|
| month | date | first day of calendar month |
| email_spend | decimal | send, platform and content cost, USD |
