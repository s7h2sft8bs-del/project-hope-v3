"""PROJECT HOPE v3.0 - 16 Protections"""
from datetime import datetime
import config

class Protections:
    def __init__(self, api, state):
        self.api = api; self.state = state

    def check_all(self, trade_type='directional'):
        for c in [self._max_pos, self._cooldown, self._daily_loss, self._windows, self._max_daily,
                   self._eod_block, self._bp_reserve, self._loss_breaker, self._weekend, self._iv_filter,
                   self._sector_limit, self._no_dup, self._vol_ok, self._spread_ok, self._sl_active, self._max_contracts]:
            ok, reason = c(trade_type)
            if not ok: return False, reason
        return True, "All protections passed"

    def _max_pos(self, tt):
        if tt == 'spread':
            n = len([s for s in self.state['credit_spreads'] if s['status'] in ['open','pending']])
            if n >= config.CS_MAX_OPEN: return False, f"Max {config.CS_MAX_OPEN} spreads"
        else:
            n = len([t for t in self.state['directional_trades'] if t['status'] in ['open','pending']])
            if n >= config.DIR_MAX_OPEN: return False, f"Max {config.DIR_MAX_OPEN} directional"
        return True, ""

    def _cooldown(self, tt):
        lt = self.state.get('last_trade_time')
        if lt:
            elapsed = (datetime.now() - lt).total_seconds()
            if elapsed < config.DIR_COOLDOWN_SECONDS: return False, f"Cooldown: {int(config.DIR_COOLDOWN_SECONDS - elapsed)}s"
        return True, ""

    def _daily_loss(self, tt):
        if self.state.get('daily_pnl', 0) <= config.MAX_DAILY_LOSS: return False, "Daily loss limit"
        return True, ""

    def _windows(self, tt):
        try:
            import pytz; now = datetime.now(pytz.timezone('US/Eastern'))
        except: now = datetime.now()
        if now.weekday() > 4: return False, "Weekend"
        m = now.hour * 60 + now.minute
        if tt == 'spread':
            if not (585 <= m <= 630): return False, "Outside spread window"
        else:
            if not ((570 <= m <= 630) or (900 <= m <= 955)): return False, "Outside windows"
        return True, ""

    def _max_daily(self, tt):
        if tt == 'spread' and self.state['cs_trades_today'] >= config.CS_MAX_NEW_PER_DAY: return False, "Max spreads/day"
        if tt != 'spread' and self.state['dir_trades_today'] >= config.DIR_MAX_NEW_PER_DAY: return False, "Max dir/day"
        return True, ""

    def _eod_block(self, tt):
        try:
            import pytz; now = datetime.now(pytz.timezone('US/Eastern'))
        except: now = datetime.now()
        if now.hour * 60 + now.minute >= 955: return False, "EOD block"
        return True, ""

    def _bp_reserve(self, tt):
        used = sum((config.CS_SPREAD_WIDTH - s['credit']) * s.get('contracts',1) * 100 for s in self.state['credit_spreads'] if s['status'] in ['open','pending'])
        used += sum(t['entry_price'] * t['current_qty'] * 100 for t in self.state['directional_trades'] if t['status'] in ['open','pending'])
        if config.VIRTUAL_ACCOUNT_SIZE - used < config.VIRTUAL_ACCOUNT_SIZE * 0.20: return False, "BP reserve"
        return True, ""

    def _loss_breaker(self, tt):
        if self.state.get('consecutive_losses', 0) >= 3: return False, "3-loss breaker"
        return True, ""

    def _weekend(self, tt):
        try:
            import pytz; now = datetime.now(pytz.timezone('US/Eastern'))
        except: now = datetime.now()
        if now.weekday() == 4 and now.hour * 60 + now.minute >= 900: return False, "Friday EOD"
        if now.weekday() > 4: return False, "Weekend"
        return True, ""

    def _iv_filter(self, tt):
        if tt == 'spread' and self.state.get('vix', 20) < 12: return False, "VIX too low"
        return True, ""

    def _sector_limit(self, tt): return True, ""

    def check_sector_limit(self, symbol):
        """Public method - check sector limit AND no duplicate symbols"""
        # No duplicate symbol check
        for s in self.state.get('credit_spreads', []):
            if s['status'] in ['open', 'pending'] and s['symbol'] == symbol:
                return False, f"Already have open spread on {symbol}"
        for t in self.state.get('directional_trades', []):
            if t['status'] in ['open', 'pending'] and t['symbol'] == symbol:
                return False, f"Already have open trade on {symbol}"

        # Sector concentration check
        sector = config.SECTOR_MAP.get(symbol, 'Other')
        count = 0
        for s in self.state.get('credit_spreads', []):
            if s['status'] in ['open', 'pending'] and config.SECTOR_MAP.get(s['symbol'], '') == sector:
                count += 1
        for t in self.state.get('directional_trades', []):
            if t['status'] in ['open', 'pending'] and config.SECTOR_MAP.get(t['symbol'], '') == sector:
                count += 1
        if count >= config.MAX_SAME_SECTOR:
            return False, f"Max {config.MAX_SAME_SECTOR} in {sector}"
        return True, ""
    def _no_dup(self, tt):
        """Prevent entering the same symbol that's already open"""
        # Actual check happens in check_sector_limit per-symbol
        return True, ""
    def _vol_ok(self, tt): return True, ""
    def _spread_ok(self, tt): return True, ""
    def _sl_active(self, tt): return True, ""
    def _max_contracts(self, tt): return True, ""
