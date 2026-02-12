"""
PROJECT HOPE v3.0 - Credit Spread Scanner
"""
from datetime import datetime
import config

class CreditSpreadScanner:
    def __init__(self, api, state):
        self.api = api
        self.state = state

    def scan(self):
        opportunities = []
        # Get sectors already in use
        open_sectors = {}
        for s in self.state.get('credit_spreads', []):
            if s['status'] in ['open', 'pending']:
                sec = config.SECTOR_MAP.get(s['symbol'], 'Other')
                open_sectors[sec] = open_sectors.get(sec, 0) + 1

        for symbol in config.WATCHLIST:
            try:
                # Sector correlation check
                sec = config.SECTOR_MAP.get(symbol, 'Other')
                if open_sectors.get(sec, 0) >= config.MAX_SAME_SECTOR:
                    continue

                exp_date, dte = self.api.find_expiration_in_range(symbol, config.CS_MIN_DTE, config.CS_MAX_DTE)
                if not exp_date: continue

                quote = self.api.get_quote(symbol)
                if not quote: continue
                price = quote.get('last', 0)
                if price <= 0: continue

                chain = self.api.get_option_chain(symbol, exp_date)
                if not chain: continue

                put = self._find_put_spread(symbol, chain, price, exp_date, dte)
                if put: opportunities.append(put)

                call = self._find_call_spread(symbol, chain, price, exp_date, dte)
                if call: opportunities.append(call)
            except Exception as e:
                continue

        opportunities.sort(key=lambda x: x['credit'], reverse=True)
        return opportunities

    def _find_put_spread(self, symbol, chain, price, exp, dte):
        puts = sorted([o for o in chain if o.get('option_type') == 'put'], key=lambda x: x.get('strike', 0), reverse=True)
        for short_put in puts:
            strike = short_put.get('strike', 0)
            g = short_put.get('greeks', {})
            delta = abs(g.get('delta', 1))
            bid = short_put.get('bid', 0)
            if delta > config.CS_TARGET_DELTA or delta < 0.10: continue
            long_strike = strike - config.CS_SPREAD_WIDTH
            long_put = next((p for p in puts if abs(p.get('strike', 0) - long_strike) < 0.5), None)
            if not long_put: continue
            credit = round(bid - long_put.get('ask', 0), 2)
            if credit < config.CS_MIN_CREDIT or credit > config.CS_MAX_CREDIT: continue
            if short_put.get('open_interest', 0) < 100: continue
            return {'type': 'put_credit_spread', 'symbol': symbol, 'direction': 'bullish', 'expiration': exp, 'dte': dte,
                    'short_strike': strike, 'long_strike': long_strike, 'short_symbol': short_put.get('symbol'),
                    'long_symbol': long_put.get('symbol'), 'credit': credit, 'max_loss': round(config.CS_SPREAD_WIDTH - credit, 2),
                    'prob_otm': round((1 - delta) * 100, 1), 'delta': delta, 'stock_price': price}
        return None

    def _find_call_spread(self, symbol, chain, price, exp, dte):
        calls = sorted([o for o in chain if o.get('option_type') == 'call'], key=lambda x: x.get('strike', 0))
        for short_call in calls:
            strike = short_call.get('strike', 0)
            g = short_call.get('greeks', {})
            delta = abs(g.get('delta', 1))
            bid = short_call.get('bid', 0)
            if delta > config.CS_TARGET_DELTA or delta < 0.10: continue
            long_strike = strike + config.CS_SPREAD_WIDTH
            long_call = next((c for c in calls if abs(c.get('strike', 0) - long_strike) < 0.5), None)
            if not long_call: continue
            credit = round(bid - long_call.get('ask', 0), 2)
            if credit < config.CS_MIN_CREDIT or credit > config.CS_MAX_CREDIT: continue
            if short_call.get('open_interest', 0) < 100: continue
            return {'type': 'call_credit_spread', 'symbol': symbol, 'direction': 'bearish', 'expiration': exp, 'dte': dte,
                    'short_strike': strike, 'long_strike': long_strike, 'short_symbol': short_call.get('symbol'),
                    'long_symbol': long_call.get('symbol'), 'credit': credit, 'max_loss': round(config.CS_SPREAD_WIDTH - credit, 2),
                    'prob_otm': round((1 - delta) * 100, 1), 'delta': delta, 'stock_price': price}
        return None

    def execute_spread(self, opp):
        result = self.api.place_credit_spread(opp['symbol'], opp['short_symbol'], opp['long_symbol'], config.CS_CONTRACTS, opp['credit'])
        if result and 'order' in result:
            rec = {**opp, 'order_id': result['order'].get('id', 'unknown'), 'contracts': config.CS_CONTRACTS,
                   'opened_at': datetime.now().isoformat(), 'status': 'pending',
                   'take_profit_price': round(opp['credit'] * (config.CS_TAKE_PROFIT_PCT / 100), 2),
                   'stop_loss_price': round(opp['credit'] * (config.CS_STOP_LOSS_PCT / 100), 2), 'manual_override': False}
            self.state['credit_spreads'].append(rec)
            self.state['cs_trades_today'] += 1
            return rec
        return None

def check_trend(api, symbol):
    try:
        h = api.get_history(symbol, days=30)
        if not h or len(h) < 20: return "neutral"
        c = [d.get("close",0) for d in h[-20:]]
        s5 = sum(c[-5:])/5
        s20 = sum(c)/20
        if s5 > s20: return "bullish"
        if s5 < s20: return "bearish"
        return "neutral"
    except: return "neutral"

def check_trend(api, symbol):
    try:
        h = api.get_history(symbol, days=30)
        if not h or len(h) < 20: return "neutral"
        c = [d.get("close",0) for d in h[-20:]]
        s5 = sum(c[-5:])/5
        s20 = sum(c)/20
        if s5 > s20: return "bullish"
        if s5 < s20: return "bearish"
        return "neutral"
    except: return "neutral"
