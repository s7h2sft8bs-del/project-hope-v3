"""PROJECT HOPE v3.0 - Greeks Dashboard - Real-time portfolio Greeks from Tradier"""
from datetime import datetime

class GreeksDashboard:
    def __init__(self, api):
        self.api = api

    def get_portfolio_greeks(self, state):
        total = {'delta':0,'gamma':0,'theta':0,'vega':0,'positions':[]}
        for spread in state.get('credit_spreads', []):
            if spread['status'] != 'open': continue
            try:
                g = self._spread_greeks(spread)
                if g:
                    total['delta']+=g['net_delta'];total['gamma']+=g['net_gamma']
                    total['theta']+=g['net_theta'];total['vega']+=g['net_vega']
                    total['positions'].append(g)
            except: pass
        # Directional trades removed - credit spreads only
            if trade['status'] != 'open': continue
            try:
                g = self._option_greeks(trade)
                if g:
                    total['delta']+=g['delta'];total['gamma']+=g['gamma']
                    total['theta']+=g['theta'];total['vega']+=g['vega']
                    total['positions'].append(g)
            except: pass
        total['delta']=round(total['delta'],2);total['gamma']=round(total['gamma'],4)
        total['theta']=round(total['theta'],2);total['vega']=round(total['vega'],2)
        return total

    def _spread_greeks(self, spread):
        quotes = self.api.get_quotes([spread['short_symbol'], spread['long_symbol']])
        if not quotes: return None
        sq = quotes.get(spread['short_symbol'], {}); lq = quotes.get(spread['long_symbol'], {})
        sg = sq.get('greeks', {}) or {}; lg = lq.get('greeks', {}) or {}
        qty = spread.get('contracts', 1)
        return {
            'symbol': spread['symbol'], 'type': spread['type'],
            'net_delta': round((-sg.get('delta',0)+lg.get('delta',0))*qty*100, 2),
            'net_gamma': round((-sg.get('gamma',0)+lg.get('gamma',0))*qty*100, 4),
            'net_theta': round((-sg.get('theta',0)+lg.get('theta',0))*qty*100, 2),
            'net_vega': round((-sg.get('vega',0)+lg.get('vega',0))*qty*100, 2),
        }

    def _option_greeks(self, trade):
        quote = self.api.get_quote(trade['option_symbol'])
        if not quote: return None
        g = quote.get('greeks', {}) or {}
        qty = trade.get('current_qty', trade.get('contracts', 1))
        return {