# Vendor file specification: TV media spend (national linear TV)

Delivered by: media agency, refreshed weekly.
File: tv_media_weekly.csv

## Grain and calendar
Data is delivered weekly. Each row is one vendor media-buying week, running Monday to Sunday.
The `week_start` column holds the Monday that begins the buying week.
Weeks roll up to the media (broadcast) calendar: 4-4-5 week periods per quarter, so periods do not line up with calendar months.
The media year begins on the Monday of the week containing 1 January. In 53-week years the extra week belongs to period 12.

## Columns
| column | type | notes |
|---|---|---|
| week_start | date | Monday of the buying week |
| media_year | int | media (broadcast) year |
| media_period | int | 1-12, 4-4-5 pattern |
| week_in_year | int | 1-53 |
| tv_spend | decimal | net media cost in USD, all networks |
