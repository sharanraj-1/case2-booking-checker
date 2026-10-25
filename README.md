# 📦 Pallet Pre-Flight

Hackathon submission for **Case 2 – Conversational Shipment Booking & Pre-Flight Error Checker**.

A public Streamlit app that books UK → EU pallet shipments by chat (or a guided form) and checks booking files for paperwork mistakes before they leave. Every booking gets: what's wrong, how serious it is and the exact fix; a carrier recommendation based on the seller's priority, with the reason; and a plain-English confirmation with next steps.

> **We use AI where language is messy and code where accuracy matters.**

## Try it

- **📄 Check a file** → **Try sample file** loads `test_bookings.xlsx` (18 bookings, one planted mistake per rule, plus edge cases). Click any row to open it.
- **💬 Book by chat** → describe a shipment in your own words, e.g. *"I need to send some mugs to Germany next week"*. It asks only for what's missing. Change things mid-way (*"make it 4 pallets"*, *"change it to Lyon"*, *"drop the candles"*, *"go with fastest"*) and watch the checks and carrier refresh, with an "Updated: Pallets 3 → 4 · Cost £540 → £720" note.
- Without an API key, the chat tab becomes a step-by-step form that collects the same fields and runs the same checks.

## Run locally

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt
streamlit run app.py
```

Optional, for the AI chat and the AI R-06 review: put your key in `.streamlit/secrets.toml` (git-ignored):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

or set the `ANTHROPIC_API_KEY` environment variable. The model is set in one place: `llm/config.py` (`claude-opus-5-5`, low effort).

## Run the tests

```bash
python test_engine.py          # engine: 22 tests, including the sample file vs expected results
pytest                         # everything: engine, chat merge logic, headless UI tests
```

| File | What it covers |
| --- | --- |
| `test_engine.py` | Every planted mistake in `test_bookings.xlsx` → expected rule, severity, status, carrier and cost. Also: leading-zero HS codes, 1% R-02 tolerance, R-03 both fixes, R-05 "no carrier fits" with pallets per carrier, 450 kg Fastest → B, Balanced → B on every route, R-06 keywords (and no false positives), DD-MM-YYYY dates, bad values never crashing, CSV loading, duplicates, orphans, AI review merge. |
| `tests/test_chat_state.py` | Chat merge logic as pure functions: add an item, update a field, relative edits ("+1 pallet"), remove an item by description, change pallets → re-check and diff, "make it Lyon" switches country, "Lyon, Germany" is asked about, synonyms, invalid values (Munich, Glasgow, bad dates), derived totals, apply-fix. |
| `tests/test_app.py` | Headless Streamlit (`AppTest`): no-key form mode, the sample file opens all 18 bookings without errors, file-mode "Apply this fix", the chat UI with a fake extractor (pallet change diff), and the guided form through to a confirmation. |
| `tests/test_chat_scripted.py` | Three real conversations against the API (vague start; missing fields; mid-conversation changes). **Skipped unless `ANTHROPIC_API_KEY` is set.** |

`make_test_file.py` regenerates `test_bookings.xlsx`.

## How it's built

```
app.py                 page shell: two tabs, header, glossary
engine.py              rules R-01..R-10, file loader, carrier recommender, ETA  ← single source of truth
chat_state.py          chat state: validate + merge patches, missing fields, questions, diffs (pure)
llm/config.py          model constant, key lookup (st.secrets → env)
llm/prompts.py         the two prompts (extraction, R-06 review)
llm/client.py          one JSON call: strips ```json fences, parses safely, retries once
llm/extract.py         chat message → patch
llm/r06.py             AI second opinion on ambiguous R-06 items (cached by description)
ui/results.py          the shared results component (both tabs)
ui/file_tab.py         upload, summary table, export, apply-fix on a copy
ui/chat_tab.py         chat, confirm, apply-fix
ui/guided_form.py      no-key step-by-step form (same state, same checks)
ui/panel.py            live side panel: booking, items, missing fields, live rule grid
ui/export.py           .xlsx download (Summary, Findings, Carrier options)
```

## Design decisions

### The LLM vs rules boundary

All ten rules, the booking status, the carrier choice, costs and delivery dates are plain Python in `engine.py`. The model never does maths or decides pass/fail, because one hallucinated pass on a planted error costs more than any feature gains.

The model has exactly two jobs:

1. **Extraction.** Each chat turn it returns only JSON: `{"booking_updates": {...}, "item_updates": [{"op": "add|update|remove", "match_sku_or_index": ..., "fields": {...}}], "reply_hint": "..."}`. Code then validates every value against the allowed values (cities per country, priorities, Warehouse/Business address, Yes/No), maps synonyms ("Frankfurt am Main" → Frankfurt, "a shop" → Business address, "cheap" → Cheapest), and merges it. Relative edits come back as `"+1"`, and **code** does the addition. If a value is ambiguous ("Germany" with no city, "Lyon, Germany", "Munich"), code asks, offering the allowed options. Even the reply is composed in code (`chat_state.build_reply`), so the assistant only ever asks for fields that are actually missing, one or two at a time, never re-asking.
2. **R-06 second opinion.** The keyword screen splits descriptions into clear hits (Red: power bank, Li-ion, perfume, hairspray, nail polish, vape, hand sanitiser…), negations it ignores (battery-free, alcohol-free, non-aerosol, candles), and ambiguous words (Advisory: wireless, battery, cleaning, cosmetics…). Only ambiguous items go to the model, which returns `{"contains_dg": "yes|no|unsure", "category", "why"}`. "Yes" adds an R-06 Red labelled **"Flagged by AI review – please confirm"**; "unsure" keeps the Advisory with the explanation; "no" removes nothing and shows "AI review: likely safe". The status is then recomputed by the engine's own status rule (`engine.apply_ai_review`).

Without a key, everything still works: chat becomes the guided form, R-06 is keyword-only, and AI notes are simply omitted.

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
- **No live rates, no paid APIs, no logins.** Pricing is only the fixed rate card.
- **Never crash:** the loader returns notices instead of raising (missing sheets/columns, orphan items, duplicate IDs, unreadable values), and each tab is wrapped so a bad file shows a message.

## Deploy (Streamlit Community Cloud)

1. Push this folder to a GitHub repository.
2. At [share.streamlit.io](https://share.streamlit.io), **Create app** → pick the repo, branch `main`, main file `app.py`.
3. Optional: **Advanced settings → Secrets**: `ANTHROPIC_API_KEY = "sk-ant-..."`. Without it, the app runs in form mode.
4. Deploy, then open the URL in an incognito window and on a phone. Wake it up shortly before judging (free apps sleep when idle).

`requirements.txt` is pinned; Python 3.12.
