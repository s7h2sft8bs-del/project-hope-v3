"""
PROJECT HOPE v3.0 - Backtesting Engine
Tests credit spread strategies against historical price data
Uses FREE Tradier historical data - no proprietary tools needed
"""
import math
from datetime import datetime, timedelta
import config

class Backtester:
    def __init__(self, api):
        self.api = api

    def run_credit_spread_backtest(self, symbol='SPY', days=365):
        """Simulate credit spread strategy on historical data"""
        history = self.api.get_history(symbol, days)
        if not history or len(history) < 30:
            return {'error': f'Insufficient data for {symbol}', 'symbol': symbol}

        trades = []
        balance = config.BACKTEST_INITIAL_BALANCE
        wins = losses = 0
        peak = balance
        max_dd = 0
        daily_returns = []

        i = 0
        while i < len(history) - 25:
            entry = history[i]
            price = entry.get('close', 0)
            if price <= 0:
                i += 1
                continue

            # Enter a put credit spread once per week
            short_strike = round(price * 0.95, 2)
            long_strike = short_strike - config.CS_SPREAD_WIDTH
            credit = round(config.CS_SPREAD_WIDTH * 0.22, 2)
            max_loss = config.CS_SPREAD_WIDTH - credit

            # Check price over next 21 trading days
            exit_idx = min(i + 21, len(history) - 1)
            min_price = price
            for j in range(i, exit_idx + 1):
                low = history[j].get('low', price)
                if low < min_price:
                    min_price = low

            # Determine result
            if min_price > short_strike:
                pnl = round(credit * 0.50 * 100, 2)
                wins += 1
                result = 'WIN'
            elif min_price <= long_strike:
                pnl = round(-max_loss * 100, 2)
                losses += 1
                result = 'MAX_LOSS'
            else:
                intrusion = (short_strike - min_price) / config.CS_SPREAD_WIDTH
                pnl = round(-(intrusion * max_loss) * 100, 2)
                losses += 1
                result = 'STOP_LOSS'

            balance += pnl
            daily_returns.append(pnl / max(balance, 1))
            if balance > peak: peak = balance
            dd = ((peak - balance) / peak * 100) if peak > 0 else 0
            if dd > max_dd: max_dd = dd

            trades.append({
                'date': entry.get('date', ''), 'symbol': symbol,
                'entry': price, 'short': short_strike, 'long': long_strike,
                'credit': credit, 'min_price': round(min_price, 2),
                'pnl': pnl, 'result': result, 'balance': round(balance, 2)
            })
            i += 5

        return self._compile_results(symbol, days, trades, wins, losses, balance, max_dd, daily_returns)

    def run_full_backtest(self, symbols=None, days=365):
        """Run backtest across top symbols for both strategies"""
        if not symbols:
            symbols = ['SPY','QQQ','AAPL','MSFT','AMZN','NVDA','AMD','TSLA','META','GOOGL','NFLX','BA','JPM','XOM','GS']

        cs_results = {}
        for sym in symbols:
            try:
                cs = self.run_credit_spread_backtest(sym, days)
                if 'error' not in cs: cs_results[sym] = cs
            except Exception as e:
                print(f"[BT ERR] {sym}: {e}")

        return {
            'credit_spreads': self._aggregate(cs_results),
            'symbols_tested': len(symbols),
            'per_symbol_cs': {k: {'win_rate': v['win_rate'], 'return': v['total_return'], 'sharpe': v['sharpe'], 'max_dd': v['max_dd']} for k, v in cs_results.items()},
        }

    def _compile_results(self, symbol, days, trades, wins, losses, balance, max_dd, daily_returns):
        total = wins + losses
        win_rate = round(wins / total * 100, 1) if total > 0 else 0
        total_pnl = round(balance - config.BACKTEST_INITIAL_BALANCE, 2)
        total_return = round(total_pnl / config.BACKTEST_INITIAL_BALANCE * 100, 1)

        # Sharpe
        if daily_returns and len(daily_returns) > 1:
            avg = sum(daily_returns) / len(daily_returns)
            std = math.sqrt(sum((r - avg)**2 for r in daily_returns) / (len(daily_returns) - 1))
            sharpe = round((avg * 252 - 0.05) / (std * math.sqrt(252)), 2) if std > 0 else 0
        else:
            sharpe = 0

        # Profit factor
        gw = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gl = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        pf = round(gw / gl, 2) if gl > 0 else 99

        # Streaks
        max_ws = max_ls = cs = 0
        last = None
        for t in trades:
            if t['pnl'] > 0:
                cs = cs + 1 if last == 'w' else 1
                last = 'w'
                max_ws = max(max_ws, cs)
            else:
                cs = cs + 1 if last == 'l' else 1
                last = 'l'
                max_ls = max(max_ls, cs)

        # Monthly
        monthly = {}
        for t in trades:
            m = t['date'][:7] if t.get('date') else 'unknown'
            monthly[m] = monthly.get(m, 0) + t['pnl']

        # Avg win/loss
        w_trades = [t['pnl'] for t in trades if t['pnl'] > 0]
        l_trades = [t['pnl'] for t in trades if t['pnl'] < 0]

        return {
            'symbol': symbol, 'days': days, 'total_trades': total,
            'wins': wins, 'losses': losses, 'win_rate': win_rate,
            'total_pnl': total_pnl, 'total_return': total_return,
            'final_balance': round(balance, 2), 'max_dd': round(max_dd, 1),
            'sharpe': sharpe, 'profit_factor': pf,
            'avg_win': round(sum(w_trades)/len(w_trades), 2) if w_trades else 0,
            'avg_loss': round(sum(l_trades)/len(l_trades), 2) if l_trades else 0,
            'max_win_streak': max_ws, 'max_loss_streak': max_ls,
            'monthly': [{'month': k, 'pnl': round(v, 2)} for k, v in sorted(monthly.items())],
            'equity_curve': [{'date': t['date'], 'bal': t['balance']} for t in trades],
            'trades': trades[-30:]
        }

    def _aggregate(self, results):
        if not results: return {'avg_win_rate': 0, 'avg_return': 0, 'avg_sharpe': 0, 'avg_max_dd': 0}
        n = len(results)
        return {
            'avg_win_rate': round(sum(r['win_rate'] for r in results.values()) / n, 1),
            'avg_return': round(sum(r['total_return'] for r in results.values()) / n, 1),
            'avg_sharpe': round(sum(r['sharpe'] for r in results.values()) / n, 2),
            'avg_max_dd': round(sum(r['max_dd'] for r in results.values()) / n, 1),
            'total_trades': sum(r['total_trades'] for r in results.values()),
            'best': max(results.items(), key=lambda x: x[1]['total_return'])[0],
            'worst': min(results.items(), key=lambda x: x[1]['total_return'])[0],
        }
