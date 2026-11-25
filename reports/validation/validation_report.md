# Refresh validation report

Vendor folder: `data/main/vendor`
**Overall: TRANSFORM**

## tv_media_weekly.csv: TRANSFORM
Verified spec claims: grain=weekly, calendar_system=media_445, week_start_day=monday, date_label=period_start
Transform: `apportion_by_day(week_start_day=monday, date_label=period_start)`
- [PASS] data: dates fall on monday, consistent with spec
- [WARN] data: 31 weeks cross a month end and must be split
- [TRANSFORM] contract: weekly rows: split each week across its days, then sum by calendar month
- [WARN] contract: file carries period columns ['media_period', 'media_year']: never join these to a calendar-month key
- [TRANSFORM] contract: apportioning conserves spend to the cent (total 24,296,495.32)

## digital_monthly.csv: PASS
Verified spec claims: grain=monthly, calendar_system=gregorian, week_start_day=not_applicable, date_label=period_start
- [PASS] contract: calendar months (LLM and spec scan agree), joins directly

## email_monthly.csv: PASS
Verified spec claims: grain=monthly, calendar_system=gregorian, week_start_day=not_applicable, date_label=period_start
- [PASS] contract: calendar months (LLM and spec scan agree), joins directly

## sales_monthly.csv: PASS
Verified spec claims: grain=monthly, calendar_system=gregorian, week_start_day=not_applicable, date_label=period_start
- [PASS] contract: calendar months (LLM and spec scan agree), joins directly
