"""
PROJECT HOPE v3.0 - IV Rank Calculator
Calculates per-symbol IV Rank and IV Percentile
IV Rank = (Current IV - 52wk Low IV) / (52wk High IV - 52wk Low IV)
"""
import threading, time
from datetime import datetime
import config

class IVRankCalculator:
    def __init__(self, api):
        self.api = api
        self.iv_data = {}  # symbol -> {current_iv, high_iv, low_iv, rank, percentile}
        self._lock = threading.Lock()
        self.last_refresh = None

    def start_refresh_loop(self):
        threading.Thread(target=self._refresh_loop, daemon=True).start()

    def _refresh_loop(self):
        while True:
            try:
                self.refresh_all()
            except Exception as e:
                print(f"[IV RANK ERR] {e}")
            time.sleep(900)  # Every 15 min

    def refresh_all(self):
        """Calculate IV rank for all watchlist symbols"""
        import random
        symbols = list(config.WATCHLIST)
        random.shuffle(symbols)  # Vary order each cycle
        
        updated = 0
        for symbol in symbols:
            try:
                result = self.calculate_iv_rank(symbol)
                if result:
                    with self._lock:
                        self.iv_data[symbol] = result
                    updated += 1
                time.sleep(0.3)  # Rate limit
            except: continue
        
        self.last_refresh = datetime.now().isoformat()
        print(f"[IV RANK] Updated {updated}/{len(symbols)} symbols")

    def calculate_iv_rank(self, symbol):
        """Calculate IV rank for a single symbol"""
        # Get current ATM IV from nearest monthly expiration
        exps = self.api.get_option_expirations(symbol)
        if not exps: return None
        
        today = datetime.now().date()
        target_exp = None
        for e in exps:
            try:
                ed = datetime.strptime(e, '%Y-%m-%d').date()
                dte = (ed - today).days
                if 20 <= dte <= 45:
                    target_exp = e
                    break
            except: continue
        
        if not target_exp: return None
        
        chain = self.api.get_option_chain(symbol, target_exp)
        if not chain: return None
        
        quote = self.api.get_quote(symbol)
        if not quote: return None
        price = quote.get('last', 0)
        if price <= 0: return None
        
        # Get current ATM IV
        current_iv = self._get_atm_iv(chain, price)
        if not current_iv or current_iv <= 0: return None
        
        # Get historical price data to estimate historical IV range
        history = self.api.get_history(symbol, 365)
        if not history or len(history) < 60: return None
        
        # Estimate IV from historical realized volatility windows
        ivs = self._estimate_historical_ivs(history)
        if not ivs or len(ivs) < 10: return None
        
        high_iv = max(ivs)
        low_iv = min(ivs)
        
        # IV Rank
        if high_iv - low_iv > 0:
            rank = round(((current_iv - low_iv) / (high_iv - low_iv)) * 100, 1)
        else:
            rank = 50.0
        
        # IV Percentile (% of days current IV was below this level)
        below = sum(1 for iv in ivs if iv < current_iv)
        percentile = round((below / len(ivs)) * 100, 1)
        
        return {
            'symbol': symbol,
            'current_iv': round(current_iv * 100, 1),
            'high_iv': round(high_iv * 100, 1),
            'low_iv': round(low_iv * 100, 1),
            'iv_rank': max(0, min(100, rank)),
            'iv_percentile': max(0, min(100, percentile)),
            'updated': datetime.now().isoformat(),
            'sector': config.SECTOR_MAP.get(symbol, 'Other'),
        }

    def _get_atm_iv(self, chain, price):
        """Get ATM implied volatility"""
        best = None
        best_diff = float('inf')
        for opt in chain:
            if opt.get('option_type') != 'call': continue
            diff = abs(opt.get('strike', 0) - price)
            if diff < best_diff:
                best_diff = diff
                g = opt.get('greeks', {}) or {}
                iv = g.get('mid_iv', 0) or g.get('smv_vol', 0)
                if iv > 0: best = iv
        return best

    def _estimate_historical_ivs(self, history):
        """Estimate implied volatility from realized vol over rolling 21-day windows"""
        import math
        ivs = []
        closes = [d.get('close', 0) for d in history if d.get('close', 0) > 0]
        if len(closes) < 30: return ivs
        
        for i in range(21, len(closes)):
            window = closes[i-21:i]
            returns = []
            for j in range(1, len(window)):
                if window[j-1] > 0:
                    returns.append(math.log(window[j] / window[j-1]))
            if len(returns) < 10: continue
            avg = sum(returns) / len(returns)
            variance = sum((r - avg)**2 for r in returns) / (len(returns) - 1)
            realized_vol = math.sqrt(variance * 252)
            # IV typically trades at ~1.1-1.3x realized vol
            ivs.append(realized_vol * 1.15)
        
        return ivs

    def get_iv_rank(self, symbol):
        """Get IV rank for a specific symbol"""
        with self._lock:
            return self.iv_data.get(symbol)

    def is_iv_favorable(self, symbol, trade_type='spread'):
        """Check if IV rank is favorable for the trade type"""
        data = self.get_iv_rank(symbol)
        if not data: return True, "No IV data"  # Don't block if no data
        
        rank = data['iv_rank']
        if trade_type == 'spread':
            # Spreads: want high IV (rich premiums)
            if rank < config.GREEKS_IV_RANK_MIN:
                return False, f"{symbol} IV Rank {rank}% too low for spreads"
            return True, f"IV Rank {rank}% - good for spreads"
        else:
            # Directional: want moderate IV
            if rank > config.GREEKS_IV_RANK_MAX:
                return False, f"{symbol} IV Rank {rank}% too high for directional"
            return True, f"IV Rank {rank}%"

    def get_top_iv_symbols(self, n=20):
        """Get symbols with highest IV rank (best for credit spreads)"""
        with self._lock:
            ranked = sorted(self.iv_data.values(), key=lambda x: x['iv_rank'], reverse=True)
        return ranked[:n]

    def get_data(self):
        """Get all IV rank data for dashboard"""
        with self._lock:
            all_data = list(self.iv_data.values())
        all_data.sort(key=lambda x: x['iv_rank'], reverse=True)
        return {
            'symbols': all_data[:50],
            'total_calculated': len(all_data),
            'last_refresh': self.last_refresh,
            'avg_iv_rank': round(sum(d['iv_rank'] for d in all_data) / len(all_data), 1) if all_data else 0,
            'high_iv_count': len([d for d in all_data if d['iv_rank'] > 50]),
        }
