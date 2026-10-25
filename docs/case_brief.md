# Case 2 – Conversational Shipment Booking & Pre-Flight Error Checker

Summarised from the team context file (25-10-2026). This is the spec the engine implements.

## What judges test

1. **Conversation (no file).** They describe a shipment in plain language, leaving details out. The app asks only for what's missing and reaches a complete booking. They change a detail mid-conversation (e.g. add a pallet) and check that the booking and its checks update.
2. **File upload.** They upload their own Bookings and Items sheets with planted rule violations.

For every booking: what's wrong, how serious and how to fix it; a recommended carrier based on the seller's priority, with the reason; a confirmation the seller understands, and what happens next. The link must work with no login.

## File layout

Row 1 title, row 2 headers, row 3 grey example (BK-001, Northfield Goods), data from row 4. The header row is found by the cell "Booking ID".

**Bookings:** Booking ID, Seller name, Origin city, Origin country, Destination city, Destination country, Destination type (Warehouse / Business address), Ready to ship date (DD-MM-YYYY), Seller priority (Cheapest / Fastest / Most reliable / Balanced), Pallets, Cartons, Total declared value, Currency (GBP), Total gross weight (kg), Delivery appointment booked (Yes / No).

**Items:** Booking ID, SKU, Description, HS code, Quantity (units), Unit price, Units per carton, Cartons, Unit weight (kg), Country of origin.

**Allowed values:** origin United Kingdom (London, Manchester, Birmingham, Leeds); destinations Germany (Berlin, Frankfurt, Hamburg), France (Paris, Lyon), Netherlands (Amsterdam, Rotterdam); currency GBP; item origin United Kingdom, China, India, Vietnam, Turkey, Germany.

## Rate card (fixed)

| Carrier | Service | Germany £/pallet | France £/pallet | Netherlands £/pallet | Transit (working days) | On time | Max kg/pallet |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Carrier A | Road economy | 180 | 170 | 160 | 5 | 92% | 500 |
| Carrier B | Road standard | 220 | 210 | 200 | 3 | 95% | 750 |
| Carrier C | Road express | 340 | 330 | 320 | 2 | 98% | 400 |

## Rulebook

| Rule | Severity | Check |
| --- | --- | --- |
| R-01 | Red | Every item has an HS code of 6+ digits |
| R-02 | Red | Declared value = Σ(qty × unit price), within 1% |
| R-03 | Red | Per item, units per carton × cartons = quantity |
| R-04 | Red | Booking cartons = Σ item cartons |
| R-05 | Red | Gross weight ÷ pallets ≤ chosen carrier's max kg/pallet |
| R-06 | Red | No lithium batteries, aerosols or flammable liquids |
| R-07 | Amber | Gross weight ≥ Σ(unit weight × qty) |
| R-08 | Amber | Warehouse delivery needs an appointment booked |
| R-09 | Amber | Every item has a country of origin |
| R-10 | Amber | Ready date not in the past (today counts as not past) |

Status: any Red → Blocked; only Amber → Ready with warnings; none → Ready.

## Known traps

- HS codes stored as numbers lose leading zeros (chapters 01–09): a 5-digit code fails R-01 with a "possible lost leading zero" note.
- Blank HS fails R-01; blank origin fails R-09.
- Dates may be Excel datetimes or text; always DD-MM-YYYY (05-11-2026 = 5 November).
- R-02 passes if |declared − items total| ÷ items total ≤ 1%.
- Pallets 0 or blank fail R-05 with a fix.
- Orphan items and bookings with no items are flagged.
- R-06: keywords + AI; avoid false positives (battery-free, alcohol-free, non-aerosol, candles); show the triggering phrase.
- File mode never overwrites the seller's numbers.

## Carrier logic

Weight per pallet decides eligibility; priority picks among eligible carriers. If none fit, each carrier gets pallets needed = ceil(gross ÷ max) and the pick is made on those costs (2,400 kg on 3 pallets → B needs 4 (£880), A 5 (£900), C 6 (£2,040)).

| Priority | Primary | Tie-breakers |
| --- | --- | --- |
| Cheapest | Lowest cost | Higher on-time, shorter transit |
| Fastest | Shortest transit | Higher on-time, lower cost |
| Most reliable | Highest on-time | Lower cost, shorter transit |
| Balanced | Minimax regret | Lowest sum of regrets, lowest cost |

Sanity check: BK-001 passes all 10 rules (1,080 × £5 = £5,400; 12 × 90 = 1,080; 90 cartons; net 540 kg ≤ 620 kg; 207 kg/pallet), and Cheapest picks Carrier A at £540 (B £660, C £1,020).

## Commercial invoice contents (UK government export guidance)

Seller and buyer details, description of goods, HS code, quantity, unit and total value, currency, country of origin, weights (net and gross) and the Incoterms. See https://www.gov.uk/guidance/international-trade-paperwork-the-basics.
