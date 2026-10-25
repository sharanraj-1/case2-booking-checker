# Optional free data sources

No live data is needed to score well. These only enrich the output and must **never** change a rule result, a status or the carrier pick.

| Source | Use | Key | Status in this app |
| --- | --- | --- | --- |
| Python `holidays` library (offline) | Holiday-aware delivery dates for the UK (England) and the destination country | No | **Done**: ETAs skip weekends and public holidays, and name the holidays skipped |
| GOV.UK Trade Tariff API (`api.trade-tariff.service.gov.uk`) | Confirm an HS code exists, show its description, suggest codes for blanks. UK tariff, so don't quote its duty rates as EU duty | No | Phase 2, not built |
| Pallet2Ship public quote form (no login) | Live market prices from ~10 carriers for the same route and load, next to our fixed-rate pick | No | **Done**: on request only, 12 s timeout, cached 30 min, advisory |
| Frankfurter / ECB rates (`api.frankfurter.app/latest?from=GBP&to=EUR`) | Show declared value in EUR, labelled "reference only" with the rate date | No | Phase 2, not built |
| Open HS dataset (harmonized-system.csv, public domain) | Offline backup for HS checks | No | Phase 2, not built |
| HMRC Check EORI | Validate a GB EORI if the seller volunteers one (chat only) | No | Phase 2, not built |

Live freight prices are shown only as advisory market context next to the fixed rate card (Pallet2Ship). P4D has no public API, so it is not used. Skip traffic, port congestion and weather.

## Rules for using them

1. Advisory only, labelled "Advisory / reference only", with the source and date shown.
2. 2–3 second timeouts, `st.cache_data` with a TTL, and silent fallback (no error shown to the seller).
3. Read the API's OpenAPI spec for endpoints; don't guess them.
4. Add them only after Phase 1 is deployed and every test passes.
