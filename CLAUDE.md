# Jeudi (jeudi.pierref.eu)

Campus meetup app (EPITA, SupBiotech, ESME, ISG, IPSA; Lyon). Code lives here, deployed from `app/` with
`cd app && docker compose -p jeudi up -d --build` behind the main Caddy (api on 192.168.1.64:8010). Spec in SPEC.md, TODO.md.

## Design decision (Morgan, 2026-11-05)
Look like Hoop, Yubo, Holy (the drink) and Mistral: loud and flat. Flat saturated fields (ink #17120f, pink #ff6b9d,
yellow #ffd84a, mint #5be3b0, orange #ff8a3d), heavy rounded type (Baloo 2 for display, DM Sans for text), pill buttons,
28px cards, one tilted sticker. This knowingly overrides the global "expressive colour never as a background field"
and "no soft radii" rules for this project only. Still banned: gradients, shadows at rest, glass, emoji icons,
violet/indigo, cream, eyebrows, monospace. Public page = colour chapters (landing.js/landing.css); app = app.css.
Gate: `inspect.mjs` (page run for `/`, `--app` for logged-in screens) must show 0 FAIL.

## Backend
`backend/main.py` is the teammate's base; Jeudi additions live in `backend/jeudi.py` (own tables). Auth: email code to sign up
or reset, password login (scrypt). Tests: `python -m pytest tests` (needs DEV_OTP=true).
