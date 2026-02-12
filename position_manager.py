"""
PROJECT HOPE v3.0 - Position Manager
"""
from datetime import datetime
import config, math

class PositionManager:
    def __init__(self, api, state, alerts, analytics=None):
        self.api = api
        self.state = state
        self.alerts = alerts
        self.analytics = analytics

    def check_all_positions(self):
        self._check_credit_spreads()

    def _check_credit_spreads(self):
        for s in self.state['credit_spreads']:
            if s['status'] != 'open' or s.get('manual_override'): continue
            try:
                quotes = self.api.get_quotes([s['short_symbol'], s['long_symbol']])
                if not quotes: continue
                sq = quotes.get(s['short_symbol'], {})
                lq = quotes.get(s['long_symbol'], {})
                debit = round(sq.get('ask', 0) - lq.get('bid', 0), 2)
                if debit < 0: debit = 0.01
                profit = round(s['credit'] - debit, 2)
                pct = round(profit / s['credit'] * 100, 1) if s['credit'] > 0 else 0
                s['current_debit'] = debit; s['current_profit'] = profit; s['profit_pct'] = pct
                try:
                    dte = (datetime.strptime(s['expiration'], '%Y-%m-%d').date() - datetime.now().date()).days
                    s['current_dte'] = dte
                except: dte = 999
                if pct >= config.CS_TAKE_PROFIT_PCT: self._close_spread(s, f"TAKE PROFIT ({pct}%)"); continue
                if pct <= -config.CS_STOP_LOSS_PCT: self._close_spread(s, f"STOP LOSS ({pct}%)"); continue
                if dte <= config.CS_EMERGENCY_DTE: self._close_spread(s, f"EMERGENCY ({dte}d)"); continue
                if dte <= config.CS_CLOSE_DTE: self._close_spread(s, f"DTE CUTOFF ({dte}d)"); continue
            except Exception as e: print(f"[PM ERR] {s['symbol']}: {e}")

    def _close_spread(self, s, reason):
        self.api.close_credit_spread(s['symbol'], s['short_symbol'], s['long_symbol'], s['contracts'], s.get('current_debit', s['credit']))
        pnl = s.get('current_profit', 0) * s['contracts'] * 100
        s['status'] = 'closed'; s['close_reason'] = reason; s['closed_at'] = datetime.now().isoformat()
        self.alerts.send(f"SPREAD: {s['symbol']} | {reason} | P/L: ${pnl:.2f}")
        self._track(pnl, s, 'spread')
        self._log(f"Spread {s['symbol']}: {reason} | ${pnl:.2f}")

    def _close_dir(self, t, qty, reason):
        self.api.sell_option(t['symbol'], t['option_symbol'], qty)
        t['current_qty'] = 0; t['status'] = 'closed'; t['close_reason'] = reason; t['closed_at'] = datetime.now().isoformat()
        pnl = t.get('pnl', 0)
        self.alerts.send(f"CLOSED: {t['symbol']} {t['option_type'].upper()} | {reason} | ${pnl:.2f}")
        self._log(f"Dir {t['symbol']}: {reason} | ${pnl:.2f}")

    def _partial(self, t, qty, reason):
        self.api.sell_option(t['symbol'], t['option_symbol'], qty)
        t['current_qty'] -= qty
        if t['current_qty'] <= 0: t['status'] = 'closed'
        self.alerts.send(f"PARTIAL: {t['symbol']} sold {qty}/{t['original_qty']} | {reason}")
        self._log(f"Partial {t['symbol']}: {reason}")

    def _track(self, pnl, trade, ttype):
        if pnl > 0:
            self.state['wins'] += 1; self.state['consecutive_losses'] = 0
        else:
            self.state['losses'] += 1; self.state['consecutive_losses'] += 1
        self.state['total_pnl'] += pnl
        if self.analytics:
            self.analytics.record_trade({'symbol': trade['symbol'], 'type': ttype, 'pnl': pnl, 'direction': trade.get('direction', '')})

    def manual_close_position(self, trade_id, ttype):
        for t in trades:
            if t.get('order_id') == trade_id and t['status'] == 'open':
                if ttype == 'spread': self._close_spread(t, "MANUAL")
                else: self._close_dir(t, t['current_qty'], "MANUAL")
                return True
        return False

    def toggle_manual_override(self, trade_id, ttype):
        for t in trades:
            if t.get('order_id') == trade_id:
                t['manual_override'] = not t.get('manual_override', False)
                return t['manual_override']
        return None

    def _log(self, msg):
        self.state['activity_log'].insert(0, {'time': datetime.now().strftime('%H:%M:%S'), 'message': msg, 'type': 'position'})
        if len(self.state['activity_log']) > 200: self.state['activity_log'] = self.state['activity_log'][:200]
