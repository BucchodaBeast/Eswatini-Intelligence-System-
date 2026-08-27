# Signal Society

A multi-agent OSINT-style intelligence platform. Specialist agents each
watch a real public data source, post findings to a shared feed, and —
when independent agents converge on the same underlying pattern —
escalate into a Council debate, synthesized by Oracle into a sourced
intelligence brief and checked by Hermes.

## Agents

**Global (12):** VERA (arXiv), DUKE (SEC filings / GitHub trending), MIRA
(Reddit sentiment), SOL (cross-domain correlation), NOVA (infrastructure
permits), ECHO (Wayback deletions), KAEL (news metadata), FLUX (capital
flows), REX (Federal Register / regulatory), VIGIL (physical / supply
chain), LORE (patents), SPECTER (breaches / security).

**Regional — Eswatini / Southern Africa (3):** IMPI (AGOA & USTR trade
actions), SIBAYA (World Bank macro data for Eswatini + the SACU/CMA bloc),
VUKA (regional news & diplomacy, including the Eswatini–Taiwan angle).

**Synthesis:** COUNCIL (dynamic debate panel between agents with genuine
analytical tension), ORACLE (brief synthesis, self-rejecting when evidence
is thin), HERMES (verifies action items on high-confidence briefs).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # fill in at least GROQ_API_KEY
python app.py
```

Runs on local SQLite with zero further setup. Set `SUPABASE_URL` +
`SUPABASE_KEY` to switch to Postgres/Supabase in production.

## Deploy to Render

1. Push this repo to GitHub.
2. Render → New → Web Service, point it at the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command is already set via `Procfile` (gunicorn, 1 worker, 300s
   timeout — sized for the free tier).
5. Add the env vars from `.env.example` in Render's dashboard —
   `GROQ_API_KEY` at minimum.
6. Free tier spins down after 15 minutes idle. The app self-pings its own
   `/api/health` every 10 minutes to stay awake once it's up, but the
   first request after a cold start will be slow.

## Notes

- IMPI, SIBAYA, and VUKA are new — each is written against its API's
  documented schema but hasn't been live-tested outside this build
  environment (no outbound network access here). Watch the logs after the
  first deploy.
- The email digest (`send_digest`, cron at 07:00 UTC) silently no-ops
  until `DIGEST_EMAIL_TO`, `SMTP_USER`, and `SMTP_PASS` are all set.
