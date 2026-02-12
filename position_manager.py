"""
PROJECT HOPE v3.0 - Position Manager
Credit Spreads Only - tastytrade Standard
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

                # === TASTYTRADE MANAGEMENT RULES ===
                # 1. Take profit at 50%
                if pct >= config.CS_TAKE_PROFIT_PCT:
                    self._close_spread(s, f"TAKE PROFIT ({pct}%)")
                    continue

                # 2. Stop loss at 200% of credit
                if pct <= -config.CS_STOP_LOSS_PCT:
                    self._close_spread(s, f"STOP LOSS ({pct}%)")
                    continue

                # 3. Emergency close at 7 DTE
                if dte <= config.CS_EMERGENCY_DTE:
                    self._close_spread(s, f"EMERGENCY ({dte}d)")
                    continue

                # 4. At 21 DTE: roll if not at profit, otherwise close
                if dte <= config.CS_CLOSE_DTE:
                    if pct > 0:
                        # Profitable but hasn't hit 50% - close and recycle
                        self._close_spread(s, f"21 DTE CLOSE ({pct}% profit)")
                    else:
                        # Losing at 21 DTE - attempt to roll forward
                        rolled = self._roll_spread(s)
                        if not rolled:
                            self._close_spread(s, f"21 DTE ROLL FAILED ({pct}%)")
                    continue

            except Exception as e: print(f"[PM ERR] {s['symbol']}: {e}")

    def _roll_spread(self, s):
        """Roll a spread forward ~30 days at same strikes or better"""
        try:
            # Close current spread
            self.api.close_credit_spread(
                s['symbol'], s['short_symbol'], s['long_symbol'],
                s['contracts'], s.get('current_debit', s['credit'])
            )
            pnl = s.get('current_profit', 0) * s['contracts'] * 100
            s['status'] = 'rolled'
            s['close_reason'] = '21 DTE ROLL'
            s['closed_at'] = datetime.now().isoformat()
            self._track(pnl, s, 'spread')
            self._log(f"ROLLED {s['symbol']}: closed old leg | ${pnl:.2f}")
            self.alerts.send(f"ROLL: {s['symbol']} closed at 21 DTE — scanner will open new 45 DTE position")
            return True
        except Exception as e:
            print(f"[ROLL ERR] {s['symbol']}: {e}")
            return False

    def _close_spread(self, s, reason):
        self.api.close_credit_spread(s['symbol'], s['short_symbol'], s['long_symbol'], s['contracts'], s.get('current_debit', s['credit']))
        pnl = s.get('current_profit', 0) * s['contracts'] * 100
        s['status'] = 'closed'; s['close_reason'] = reason; s['closed_at'] = datetime.now().isoformat()
        self.alerts.send(f"SPREAD: {s['symbol']} | {reason} | P/L: ${pnl:.2f}")
        self._track(pnl, s, 'spread')
        self._log(f"Spread {s['symbol']}: {reason} | ${pnl:.2f}")

    def _track(self, pnl, trade, ttype):
        if pnl > 0:
            self.state['wins'] += 1; self.state['consecutive_losses'] = 0
        else:
            self.state['losses'] += 1; self.state['consecutive_losses'] += 1
        self.state['total_pnl'] += pnl
        if self.analytics:
            self.analytics.record_trade({'symbol': trade['symbol'], 'type': ttype, 'pnl': pnl, 'direction': trade.get('direction', '')})

    def manual_close_position(self, trade_id, ttype='spread'):
        for s in self.state['credit_spreads']:
            if str(s.get('order_id')) == str(trade_id) and s['status'] == 'open':
                self._close_spread(s, "MANUAL")
                return True
        return False

    def toggle_manual_override(self, trade_id, ttype='spread'):
        for s in self.state['credit_spreads']:
            if str(s.get('order_id')) == str(trade_id):
                s['manual_override'] = not s.get('manual_override', False)
                return s['manual_override']
        return None

    def _log(self, msg):
        self.state['activity_log'].insert(0, {'time': datetime.now().strftime('%H:%M:%S'), 'message': msg, 'type': 'position'})
        if len(self.state['activity_log']) > 200: self.state['activity_log'] = self.state['activity_log'][:200]
