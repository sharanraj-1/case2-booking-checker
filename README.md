# 📦 Pallet Pre-Flight

Hackathon submission for **Case 2 – Conversational Shipment Booking & Pre-Flight Error Checker**.

A public Streamlit app that books UK → EU pallet shipments through a guided conversation (tap-to-answer, or free text with an API key) and checks booking files for paperwork mistakes before they leave. Every booking gets: what's wrong, how serious it is and the exact fix; a carrier recommendation based on the seller's priority, with the reason; and a plain-English confirmation with next steps.

> **We use AI where language is messy and code where accuracy matters.**

## Try it

- **Book a shipment.** Answer one question at a time. Every question comes with tap-to-answer options (country and city tiles, quick dates, +/− pallets, a simple product card), or you can type. With an API key you can also write freely: *"I need to send some mugs to Germany next week"*, *"make it 4 pallets"*, *"change it to Lyon"*, *"drop the candles"*. The **Your booking** card fills in live; tap any line to change it, and use +/− on pallets. Each change shows chips like `Pallets 3 → 4` `Cost £540.00 → £720.00`.
- **Check a file.** Drop one .xlsx (Bookings + Items sheets) or two CSVs. You get counts, one card per booking and a slide-over with the full results. "Fix it" applies a numeric fix to an in-app copy (with Undo; your file is never changed), and "Download results" exports an .xlsx. Need a demo? **Try an example** loads `test_bookings.xlsx`.
- **Compare with the market.** After the check, **Check live prices** fetches real prices from about 10 carriers (FedEx, K+N, DHL, Palletways…) for the same route and load via Pallet2Ship, next to our fixed-rate pick. Reference only.
- **Paperwork.** Every result has the 15-point **export invoice checklist** from business.gov.uk (what we already have vs what you add), a **draft commercial invoice** download (.xlsx, pre-filled), and the **rules for the UK → destination country** (EORI, export declaration, import VAT rate, UK-EU origin and the statement on origin text).
- **⌘K / Ctrl+K** opens the command menu (new booking, upload, example file, download, jump to any booking). **/** jumps to the booking chat.

Statuses are in plain words: **Good to go** (Ready), **OK to ship** (Ready with warnings) and **Can't ship yet** (Blocked).

## Run locally

On Windows, the quickest way: `powershell -ExecutionPolicy Bypass -File run.ps1` (creates the venv the first time), then open http://localhost:8501. **Keep that window open**: the page needs the server running, and shows "Can't reach the app" if it stops.

Or by hand:

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt
streamlit run app.py
```

The built front end (`pallet_ui/frontend/dist`) is committed, so Node isn't needed to run or deploy. To change the UI:

```bash
cd pallet_ui/frontend
npm install
npm run build                    # then refresh the Streamlit page
# or live reload: PALLET_UI_DEV=1 streamlit run app.py  +  npm run dev
```

For free-text chat and the AI R-06 review, all AI calls go through **OpenRouter** to Google's **Gemini** (`google/gemini-3.8-flash`, low reasoning effort; set in `llm/config.py`). Put your key in `.streamlit/secrets.toml` (git-ignored):

```toml
OPENROUTER_API_KEY = "sk-or-v1-..."
```

or set the `OPENROUTER_API_KEY` environment variable. `PALLET_NO_AI=1` forces guided mode. Without a key everything still works through the tap-to-answer questions.

## Run the tests

```bash
python test_engine.py          # engine: 22 tests, including the sample file vs expected results
pytest                         # everything: engine, chat merge logic, bridge (UI events), app smoke test
```

| File | What it covers |
| --- | --- |
| `test_engine.py` | Every planted mistake in `test_bookings.xlsx` → expected rule, severity, status, carrier and cost. Also: leading-zero HS codes, 1% R-02 tolerance, R-03 both fixes, R-05 "no carrier fits" with pallets per carrier, 450 kg Fastest → B, Balanced → B on every route, R-06 keywords (and no false positives), DD-MM-YYYY dates, bad values never crashing, CSV loading, duplicates, orphans, AI review merge. |
| `tests/test_chat_state.py` | Chat merge logic as pure functions: add an item, update a field, relative edits ("+1 pallet"), remove an item by description, change pallets → re-check and diff, "make it Lyon" switches country, "Lyon, Germany" is asked about, synonyms, invalid values (Munich, Glasgow, bad dates), derived totals, apply-fix. |
| `tests/test_bridge.py` | The UI's events end to end without a browser: a full no-AI conversation from empty to confirmed, typed answers, invalid answers, +1 pallet with its cost change, add/update/remove products, "Fix it" in chat and in file mode, undo, duplicate events ignored, AI extractor and its failure fallback, broken uploads, every sample booking serialising in plain English. |
| `tests/test_guardrails.py` | Chatbot guardrails with the real grounding filter: off-topic refusal, prompt injection changes nothing, questions get only curated answers, unknown questions aren't guessed, invented values are dropped, unit conversions pass; closest-city/country suggestions; invoice checklist, draft invoice and country rules; live prices are advisory, hidden when the load changes, and failures are reported. |
| `tests/test_app_smoke.py` | `app.py` starts with no key; the built front end is present. |
| `tests/test_chat_scripted.py` | Seven real conversations against the AI: vague start, missing fields, mid-conversation changes, off-topic, prompt injection, a paperwork question, and "Munich". **Skipped unless `OPENROUTER_API_KEY` is set.** |

`make_test_file.py` regenerates `test_bookings.xlsx`.

## How it's built

```
app.py                 Streamlit shell: full-screen React component, session, event callback
bridge.py              UI events → chat_state / engine; builds the plain-English payload (pure, tested)
engine.py              rules R-01..R-10, file loader, carrier recommender, ETA  ← single source of truth
chat_state.py          booking state: validate + merge patches, missing fields, diffs (pure)
knowledge.py           curated answers, export-invoice checklist, UK/EU country rules (sourced, no AI)
geo.py                 nearest served city/country for places we don't serve (coordinates, no AI)
live_rates.py          live market prices from Pallet2Ship's public quote form (advisory, cached)
llm/config.py          OpenRouter model constant, key lookup (st.secrets → env → secrets file)
llm/prompts.py         the two prompts (extraction + intent, R-06 review)
llm/client.py          one JSON call to OpenRouter: strips ```json fences, parses safely, retries once
llm/extract.py         chat message → intent, topic and a grounded patch (guardrails)
llm/r06.py             AI second opinion on ambiguous R-06 items (cached by description)
ui/export.py           .xlsx downloads: results (Summary, Findings, Carrier options) and the draft commercial invoice
pallet_ui/             the React front end as a Streamlit custom component
  frontend/src/App.tsx           nav, ⌘K palette, tabs, pending/skeleton state, toasts
  frontend/src/views/            BookView (chat + live card), Ask (answer controls), FileView, Results (shared bento)
  frontend/src/components/       fx (glass, tilt, magnetic buttons, reveal, skeletons), Hero3D (three.js), Nav, CommandPalette
```

**Why React inside Streamlit:** the brief needs a public Streamlit app, the Python engine as the single source of truth, and the API key kept server-side. A Streamlit custom component gives a full React interface (Tailwind, Framer Motion, cmdk, three.js) while every rule result still comes from Python. Each tap sends a small event (`{"type": "answer", "field": "pallets", "value": "3"}`); `bridge.handle_event` applies it, re-runs the engine, and sends back a payload the UI only renders. While Python works, the UI shows shimmer skeletons, never spinners. Next.js isn't used because it can't run inside Streamlit and would need a second server for the Python rules.

**UX principles:** one question at a time, always with a control that fits it; plain words first and rule IDs second; every problem says what's wrong, why it matters and how to fix it, with a one-tap fix where the fix is a number; nothing is hidden behind jargon (the HS code field links to the GOV.UK lookup). Motion respects the system's reduce-motion setting.

## Design decisions

### The LLM vs rules boundary

All ten rules, the booking status, the carrier choice, costs and delivery dates are plain Python in `engine.py`. The model never does maths or decides pass/fail, because one hallucinated pass on a planted error costs more than any feature gains.

The model has exactly two jobs:

1. **Extraction.** Each chat turn it returns only JSON: `{"intent": "booking|question|greeting|off_topic", "topic": <curated topic id or null>, "booking_updates": {...}, "item_updates": [{"op": "add|update|remove", "match_sku_or_index": ..., "fields": {...}}]}`. Code then validates every value against the allowed values (cities per country, priorities, Warehouse/Business address, Yes/No), maps synonyms ("Frankfurt am Main" → Frankfurt, "a shop" → Business address, "cheap" → Cheapest), and merges it. Relative edits come back as `"+1"`, and **code** does the addition. If a value is ambiguous ("Germany" with no city, "Lyon, Germany", "Munich"), code asks, offering the allowed options. Even the reply is composed in code (`chat_state.build_reply`), so the assistant only ever asks for fields that are actually missing, one or two at a time, never re-asking.
2. **R-06 second opinion.** The keyword screen splits descriptions into clear hits (Red: power bank, Li-ion, perfume, hairspray, nail polish, vape, hand sanitiser…), negations it ignores (battery-free, alcohol-free, non-aerosol, candles), and ambiguous words (Advisory: wireless, battery, cleaning, cosmetics…). Only ambiguous items go to the model, which returns `{"contains_dg": "yes|no|unsure", "category", "why"}`. "Yes" adds an R-06 Red labelled **"Flagged by AI review – please confirm"**; "unsure" keeps the Advisory with the explanation; "no" removes nothing and shows "AI review: likely safe". The status is then recomputed by the engine's own status rule (`engine.apply_ai_review`).

### Chatbot guardrails

The assistant may only take booking inputs, or suggest the closest valid input. Enforced in code, not just the prompt:

- **The model never talks to the customer.** Every reply is built in code: the next question, a closest-match suggestion, or a curated answer from `knowledge.py` picked by topic id. Off-topic requests (poems, code, other companies, "ignore your rules") get a fixed refusal and are steered back to the current question.
- **Grounding:** every number, place, name and HS code the model extracts must be traceable to the customer's own words (allowing unit conversions like "half a tonne" → 500 kg and relative edits like "add a pallet"); anything else is dropped and the customer is told. The model can't invent values.
- **Data, not instructions:** the message is passed as a JSON string labelled data; output is reduced to known keys and validated against the allowed values; input is capped at 1,500 characters.
- **Closest valid input:** a place we don't serve gets the nearest one we do, from real coordinates (`geo.py`): Munich → Frankfurt (~300 km), Glasgow → Leeds, Brussels → Rotterdam, Belgium → the Netherlands or France. The suggestion is shown first, highlighted, as a one-tap answer.
- **Questions** about HS codes, EORI, Incoterms, the commercial invoice, VAT and duty, origin and the statement on origin, dangerous goods, pallets, carriers and timing are answered only from checked text; anything else gets "I don't have a checked answer for that, so I won't guess."

### Paperwork and country rules

`knowledge.py` turns each booking into the business.gov.uk export-invoice checklist (15 points: what we already have from the booking, what to check because a rule flagged it, and what the seller must add, such as invoice number, buyer details and Incoterms) and a draft .xlsx invoice. Country rules cover the UK export side (GB EORI, export declaration, licences, records) and the import side for Germany/France/Netherlands (EU EORI, customs authority, standard import VAT 19%/20%/21%, UK-EU zero tariff only for UK-origin goods with a statement on origin, which is pre-filled). All advisory: they never change a rule result or the status. Sources: business.gov.uk "How to create an export invoice", gov.uk "Export goods", gov.uk "Claiming preferential rates of duty between the UK and EU".

### Live market prices

The brief's fixed rate card stays the only basis for the carrier pick and every check (judges test against it). On request, `live_rates.py` fetches real prices from **Pallet2Ship**'s public, login-free quote form (its robots.txt allows it; its terms forbid deep links, so the app names it without linking). It maps the load to a Pallet2Ship pallet type, sends an honest User-Agent, times out after 12 seconds, caches each route/load for 30 minutes, and hides the quotes as soon as the route or load changes. **P4D (myparceldelivery.com / p4d.co.uk)** isn't used: its prices come from a private backend with no public API.

Without a key, everything still works: every question has tap-to-answer controls and short typed answers go straight to the field being asked, R-06 is keyword-only, and AI notes are simply omitted.

### How R-05 drives eligibility (the circular rule)

R-05 depends on the chosen carrier, but we choose the carrier. We break the loop explicitly:

1. Compute weight per pallet = gross ÷ pallets.
2. Mark each carrier eligible if that's within its max kg/pallet (A 500, B 750, C 400).
3. Recommend **only** from eligible carriers, so R-05 passes for the pick. Exclusions are explained ("Carrier C excluded: 450 kg per pallet exceeds its 400 kg limit").
4. If none fit (or pallets are blank/zero), R-05 is Red, and each carrier gets the pallets it would need, ceil(gross ÷ max), with the new cost. The recommendation is made on those numbers. Example: 2,400 kg on 3 pallets → B needs 4 (£880), A 5 (£900), C 6 (£2,040), so Cheapest picks B on 4 pallets.

So 450 kg/pallet with priority Fastest falls back to Carrier B, and 600 kg/pallet gives B to every priority.

### Balanced scoring: minimax regret

Equal-weight min-max scoring picks Carrier C (the most expensive) on every route (C 2.0, B 1.92, A 1.0), which isn't balanced. Instead, for cost, transit and on-time we compute regret = (value − best) ÷ (worst − best) among eligible carriers, score each carrier by its **largest** regret, and pick the lowest (ties → lowest sum of regrets → lowest cost). A is worst on speed and reliability, C is worst on cost, and B is never the worst at anything, so B wins: *"never the priciest, slowest or least reliable option."*

### Other choices

- **Status:** any Red or missing/unreadable data → Blocked; only Amber → Ready with warnings; else Ready. "Data" findings (e.g. a booking with no items, an unknown city) block, because the booking can't be verified.
- **Dates** are always DD-MM-YYYY; Excel datetimes are accepted. "Today" is the Europe/London date. A ready date of today is not past.
- **ETA** = collection date (ready date, or today if it's past, rolled to the next UK working day) + transit in working days, skipping weekends and UK + destination public holidays (`holidays` library, offline). The notes say which holidays were skipped.
- **HS codes** are read as text; a 5-digit code gets "possible lost leading zero" and a one-click fix to `0` + code.
- **File mode never overwrites the seller's numbers.** "Apply this fix" edits an in-app copy of that booking only on an explicit click, says so, and can be undone. In chat, booking cartons and declared value are calculated from the items when the seller didn't state them, and labelled "(calculated)".
- **No paid APIs, no logins.** The carrier pick uses only the fixed rate card; live market prices are optional and advisory.
- **Never crash:** the loader returns notices instead of raising (missing sheets/columns, orphan items, duplicate IDs, unreadable values), and each tab is wrapped so a bad file shows a message.

## Deploy (Streamlit Community Cloud)

1. Push this folder to a GitHub repository (including `pallet_ui/frontend/dist`; `node_modules` is ignored).
2. At [share.streamlit.io](https://share.streamlit.io), **Create app** → pick the repo, branch `main`, main file `app.py`.
3. Optional: **Advanced settings → Secrets**: `OPENROUTER_API_KEY = "sk-or-v1-..."`. Without it, the app runs in guided (tap-to-answer) mode.
4. Deploy, then open the URL in an incognito window and on a phone. Wake it up shortly before judging (free apps sleep when idle).

`requirements.txt` is pinned; Python 3.12.
