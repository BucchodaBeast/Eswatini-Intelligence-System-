"""
agents/indlela.py — INDLELA, The Path
Territory: realized trade flows for Eswatini — what's actually being
exported and imported, not just what policy says should happen. Named for
the Nguni word for "the path" or "the road": the route goods actually take.
"""
import requests, random
from agents.base import BaseAgent

class IndlelaAgent(BaseAgent):
    name      = 'INDLELA'
    title     = 'The Path'
    color     = '#1E88A8'
    glyph     = '➤'
    territory = 'Realized Trade Flows · Export/Import Volumes (UN Comtrade)'
    tagline   = "Every path a container travels is a fact the policy debate hasn't caught up to."

    personality = """
You are INDLELA, The Path of The Signal Society.

Voice: Literal, unsentimental, allergic to forecasts. You don't predict
trade — you report what already moved. Named for the road a shipment
actually travels, as distinct from the road policy says it should travel.

System awareness: You are one of the Society's regional specialists,
sibling to IMPI, SIBAYA, VUKA, SIZA, and IMVULA. Where IMPI watches trade
POLICY (what Washington is deciding), you watch trade REALITY — the goods
that already crossed a border, recorded in official customs statistics.
When your numbers and IMPI's policy narrative disagree, that gap is
usually the most interesting thing either of you has found.

Purpose: Realized export/import data — value, volume, partner country,
product category — is the ground truth that policy debates, currency
moves, and fiscal forecasts all eventually have to answer to. A decline in
apparel exports shows up in your data months before it shows up in an
unemployment statistic. A shift in sugar export volume shows up before it
shows up in the current account.

Cross-reference rules:
- Tag IMPI when realized flows are moving in a direction the policy debate hasn't caught up to
- Tag SIBAYA when a trade balance shift has an obvious current-account or reserves implication
- Tag IMVULA when a shift in agricultural exports (sugar, cotton) might trace back to a harvest
- Tag SIZA when trade data suggests aid-dependency is deepening or easing

Style: Always give the exact commodity, direction (export/import), value or
year-over-year change, and partner country when available. State plainly
when data is lagged — Comtrade reporting is rarely real-time — rather than
implying it's current. Never speculate about cause; that's what the
cross-referenced agent is for.
Tags: #trade #eswatini #SACU #exports #imports
"""

    # Eswatini's UN M49 reporter code.
    REPORTER = '748'
    # HS chapters worth rotating through: TOTAL, sugar, apparel/textiles.
    COMMODITIES = [
        ('TOTAL', 'all commodities'),
        ('17',    'sugar and sugar confectionery'),
        ('61',    'knitted apparel'),
        ('62',    'woven apparel'),
    ]

    def fetch_data(self):
        items = []
        cmd_code, cmd_label = random.choice(self.COMMODITIES)
        flow = random.choice(['X', 'M'])  # X=export, M=import
        items += self._fetch_comtrade(cmd_code, cmd_label, flow)
        return items

    def _fetch_comtrade(self, cmd_code, cmd_label, flow):
        """UN Comtrade free preview endpoint — no API key required, capped
        at 500 records (plenty for a single country/commodity/flow query)."""
        try:
            resp = requests.get(
                'https://comtradeapi.un.org/public/v1/preview/C/A/HS',
                params={
                    'reporterCode': self.REPORTER,
                    'period':       '2024,2023',
                    'partnerCode':  '0',       # 0 = World (all partners)
                    'cmdCode':      cmd_code,
                    'flowCode':     flow,
                    'format':       'JSON',
                },
                timeout=15,
                headers={'User-Agent': 'SignalSociety/1.0 (research@signalsociety.ai)'},
            )
            resp.raise_for_status()
            data = resp.json().get('data', [])
            flow_label = 'exports' if flow == 'X' else 'imports'
            return [{
                'source':       'UN Comtrade',
                'id':           f"{self.REPORTER}-{cmd_code}-{flow}-{d.get('period')}",
                'reporter':     d.get('reporterDesc', 'Eswatini'),
                'partner':      d.get('partnerDesc', 'World'),
                'commodity':    cmd_label,
                'flow':         flow_label,
                'period':       d.get('period'),
                'trade_value_usd': d.get('primaryValue'),
                'net_weight_kg':   d.get('netWgt'),
            } for d in data[:6] if d.get('primaryValue')]
        except Exception as e:
            self.log.error(f"UN Comtrade fetch ({cmd_code}/{flow}): {e}")
            return []
