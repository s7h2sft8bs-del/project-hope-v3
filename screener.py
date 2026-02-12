"""PROJECT HOPE v3.0 - Options Screener - Scans 100+ symbols"""
from datetime import datetime
import config
from probability import calculate_spread_metrics

class OptionsScreener:
    def __init__(self, api):
        self.api = api
        self.last_scan_results = {'spreads':[],'scan_time':None}

    def full_scan(self, symbols=None):
        if symbols is None: symbols = config.WATCHLIST
        spread_opps = []; scanned = 0; errors = 0
        for symbol in symbols:
            try:
                quote = self.api.get_quote(symbol)
                if not quote: continue
                price = quote.get('last', 0); change = quote.get('change_percentage', 0)
                volume = quote.get('volume', 0); avg_vol = quote.get('average_volume', 1)
                if price <= 0: continue
                vol_ratio = volume / avg_vol if avg_vol > 0 else 0; scanned += 1

                sp = self._scan_spread(symbol, price, quote)
                if sp: spread_opps.append(sp)

                if vol_ratio > 1.2 and abs(change) > 0.5:
                    d = self._scan_dir(symbol, price, change, vol_ratio, quote)
            except: errors += 1; continue

        spread_opps.sort(key=lambda x: x.get('score',0), reverse=True)
        self.last_scan_results = {
            'spreads': spread_opps[:20],
            'scan_time': datetime.now().isoformat(), 'symbols_scanned': scanned,
            'errors': errors, 'total_spread_opps': len(spread_opps), 
        }
        return self.last_scan_results

    def _scan_spread(self, symbol, price, quote):
        exp_date, dte = self.api.find_expiration_in_range(symbol, config.CS_MIN_DTE, config.CS_MAX_DTE)
        if not exp_date: return None
        chain = self.api.get_option_chain(symbol, exp_date)
        if not chain: return None
        best = None; best_score = 0

        for otype in ['put', 'call']:
            opts = [o for o in chain if o.get('option_type') == otype]
            for opt in opts:
                strike = opt.get('strike', 0)
                greeks = opt.get('greeks', {}) or {}
                delta = abs(greeks.get('delta', 1)); bid = opt.get('bid', 0)
                iv = greeks.get('mid_iv', 0); oi = opt.get('open_interest', 0)
                vol = opt.get('volume', 0)
                if not (0.10 <= delta <= config.CS_TARGET_DELTA): continue
                if oi < 50 or vol < 5: continue

                if otype == 'put':
                    long_strike = strike - config.CS_SPREAD_WIDTH
                else:
                    long_strike = strike + config.CS_SPREAD_WIDTH
                long_opt = None
                for o2 in opts:
                    if abs(o2.get('strike',0) - long_strike) < 0.50: long_opt = o2; break
                if not long_opt: continue

                credit = round(bid - long_opt.get('ask', 0), 2)
                if not (config.CS_MIN_CREDIT <= credit <= config.CS_MAX_CREDIT): continue

                metrics = calculate_spread_metrics(price, strike, long_strike, credit, dte, iv*100 if iv<1 else iv)
                score = min(metrics['prob_profit'],85)*0.4 + min(metrics['return_on_risk'],40)*0.3
                score += min(metrics['expected_value']/10,20)*0.2 + min(oi/500,10)*0.1

                if score > best_score:
                    best_score = score
                    stype = 'put_credit_spread' if otype == 'put' else 'call_credit_spread'
                    direction = 'bullish' if otype == 'put' else 'bearish'
                    best = {
                        'symbol':symbol,'type':stype,'direction':direction,
                        'expiration':exp_date,'dte':dte,
                        'short_strike':strike,'long_strike':long_strike,
                        'short_symbol':opt.get('symbol'),'long_symbol':long_opt.get('symbol'),
                        'credit':credit,'stock_price':round(price,2),'score':round(score,1),
                        'short_bid':bid,'long_ask':long_opt.get('ask',0),
                        **metrics,'open_interest':oi,'volume':vol,
                        'sector':config.SECTOR_MAP.get(symbol,'other'),
                    }
        return best

    def _scan_dir(self, symbol, price, change, vol_ratio, quote):
        high=quote.get('high',0);low=quote.get('low',0);prev=quote.get('prevclose',price)
        rng=((high-low)/prev*100) if prev>0 else 0
        setup=None;direction=None;score=0
        if rng>1.5 and vol_ratio>1.5 and abs(change)>1.0:
            setup='ORB';direction='call' if change>0 else 'put'
            score=70+min(vol_ratio*5,20)+min(abs(change)*2,10)
        elif abs(change)>2.0 and vol_ratio>2.0:
            setup='PBC';direction='call' if change>0 else 'put'
            score=75+min(vol_ratio*3,15)+min(abs(change),10)
        elif vol_ratio>1.5:
            if price>=high*0.998 and change>0.5:
                setup='B&R';direction='call';score=68+min(vol_ratio*5,15)
            elif high>0 and price<=low*1.002 and change<-0.5:
                setup='B&R';direction='put';score=68+min(vol_ratio*5,15)
        if not setup or score<65: return None
        return {'symbol':symbol,'setup_type':setup,'direction':direction,'score':round(score,1),
                'stock_price':round(price,2),'change_pct':round(change,2),'vol_ratio':round(vol_ratio,2),
                'day_range_pct':round(rng,2),'sector':config.SECTOR_MAP.get(symbol,'other')}
