"""
PROJECT HOPE v3.0 - Risk Analyzer
Portfolio stress testing, correlation matrix, risk-at-a-glance
"""
import math
from datetime import datetime
import config

class RiskAnalyzer:
    def __init__(self, api):
        self.api = api
        self.correlation_cache = {}
        self.last_stress = None

    def stress_test(self, state, scenarios=None):
        """Run stress test: what happens to portfolio under different market moves"""
        if not scenarios:
            scenarios = [
                {'name': 'SPY -1%', 'move': -1},
                {'name': 'SPY -3%', 'move': -3},
                {'name': 'SPY -5%', 'move': -5},
                {'name': 'SPY -10%', 'move': -10},
                {'name': 'SPY +3%', 'move': 3},
                {'name': 'SPY +5%', 'move': 5},
                {'name': 'VIX Spike to 35', 'vix_to': 35},
                {'name': 'VIX Spike to 50', 'vix_to': 50},
            ]

        results = []
        greeks = state.get('portfolio_greeks', {})
        delta = greeks.get('delta', 0)
        gamma = greeks.get('gamma', 0)
        theta = greeks.get('theta', 0)
        vega = greeks.get('vega', 0)
        current_vix = state.get('vix', 20)

        for s in scenarios:
            pnl = 0
            if 'move' in s:
                move_pct = s['move']
                # Delta P&L + Gamma adjustment
                pnl = delta * move_pct + 0.5 * gamma * (move_pct ** 2)
                # VIX typically moves ~3x inverse of SPY
                vix_move = -move_pct * 3
                pnl += vega * vix_move * 0.01
            elif 'vix_to' in s:
                vix_change = s['vix_to'] - current_vix
                pnl = vega * vix_change * 0.01

            # Add daily theta
            pnl += theta

            results.append({
                'scenario': s['name'],
                'estimated_pnl': round(pnl, 2),
                'pnl_pct': round(pnl / config.VIRTUAL_ACCOUNT_SIZE * 100, 2),
                'surviving': pnl > config.MAX_DAILY_LOSS,
            })

        # Position concentration risk
        open_spreads = [s for s in state.get('credit_spreads', []) if s['status'] in ['open', 'pending']]
        
        sectors = {}
        for s in open_spreads:
            sec = config.SECTOR_MAP.get(s['symbol'], 'Other')
            sectors[sec] = sectors.get(sec, 0) + 1
        for t in open_dir:
            sec = config.SECTOR_MAP.get(t['symbol'], 'Other')
            sectors[sec] = sectors.get(sec, 0) + 1

        # Max single-position risk
        max_risk = 0
        for s in open_spreads:
            risk = (config.CS_SPREAD_WIDTH - s['credit']) * s.get('contracts', 1) * 100
            max_risk = max(max_risk, risk)
        for t in open_dir:
            max_risk = max(max_risk, risk)

        total_risk = sum((config.CS_SPREAD_WIDTH - s['credit']) * s.get('contracts', 1) * 100 for s in open_spreads)

        self.last_stress = datetime.now().isoformat()
        
        return {
            'scenarios': results,
            'sector_exposure': sectors,
            'total_positions': len(open_spreads) + len(open_dir),
            'total_risk': round(total_risk, 2),
            'max_single_risk': round(max_risk, 2),
            'risk_pct_of_account': round(total_risk / config.VIRTUAL_ACCOUNT_SIZE * 100, 1),
            'portfolio_delta': round(delta, 2),
            'portfolio_theta': round(theta, 2),
            'daily_theta_income': round(theta, 2),
            'current_vix': current_vix,
            'last_stress': self.last_stress,
        }

    def calculate_correlations(self, symbols=None):
        """Calculate correlation matrix for open positions"""
        if not symbols:
            return {}
        
        # Get 30 days of history for each symbol
        price_data = {}
        for sym in symbols[:15]:  # Limit to 15 to avoid rate limits
            try:
                history = self.api.get_history(sym, 30)
                if history and len(history) >= 10:
                    closes = [d.get('close', 0) for d in history if d.get('close', 0) > 0]
                    if len(closes) >= 10:
                        # Calculate returns
                        returns = []
                        for i in range(1, len(closes)):
                            returns.append((closes[i] - closes[i-1]) / closes[i-1])
                        price_data[sym] = returns
            except: continue

        # Calculate pairwise correlations
        matrix = {}
        syms = list(price_data.keys())
        for i in range(len(syms)):
            for j in range(i, len(syms)):
                if i == j:
                    if syms[i] not in matrix: matrix[syms[i]] = {}
                    matrix[syms[i]][syms[j]] = 1.0
                    continue
                
                r1 = price_data[syms[i]]
                r2 = price_data[syms[j]]
                n = min(len(r1), len(r2))
                if n < 5: continue
                
                corr = self._pearson(r1[:n], r2[:n])
                if syms[i] not in matrix: matrix[syms[i]] = {}
                if syms[j] not in matrix: matrix[syms[j]] = {}
                matrix[syms[i]][syms[j]] = corr
                matrix[syms[j]][syms[i]] = corr

        self.correlation_cache = matrix
        
        # Find highly correlated pairs
        high_corr = []
        for i in range(len(syms)):
            for j in range(i+1, len(syms)):
                if syms[i] in matrix and syms[j] in matrix.get(syms[i], {}):
                    c = matrix[syms[i]][syms[j]]
                    if abs(c) > 0.7:
                        high_corr.append({
                            'pair': f"{syms[i]}/{syms[j]}",
                            'correlation': round(c, 2),
                            'risk': 'HIGH' if abs(c) > 0.85 else 'MODERATE'
                        })

        return {
            'matrix': {s: {s2: round(v, 2) for s2, v in pairs.items()} for s, pairs in matrix.items()},
            'high_correlations': high_corr,
            'symbols_analyzed': len(syms),
        }

    def _pearson(self, x, y):
        """Pearson correlation coefficient"""
        n = len(x)
        if n < 3: return 0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        std_x = math.sqrt(sum((xi - mean_x)**2 for xi in x))
        std_y = math.sqrt(sum((yi - mean_y)**2 for yi in y))
        if std_x == 0 or std_y == 0: return 0
        return round(cov / (std_x * std_y), 3)

    def get_sector_heatmap(self):
        """Get sector performance for heatmap display"""
        sector_etfs = {
            'Tech': 'XLK', 'Finance': 'XLF', 'Healthcare': 'XLV',
            'Energy': 'XLE', 'Consumer': 'XLY', 'Industrial': 'XLI',
            'Telecom': 'XLC', 'ETF': 'SPY', 'Semiconductor': 'SOXX',
        }
        
        symbols = list(sector_etfs.values())
        quotes = self.api.get_quotes(symbols)
        
        heatmap = []
        for sector, etf in sector_etfs.items():
            q = quotes.get(etf, {})
            chg = q.get('change_percentage', 0)
            if isinstance(chg, str):
                try: chg = float(chg.replace('%', ''))
                except: chg = 0
            heatmap.append({
                'sector': sector,
                'etf': etf,
                'change_pct': round(chg, 2),
                'price': q.get('last', 0),
                'volume': q.get('volume', 0),
            })
        
        heatmap.sort(key=lambda x: x['change_pct'], reverse=True)
        return heatmap
