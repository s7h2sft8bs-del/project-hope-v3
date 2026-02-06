"""
PROJECT HOPE v3.0 - Directional Scanner
"""
from datetime import datetime
import config

class DirectionalScanner:
    def __init__(self, api, state):
        self.api = api
        self.state = state

    def scan(self):
        opportunities = []
        batch = self.api.get_quotes_batch(config.WATCHLIST)
        for symbol in config.WATCHLIST:
            try:
                q = batch.get(symbol)
                if not q: continue
                price = q.get('last', 0)
                change = q.get('change_percentage', 0)
                vol = q.get('volume', 0)
                avg_vol = q.get('average_volume', 1)
                high = q.get('high', 0)
                low = q.get('low', 0)
                prev = q.get('prevclose', 0)
                if price <= 0 or prev <= 0: continue
                vol_ratio = vol / avg_vol if avg_vol > 0 else 0
                if vol_ratio < 1.2: continue
                rng = ((high - low) / prev * 100) if prev > 0 else 0
                setup = self._eval(symbol, price, change, vol_ratio, high, low, prev, rng)
                if setup:
                    opt = self._find_option(symbol, price, setup['direction'])
                    if opt:
                        setup.update(opt)
                        opportunities.append(setup)
            except: continue
        opportunities.sort(key=lambda x: x.get('score', 0), reverse=True)
        return opportunities[:10]

    def _eval(self, sym, price, chg, vr, hi, lo, prev, rng):
        score = 0; st = None; d = None
        if rng > 1.5 and vr > 1.5:
            if chg > 1.0: st, d, score = 'ORB', 'call', 70 + min(vr*5,20) + min(abs(chg)*2,10)
            elif chg < -1.0: st, d, score = 'ORB', 'put', 70 + min(vr*5,20) + min(abs(chg)*2,10)
        elif 0.3 < abs(chg) < 1.5 and vr > 1.3:
            mid = (hi + lo) / 2
            if price > mid and chg > 0: st, d, score = 'VWAP', 'call', 65 + min(vr*5,15)
            elif price < mid and chg < 0: st, d, score = 'VWAP', 'put', 65 + min(vr*5,15)
        elif abs(chg) > 2.0 and vr > 2.0:
            if chg > 2.0: st, d, score = 'PBC', 'call', 75 + min(vr*3,15) + min(abs(chg),10)
            elif chg < -2.0: st, d, score = 'PBC', 'put', 75 + min(vr*3,15) + min(abs(chg),10)
        elif vr > 1.5:
            if price >= hi * 0.998 and chg > 0.5: st, d, score = 'B&R', 'call', 68 + min(vr*5,15)
            elif price <= lo * 1.002 and chg < -0.5: st, d, score = 'B&R', 'put', 68 + min(vr*5,15)
        if st and score >= 65:
            return {'symbol': sym, 'setup_type': st, 'direction': d, 'score': round(score,1), 'stock_price': price, 'change_pct': chg, 'vol_ratio': round(vr,2)}
        return None

    def _find_option(self, symbol, price, direction):
        exps = self.api.get_option_expirations(symbol)
        today = datetime.now().date()
        target_exp = None
        for e in exps:
            try:
                ed = datetime.strptime(e, '%Y-%m-%d').date()
                dte = (ed - today).days
                if 5 <= dte <= 14: target_exp = e; break
            except: continue
        if not target_exp: return None
        chain = self.api.get_option_chain(symbol, target_exp)
        if not chain: return None
        otype = 'call' if direction == 'call' else 'put'
        opts = [o for o in chain if o.get('option_type') == otype]
        best = None; best_diff = float('inf')
        target = price * (1.01 if direction == 'call' else 0.99)
        for o in opts:
            ask = o.get('ask', 0)
            if ask <= 0 or ask > 5.00 or o.get('open_interest', 0) < 50: continue
            diff = abs(o.get('strike', 0) - target)
            if diff < best_diff: best_diff = diff; best = o
        if best:
            ask = best.get('ask', 0)
            max_spend = config.VIRTUAL_ACCOUNT_SIZE * config.DIRECTIONAL_ALLOCATION / config.DIR_MAX_OPEN
            qty = min(int(max_spend / (ask * 100)), config.DIR_MAX_CONTRACTS)
            if qty < 1: qty = 1
            return {'option_symbol': best.get('symbol'), 'strike': best.get('strike'), 'expiration': target_exp,
                    'ask': ask, 'contracts': qty, 'option_type': otype, 'greeks': best.get('greeks', {})}
        return None

    def execute_trade(self, opp):
        result = self.api.buy_option(opp['symbol'], opp['option_symbol'], opp['contracts'], opp['ask'])
        if result and 'order' in result:
            rec = {'order_id': result['order'].get('id','unknown'), 'type': 'directional', 'symbol': opp['symbol'],
                   'option_symbol': opp['option_symbol'], 'option_type': opp['option_type'], 'direction': opp['direction'],
                   'setup_type': opp['setup_type'], 'strike': opp['strike'], 'expiration': opp['expiration'],
                   'entry_price': opp['ask'], 'contracts': opp['contracts'], 'score': opp['score'],
                   'opened_at': datetime.now().isoformat(), 'status': 'pending', 'tier_hit': 0,
                   'original_qty': opp['contracts'], 'current_qty': opp['contracts'], 'manual_override': False}
            self.state['directional_trades'].append(rec)
            self.state['dir_trades_today'] += 1
            return rec
        return None
