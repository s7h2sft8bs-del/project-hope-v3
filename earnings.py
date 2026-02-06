"""
PROJECT HOPE v3.0 - Earnings Calendar
Blocks autopilot from entering trades near earnings announcements
Uses Tradier corporate calendar + manual tracking
"""
import threading, time
from datetime import datetime, timedelta
import config

class EarningsCalendar:
    def __init__(self, api, storage=None):
        self.api = api
        self.storage = storage
        self.earnings_data = {}  # symbol -> {'date': '2025-01-30', 'timing': 'AMC/BMO'}
        self.last_refresh = None
        self._lock = threading.Lock()

    def start_refresh_loop(self):
        """Background thread to refresh earnings data periodically"""
        threading.Thread(target=self._refresh_loop, daemon=True).start()

    def _refresh_loop(self):
        """Refresh earnings data every 6 hours"""
        while True:
            try:
                self.refresh_earnings()
            except Exception as e:
                print(f"[EARNINGS ERR] {e}")
            time.sleep(21600)  # 6 hours

    def refresh_earnings(self):
        """Fetch upcoming earnings for all watchlist symbols"""
        today = datetime.now().date()
        end = today + timedelta(days=14)  # Look 2 weeks ahead
        
        # Try Tradier corporate calendar
        try:
            data = self.api._get('/v1/markets/calendar', {
                'month': str(today.month),
                'year': str(today.year)
            })
            if data and 'calendar' in data:
                cal = data['calendar']
                if 'days' in cal and 'day' in cal['days']:
                    days = cal['days']['day']
                    if isinstance(days, dict): days = [days]
                    for day in days:
                        if day.get('status') == 'open':
                            # Check for earnings in premarket/aftermarket fields
                            date_str = day.get('date', '')
                            if date_str:
                                self._parse_calendar_day(date_str, day)
        except Exception as e:
            print(f"[EARNINGS] Calendar API: {e}")

        # Also check individual symbols via options activity (high IV = possible earnings)
        self._detect_earnings_from_iv()
        
        self.last_refresh = datetime.now().isoformat()
        with self._lock:
            count = len([s for s, d in self.earnings_data.items() if d.get('date')])
        print(f"[EARNINGS] Refreshed: {count} upcoming earnings tracked")

    def _parse_calendar_day(self, date_str, day_data):
        """Parse Tradier calendar data for earnings"""
        # Tradier may include earnings info in calendar
        desc = str(day_data.get('description', ''))
        if 'earning' in desc.lower():
            # Extract symbols mentioned
            for sym in config.WATCHLIST:
                if sym in desc:
                    with self._lock:
                        self.earnings_data[sym] = {
                            'date': date_str,
                            'timing': 'unknown',
                            'source': 'calendar'
                        }

    def _detect_earnings_from_iv(self):
        """Detect possible upcoming earnings by checking for abnormal IV"""
        # Check a subset each cycle to avoid rate limits
        import random
        check_symbols = random.sample(config.WATCHLIST, min(30, len(config.WATCHLIST)))
        
        for symbol in check_symbols:
            try:
                # If near-term IV is much higher than later-term, likely earnings coming
                exps = self.api.get_option_expirations(symbol)
                if len(exps) < 2: continue
                
                today = datetime.now().date()
                near_exp = None
                far_exp = None
                
                for e in exps:
                    try:
                        ed = datetime.strptime(e, '%Y-%m-%d').date()
                        dte = (ed - today).days
                        if 3 <= dte <= 14 and not near_exp: near_exp = e
                        elif 28 <= dte <= 45 and not far_exp: far_exp = e
                    except: continue
                
                if not near_exp or not far_exp: continue
                
                near_chain = self.api.get_option_chain(symbol, near_exp)
                far_chain = self.api.get_option_chain(symbol, far_exp)
                
                if not near_chain or not far_chain: continue
                
                # Get ATM IV for both
                quote = self.api.get_quote(symbol)
                if not quote: continue
                price = quote.get('last', 0)
                
                near_iv = self._get_atm_iv(near_chain, price)
                far_iv = self._get_atm_iv(far_chain, price)
                
                if near_iv and far_iv and near_iv > 0 and far_iv > 0:
                    iv_ratio = near_iv / far_iv
                    # If near-term IV is 50%+ higher than far-term, likely earnings
                    if iv_ratio > 1.5:
                        with self._lock:
                            if symbol not in self.earnings_data:
                                self.earnings_data[symbol] = {
                                    'date': near_exp,
                                    'timing': 'detected',
                                    'source': 'iv_skew',
                                    'iv_ratio': round(iv_ratio, 2),
                                    'near_iv': round(near_iv * 100, 1),
                                    'far_iv': round(far_iv * 100, 1),
                                }
                                print(f"[EARNINGS] Detected {symbol}: IV ratio {iv_ratio:.2f}")
                time.sleep(0.5)  # Rate limit
            except: continue

    def _get_atm_iv(self, chain, price):
        """Get implied volatility of the closest ATM option"""
        best = None
        best_diff = float('inf')
        for opt in chain:
            diff = abs(opt.get('strike', 0) - price)
            if diff < best_diff:
                best_diff = diff
                g = opt.get('greeks', {}) or {}
                iv = g.get('mid_iv', 0) or g.get('smv_vol', 0)
                if iv > 0: best = iv
        return best

    def is_earnings_blackout(self, symbol):
        """Check if symbol is in earnings blackout window"""
        with self._lock:
            if symbol not in self.earnings_data:
                return False, ""
            
            earn = self.earnings_data[symbol]
            earn_date_str = earn.get('date', '')
            if not earn_date_str:
                return False, ""
            
            try:
                earn_date = datetime.strptime(earn_date_str, '%Y-%m-%d').date()
                today = datetime.now().date()
                days_until = (earn_date - today).days
                
                if 0 <= days_until <= config.EARNINGS_BLACKOUT_DAYS:
                    return True, f"{symbol} earnings in {days_until}d ({earn_date_str})"
                if days_until < 0 and days_until >= -1:
                    return True, f"{symbol} just reported ({earn_date_str})"
            except:
                pass
        
        return False, ""

    def add_manual_earnings(self, symbol, date_str, timing='unknown'):
        """Manually add earnings date"""
        with self._lock:
            self.earnings_data[symbol] = {
                'date': date_str,
                'timing': timing,
                'source': 'manual'
            }
        if self.storage:
            earnings_all = self.storage._read(self.storage.STORAGE_DIR + '/earnings.json') or {}
            earnings_all[symbol] = {'date': date_str, 'timing': timing}
            self.storage._write(self.storage.STORAGE_DIR + '/earnings.json', earnings_all)

    def get_upcoming(self, days_ahead=14):
        """Get all upcoming earnings within N days"""
        today = datetime.now().date()
        upcoming = []
        with self._lock:
            for symbol, data in self.earnings_data.items():
                try:
                    ed = datetime.strptime(data['date'], '%Y-%m-%d').date()
                    days_until = (ed - today).days
                    if 0 <= days_until <= days_ahead:
                        upcoming.append({
                            'symbol': symbol,
                            'date': data['date'],
                            'days_until': days_until,
                            'timing': data.get('timing', 'unknown'),
                            'source': data.get('source', 'unknown'),
                            'sector': config.SECTOR_MAP.get(symbol, 'Other'),
                        })
                except: continue
        upcoming.sort(key=lambda x: x['days_until'])
        return upcoming

    def get_data(self):
        """Get all earnings data for dashboard"""
        return {
            'upcoming': self.get_upcoming(14),
            'total_tracked': len(self.earnings_data),
            'last_refresh': self.last_refresh,
            'blackout_symbols': [s for s in config.WATCHLIST if self.is_earnings_blackout(s)[0]],
        }
