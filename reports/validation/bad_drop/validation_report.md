# Refresh validation report

Vendor folder: `data/drops/week_ending`
**Overall: BLOCK**

## tv_media_weekly.csv: BLOCK
Verified spec claims: grain=weekly, calendar_system=media_445, week_start_day=monday, date_label=period_start
Transform: `apportion_by_day(week_start_day=monday, date_label=period_start)`
- [BLOCK] data: spec implies dates fall on monday, data dates fall on sunday
- [WARN] data: 32 weeks cross a month end and must be split
- [TRANSFORM] contract: weekly rows: split each week across its days, then sum by calendar month
- [WARN] contract: file carries period columns ['media_period', 'media_year']: never join these to a calendar-month key

## digital_monthly.csv: PASS
Verified spec claims: grain=monthly, calendar_system=gregorian, week_start_day=not_applicable, date_label=period_start
- [PASS] contract: calendar months, joins directly

## email_monthly.csv: PASS
Verified spec claims: grain=monthly, calendar_system=gregorian, week_start_day=not_applicable, date_label=period_start
- [PASS] contract: calendar months, joins directly

## sales_monthly.csv: PASS
Verified spec claims: grain=monthly, calendar_system=gregorian, week_start_day=not_applicable, date_label=period_start
- [PASS] contract: calendar months, joins directly
