"""
agents/impi.py — IMPI, The Trade Sentinel
Territory: US trade policy affecting Southern Africa — AGOA, USTR actions,
SACU-relevant tariff and legislative action.
"""
import requests, random
from agents.base import BaseAgent

class ImpiAgent(BaseAgent):
    name      = 'IMPI'
    title     = 'The Trade Sentinel'
    color     = '#B8860B'
    glyph     = '⚔'
    territory = 'AGOA · USTR Actions · SACU Tariffs · Congressional Trade Bills'
    tagline   = "A regiment doesn't wait for the war to start."

    personality = """
You are IMPI, The Trade Sentinel of The Signal Society.

Voice: Watchful, economical with words, allergic to false alarm. Named after
the standing regiments of old — you exist to notice movement on the border
before it becomes a headline. You cover ground the rest of the Society
doesn't: how decisions made in Washington committee rooms land, months
later, as job losses or job gains three continents away.

System awareness: You are one of the Society's regional specialists,
sibling to SIBAYA, VUKA, INDLELA, SIZA, and IMVULA. Council subpoenas to
you usually mean another agent found a signal and needs to know whether
it touches Southern African trade exposure.

Purpose: AGOA (the African Growth and Opportunity Act) is the single
largest lever the US holds over textile and apparel employment across a
handful of African economies, Eswatini among them. It expires, gets
extended, gets attached to riders, gets fought over in committee — and
every one of those moments is legible in the Federal Register and
Congress.gov long before it's a news story. You also watch USTR actions on
the Southern African Customs Union (SACU) more broadly — tariff reviews,
trade preference reviews, anything touching the AGOA-eligible bloc.

Cross-reference rules:
- Tag INDLELA when a trade-policy risk should be showing up in realized export/import flows but isn't (or is)
- Tag SIBAYA when a bill or ruling has a direct fiscal or currency read-through for a SACU economy
- Tag SIZA when trade and aid policy are moving in the same direction — or visibly not
- Tag VUKA when a trade action is severe enough to plausibly become a regional political story

Style: Always name the specific instrument (bill number, USTR determination,
Federal Register docket) and the specific deadline or vote date if known.
State plainly which countries/sectors are exposed — don't hedge into
vagueness. Note when a "technical" trade action has an outsized real-economy
effect on a small, AGOA-dependent economy. If the item you were given isn't
actually about AGOA, SACU, or African trade specifically — even if it
technically matched a search term — say so plainly rather than inventing a
connection. A CBP notice about an unrelated country's cultural artifacts is
not an AGOA signal just because both mention customs.
Tags: #AGOA #trade #tariffs #SACU #eswatini #textiles
"""

    AGOA_KEYWORDS = [
        'African Growth and Opportunity Act', 'AGOA',
        'sub-Saharan Africa trade preference', 'Southern African Customs Union',
        'AGOA eligibility', 'AGOA textile',
    ]
    # Federal Register's full-text search can surface documents that merely
    # mention a search word in passing (e.g. a generic "textile" notice with
    # zero connection to Africa). Require at least one of these to actually
    # appear before treating a hit as real — cheap, catches most false
    # positives without needing a second API call.
    RELEVANCE_ANCHORS = [
        'agoa', 'africa', 'african', 'sacu', 'eswatini', 'swaziland',
        'lesotho', 'botswana', 'namibia', 'south africa', 'sub-saharan',
    ]

    def fetch_data(self):
        items = []
        items += self._fetch_federal_register()
        if len(items) < 4:
            items += self._fetch_congress_gov()
        return items

    def _is_relevant(self, title, abstract):
        haystack = f"{title} {abstract}".lower()
        return any(anchor in haystack for anchor in self.RELEVANCE_ANCHORS)

    def _fetch_federal_register(self):
        """Federal Register full-text search for AGOA / African trade terms
        — same endpoint REX uses, different query. No API key required."""
        term = random.choice(self.AGOA_KEYWORDS)
        try:
            params = [
                ('conditions[term]', term),
                ('per_page',         '10'),
                ('order',            'newest'),
                ('fields[]',         'document_number'),
                ('fields[]',         'title'),
                ('fields[]',         'publication_date'),
                ('fields[]',         'type'),
                ('fields[]',         'agency_names'),
                ('fields[]',         'abstract'),
                ('fields[]',         'html_url'),
            ]
            resp = requests.get(
                'https://www.federalregister.gov/api/v1/documents.json',
                params=params, timeout=15,
                headers={'User-Agent': 'SignalSociety/1.0 (research@signalsociety.ai)'},
            )
            resp.raise_for_status()
            docs = resp.json().get('results', [])
            relevant = [d for d in docs if self._is_relevant(d.get('title', ''), d.get('abstract') or '')]
            if len(relevant) < len(docs):
                self.log.info(f"Federal Register: dropped {len(docs)-len(relevant)} off-topic hit(s) for search_term={term!r}")
            return [{
                'source': 'Federal Register', 'id': d.get('document_number', ''),
                'title': d.get('title', ''), 'search_term': term,
                'agency': ', '.join(d.get('agency_names', [])),
                'published': d.get('publication_date', ''),
                'abstract': (d.get('abstract') or '')[:250],
                'url': d.get('html_url', ''),
            } for d in relevant[:6] if d.get('title')]
        except Exception as e:
            self.log.error(f"Federal Register AGOA search ({term}): {e}")
            return []

    def _fetch_congress_gov(self):
        """Congress.gov EFTS full-text search for AGOA-related bills — free,
        no API key. Same endpoint REX's Congress fallback uses."""
        term = random.choice(['AGOA', 'African Growth and Opportunity Act'])
        try:
            resp = requests.get(
                'https://efts.congress.gov/LATEST/search.json',
                params={'q': term, 'dateIsW': 'true'},
                headers={'User-Agent': 'SignalSociety/1.0 (research)'},
                timeout=12,
            )
            if not resp.ok:
                return []
            results = resp.json().get('results', [])[:8]
            return [{
                'source':      'Congress.gov',
                'id':          r.get('packageId') or r.get('legisNum') or r.get('title', '')[:30],
                'title':       r.get('title', ''),
                'agency':      f"Congress #{r.get('congress', '')}",
                'modified':    r.get('dateIssued', ''),
                'highlights':  (r.get('snippet') or '')[:200],
                'search_term': term,
            } for r in results if r.get('title')]
        except Exception as e:
            self.log.error(f"Congress.gov AGOA search ({term}): {e}")
            return []
