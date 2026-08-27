"""
agents/imvula.py — IMVULA, The Rain
Territory: climate and agriculture signals for Eswatini — rainfall,
temperature, and crop/land indicators. Sugar is Eswatini's largest export
and rainfall is its leading indicator. Named for the Nguni word for rain.
"""
import requests, random
from agents.base import BaseAgent

class ImvulaAgent(BaseAgent):
    name      = 'IMVULA'
    title     = 'The Rain'
    color     = '#4472C4'
    glyph     = '☂'
    territory = 'Rainfall · Temperature · Agricultural Output (NASA POWER, World Bank)'
    tagline   = 'The harvest is a press release the sky wrote three months early.'

    personality = """
You are IMVULA, The Rain of The Signal Society.

Voice: Patient, physical, indifferent to press cycles. Named for rain
itself — you report what the sky and the soil are actually doing, which
moves on its own schedule regardless of what anyone announces.

System awareness: You are one of the Society's regional specialists,
sibling to IMPI, SIBAYA, VUKA, INDLELA, and SIZA. You are the earliest
possible warning in the chain that runs from rainfall to harvest to
export volume to current account — the other regional agents pick up
that chain further downstream.

Purpose: Sugar is Eswatini's largest export earner, and Eswatini also
hosts one of the largest Coca-Cola concentrate operations in Africa —
both are, at root, agricultural stories. A rainfall deficit today is a
sugar export shortfall in a season and a current-account story after
that. You track satellite-era rainfall and temperature data alongside
World Bank agricultural land and yield indicators.

Cross-reference rules:
- Tag INDLELA when a rainfall/yield signal should plausibly show up in export volumes on a lag
- Tag SIBAYA when an agricultural shortfall has an obvious current-account or fiscal implication
- Tag VUKA when a climate signal is severe enough to plausibly become a public/political story
- Tag SIZA when a drought signal rises to the level of a food-security concern

Style: Always give the specific metric (rainfall in mm, temperature
anomaly, indicator value) and the comparison period — a number alone
means nothing without knowing what's normal for that period. State
plainly that satellite/model data lags and is an estimate, not a rain
gauge reading. Never claim certainty about a coming harvest; report the
input data and let the implication stand on its own.
Tags: #eswatini #agriculture #climate #sugar
"""

    # Approximate geographic centre of Eswatini.
    LAT, LON = -26.5, 31.5

    def fetch_data(self):
        items = []
        items += self._fetch_nasa_power()
        if len(items) < 2:
            items += self._fetch_worldbank_agriculture()
        return items

    def _fetch_nasa_power(self):
        """NASA POWER daily API — free, no key. Pulls the last ~35 days of
        precipitation and temperature for Eswatini's rough centroid."""
        from datetime import datetime, timedelta
        end   = datetime.utcnow() - timedelta(days=3)   # POWER lags a few days
        start = end - timedelta(days=35)
        try:
            resp = requests.get(
                'https://power.larc.nasa.gov/api/temporal/daily/point',
                params={
                    'parameters': 'PRECTOTCORR,T2M',
                    'community':  'AG',
                    'longitude':  self.LON,
                    'latitude':   self.LAT,
                    'start':      start.strftime('%Y%m%d'),
                    'end':        end.strftime('%Y%m%d'),
                    'format':     'JSON',
                },
                timeout=20,
            )
            resp.raise_for_status()
            params = resp.json().get('properties', {}).get('parameter', {})
            precip = params.get('PRECTOTCORR', {})
            temp   = params.get('T2M', {})
            if not precip:
                return []
            days = sorted(precip.keys())
            total_precip = sum(v for v in precip.values() if isinstance(v, (int, float)) and v >= 0)
            avg_temp = (sum(temp.values()) / len(temp)) if temp else None
            return [{
                'source':          'NASA POWER',
                'id':              f"power-{days[0]}-{days[-1]}",
                'period_start':    days[0],
                'period_end':      days[-1],
                'total_precip_mm': round(total_precip, 1),
                'avg_temp_c':      round(avg_temp, 1) if avg_temp is not None else None,
                'location':        'Eswatini (country centroid, ~27km grid)',
            }]
        except Exception as e:
            self.log.error(f"NASA POWER fetch: {e}")
            return []

    def _fetch_worldbank_agriculture(self):
        """World Bank Open Data — agricultural land / cereal yield indicators
        for Eswatini. Same confirmed free, no-key endpoint SIBAYA uses."""
        indicators = {
            'AG.YLD.CREL.KG': 'Cereal yield (kg per hectare)',
            'AG.LND.AGRI.ZS': 'Agricultural land (% of land area)',
        }
        code = random.choice(list(indicators.keys()))
        try:
            resp = requests.get(
                f'https://api.worldbank.org/v2/country/SWZ/indicator/{code}',
                params={'format': 'json', 'mrnev': '1', 'per_page': '2'},
                timeout=15,
                headers={'User-Agent': 'SignalSociety/1.0 (research@signalsociety.ai)'},
            )
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
                return []
            records = [r for r in payload[1] if r.get('value') is not None]
            return [{
                'source':    'World Bank Open Data',
                'id':        f"SWZ-{code}-{r.get('date')}",
                'indicator': indicators.get(code, code),
                'value':     r.get('value'),
                'year':      r.get('date'),
            } for r in records[:2]]
        except Exception as e:
            self.log.error(f"World Bank agriculture fetch ({code}): {e}")
            return []
