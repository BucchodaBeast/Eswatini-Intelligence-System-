"""
agents/sibaya.py — SIBAYA, The Reserve Watcher
Territory: Southern African macro-fiscal data — GDP, inflation, reserves,
debt, current account. Named for the traditional cattle-kraal: the place
where a household's wealth was actually counted and kept.
"""
import requests, random
from agents.base import BaseAgent

class SibayaAgent(BaseAgent):
    name      = 'SIBAYA'
    title     = 'The Reserve Watcher'
    color     = '#8B5A2B'
    glyph     = '◈'
    territory = 'GDP · Inflation · Reserves · Debt · Current Account (Eswatini & SACU)'
    tagline   = 'Count what is actually in the kraal, not what is claimed to be.'

    personality = """
You are SIBAYA, The Reserve Watcher of The Signal Society.

Voice: Plain-spoken, numerate, unimpressed by rhetoric. Named for the
cattle-kraal — the place in the homestead where wealth was actually kept
and counted, as opposed to talked about. You report what the official
statistics say, in the order they were revised, and flag when a number
moves further or faster than the press release admits.

System awareness: You are one of the Society's regional specialists,
sibling to IMPI, VUKA, INDLELA, SIZA, and IMVULA. Where they watch policy,
narrative, flows, aid, and climate, you watch the ledger — GDP, inflation,
reserves, debt, and the current account, for Eswatini and the wider
Southern African Customs Union (SACU) bloc its currency is pegged to.

Purpose: Eswatini's Lilangeni is pegged to the South African Rand, so
nearly every macro number you track is really a story about two economies
at once. A reserves drawdown, a debt-to-GDP print, a current-account swing
— these are the numbers that precede a peg coming under pressure, a credit
downgrade, or a budget crisis, months before anyone is talking about it.

Cross-reference rules:
- Tag INDLELA when a reserves/current-account move should line up with a trade-flow shift
- Tag IMPI when a fiscal or trade-balance number connects to an AGOA or SACU trade decision
- Tag VUKA when the official numbers and the on-the-ground narrative diverge
- Tag SIZA when a fiscal shortfall lines up with an aid or donor-financing change

Style: Always cite the exact indicator, the value, and the date/year of the
observation — World Bank data lags real time, so state the lag plainly
rather than implying it's current. Compare against the prior available
reading when you have it. Never editorialise about domestic politics —
stick to the numbers and what they imply for capital and trade.
Tags: #eswatini #macro #SACU #currency #reserves #debt
"""

    # World Bank indicator codes — stable, free, no API key required.
    INDICATORS = {
        'NY.GDP.MKTP.KD.ZG': 'GDP growth (annual %)',
        'FP.CPI.TOTL.ZG':    'Inflation, consumer prices (annual %)',
        'GC.DOD.TOTL.GD.ZS': 'Central government debt (% of GDP)',
        'BN.CAB.XOKA.GD.ZS': 'Current account balance (% of GDP)',
        'FI.RES.TOTL.CD':    'Total reserves, incl. gold (current US$)',
        'SL.UEM.TOTL.ZS':    'Unemployment (% of total labor force)',
    }
    # Eswatini, South Africa, Lesotho, Mozambique — the SACU/CMA neighbourhood
    COUNTRIES = ['SWZ', 'ZAF', 'LSO', 'MOZ']

    def fetch_data(self):
        items = []
        # ZAR/USD daily — the Lilangeni is pegged 1:1 to the Rand, so this
        # series doubles as an Eswatini currency read. Checked every run
        # since it's the only fast-moving series in this agent's territory.
        items += self._fetch_fred_zar()
        items += self._fetch_indicators()
        return items

    def _fetch_fred_zar(self):
        """FRED's keyless CSV endpoint — same pattern FLUX already uses for
        Treasury/Fed series, just pointed at the ZAR/USD exchange rate
        (DEXSFUS). No API key required."""
        try:
            resp = requests.get(
                'https://fred.stlouisfed.org/graph/fredgraph.csv',
                params={'id': 'DEXSFUS'},
                timeout=12,
                headers={'User-Agent': 'SignalSociety/1.0 (research@signalsociety.ai)'},
            )
            if not resp.ok:
                return []
            lines = [l for l in resp.text.strip().split('\n') if l and ',' in l]
            if len(lines) < 3:
                return []
            def parse(line):
                d, v = line.split(',')
                try:
                    return d, float(v)
                except ValueError:
                    return d, None
            ld, lv = parse(lines[-1])
            pd_, pv = parse(lines[-2])
            if lv is None:
                return []
            change = round(((lv - pv) / pv) * 100, 2) if pv else None
            return [{
                'source':      'FRED',
                'id':          f'DEXSFUS-{ld}',
                'series':      'ZAR/USD exchange rate (South African Rand — Eswatini Lilangeni is pegged 1:1)',
                'latest_date': ld, 'latest_value': lv,
                'prior_date':  pd_, 'prior_value': pv,
                'pct_change':  change,
            }]
        except Exception as e:
            self.log.error(f"FRED ZAR fetch: {e}")
            return []

    def _fetch_indicators(self):
        items = []
        codes = random.sample(list(self.INDICATORS.keys()), k=3)
        for code in codes:
            items += self._fetch_indicator(code)
        return items

    def _fetch_indicator(self, code):
        """World Bank Open Data API — free, no key, extremely stable schema."""
        country = random.choice(self.COUNTRIES)
        try:
            resp = requests.get(
                f'https://api.worldbank.org/v2/country/{country}/indicator/{code}',
                params={'format': 'json', 'mrnev': '1', 'per_page': '3'},
                timeout=15,
                headers={'User-Agent': 'SignalSociety/1.0 (research@signalsociety.ai)'},
            )
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
                return []
            records = [r for r in payload[1] if r.get('value') is not None]
            return [{
                'source':         'World Bank Open Data',
                'id':             f"{country}-{code}-{r.get('date')}",
                'country':        r.get('country', {}).get('value', country),
                'indicator':      self.INDICATORS.get(code, code),
                'indicator_code': code,
                'value':          r.get('value'),
                'year':           r.get('date'),
                'unit':           r.get('unit', ''),
            } for r in records[:2]]
        except Exception as e:
            self.log.error(f"World Bank fetch ({country}/{code}): {e}")
            return []
