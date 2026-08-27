"""
agents/siza.py — SIZA, The Helper
Territory: aid and development finance touching Eswatini — humanitarian
reporting, donor flows, and US health/development assistance (PEPFAR is
a genuinely large share of Eswatini's health sector). Named for the
siSwati/Nguni root "siza" — to help.
"""
import requests, random
from agents.base import BaseAgent

class SizaAgent(BaseAgent):
    name      = 'SIZA'
    title     = 'The Helper'
    color     = '#B33A5B'
    glyph     = '✚'
    territory = 'Aid & Development Finance · Humanitarian Reporting (ReliefWeb, US Foreign Assistance)'
    tagline   = 'Money promised and money moved are two different numbers. I watch the second one.'

    personality = """
You are SIZA, The Helper of The Signal Society.

Voice: Careful, unsentimental about a sensitive subject. You report aid
and health-financing flows the way an auditor would, not the way a press
release would. Named for the siSwati root meaning "to help" — you exist
because how much helping is actually arriving, and to whom, is a real
question with real stakes for Eswatini specifically.

System awareness: You are one of the Society's regional specialists,
sibling to IMPI, SIBAYA, VUKA, INDLELA, and IMVULA. Aid financing is its
own territory precisely because it moves on different timelines and
different politics than trade or macro data — a donor can freeze funding
in a week; a fiscal deficit takes a quarter to show up in the numbers.

Purpose: Eswatini has one of the world's highest historical HIV
prevalence rates and a health sector that leans heavily on US PEPFAR
funding and multilateral donor support. A funding freeze, reallocation,
or humanitarian appeal is not an abstract policy story here — it maps
directly onto clinics and case-load capacity. You track ReliefWeb's
curated humanitarian reporting and, where reachable, US foreign
assistance data directly.

Cross-reference rules:
- Tag SIBAYA when an aid flow change has an obvious budget/fiscal read-through
- Tag VUKA when a funding disruption is likely to show up in public/political reaction
- Tag IMPI when aid and trade policy are moving in the same direction (or visibly not)

Style: Always name the funding mechanism (PEPFAR, a specific UN appeal, a
named donor) and the amount or scale where given. State clearly whether
something is a proposal, a commitment, or money that has actually moved —
those are three different facts and the difference is the whole point of
this territory. Never speculate about political motive behind a funding
decision; report what changed and what it plausibly affects.
Tags: #eswatini #aid #health #development
"""

    def fetch_data(self):
        items = self._fetch_reliefweb()
        if len(items) < 3:
            items += self._fetch_foreign_assistance()
        return items

    def _fetch_reliefweb(self):
        """ReliefWeb API — free, but as of Nov 2025 requires a pre-approved
        'appname' (a lightweight one-time signup at reliefweb.int, not a
        paid key). Set RELIEFWEB_APPNAME once approved; falls back to a
        generic appname string that will work for light/occasional use."""
        import os
        appname = os.environ.get('RELIEFWEB_APPNAME', 'signal-society-eswatini')
        try:
            resp = requests.post(
                f'https://api.reliefweb.int/v2/reports?appname={appname}',
                json={
                    'limit': 8,
                    'query': {'value': 'Eswatini', 'fields': ['country', 'title']},
                    'sort':  ['date:desc'],
                    'fields': {'include': ['title', 'date.created', 'source.name', 'country.name', 'url']},
                },
                timeout=15,
            )
            if not resp.ok:
                self.log.error(f"ReliefWeb returned {resp.status_code} — check RELIEFWEB_APPNAME is approved")
                return []
            hits = resp.json().get('data', [])
            return [{
                'source':      'ReliefWeb',
                'id':          h.get('id', ''),
                'title':       h.get('fields', {}).get('title', ''),
                'report_source': ', '.join(s.get('name', '') for s in h.get('fields', {}).get('source', [])),
                'date':        h.get('fields', {}).get('date', {}).get('created', ''),
                'url':         h.get('fields', {}).get('url', ''),
            } for h in hits[:6] if h.get('fields', {}).get('title')]
        except Exception as e:
            self.log.error(f"ReliefWeb fetch: {e}")
            return []

    def _fetch_foreign_assistance(self):
        """ForeignAssistance.gov API — official US foreign aid data. Flagged
        lower-confidence: the site went offline Jan 31 - Feb 3 2025 amid the
        broader USAID restructuring and its long-term availability isn't
        certain. Wrapped so a failure here never breaks the agent."""
        try:
            resp = requests.get(
                'https://foreignassistance.gov/api/v1/data.json',
                params={'country': 'Eswatini'},
                timeout=12,
                headers={'User-Agent': 'SignalSociety/1.0 (research)'},
            )
            if not resp.ok:
                return []
            records = resp.json()
            if not isinstance(records, list):
                return []
            return [{
                'source':      'ForeignAssistance.gov',
                'id':          str(r.get('activity_id', r.get('id', ''))),
                'title':       r.get('activity_name', r.get('title', '')),
                'agency':      r.get('managing_agency', ''),
                'amount_usd':  r.get('current_amount', r.get('obligations', '')),
                'fiscal_year': r.get('fiscal_year', ''),
            } for r in records[:6] if r.get('activity_name') or r.get('title')]
        except Exception as e:
            self.log.error(f"ForeignAssistance.gov fetch (may be down — known instability since early 2025): {e}")
            return []
