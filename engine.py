"""PROJECT HOPE v3.0 - Trading Engine - The Brain"""
import threading, time
from datetime import datetime, date
from tradier_api import TradierAPI
from credit_spread_scanner import CreditSpreadScanner
from directional_scanner import DirectionalScanner
from position_manager import PositionManager
from protections import Protections
from alerts import Alerts
from analytics import Analytics
from greeks import GreeksDashboard
from screener import OptionsScreener
from backtester import Backtester
import config

class TradingEngine:
    def __init__(self):
        self.api = TradierAPI()
        self.alerts = Alerts()
        self.state = {
            'autopilot':False,'connected':False,'balance':{},'vix':20,
            'daily_pnl':0,'last_trade_time':None,
            'credit_spreads':[],'cs_trades_today':0,
            'directional_trades':[],'dir_trades_today':0,
            'wins':0,'losses':0,'consecutive_losses':0,'total_pnl':0,
            'activity_log':[],'engine_running':False,'last_scan':None,
            'market_open':False,'in_window':False,'today':str(date.today()),
            'spread_opportunities':[],'directional_opportunities':[],
            'portfolio_greeks':{'delta':0,'gamma':0,'theta':0,'vega':0,'positions':[]},
            'screener_results':{'spreads':[],'directional':[],'scan_time':None,'symbols_scanned':0},
            'backtest_results':None,'backtest_running':False,
        }
        self.spread_scanner = CreditSpreadScanner(self.api, self.state)
        self.directional_scanner = DirectionalScanner(self.api, self.state)
        self.position_manager = PositionManager(self.api, self.state, self.alerts)
        self.protections = Protections(self.api, self.state)
        self.analytics = Analytics()
        self.greeks_dash = GreeksDashboard(self.api)
        self.screener = OptionsScreener(self.api)
        self.backtester = Backtester(self.api)
        self._log('system', f'Engine initialized. Scanning {len(config.WATCHLIST)} symbols.')

    def start(self):
        self.state['engine_running'] = True
        balance = self.api.get_account_balance()
        if balance:
            self.state['connected'] = True; self.state['balance'] = balance
            self._log('system', f"Connected. Balance: ${balance['total_value']:,.2f}")
        else:
            self._log('alert', 'Failed to connect to Tradier API')
        for fn in [self._position_loop, self._spread_loop, self._directional_loop,
                   self._account_loop, self._clock_loop, self._reset_loop,
                   self._greeks_loop, self._screener_loop]:
            threading.Thread(target=fn, daemon=True).start()
        self._log('system', 'All engine threads started')

    def _position_loop(self):
        while self.state['engine_running']:
            try:
                if self.state['autopilot'] and self.state['market_open']:
                    self.position_manager.check_all_positions()
                    self._sync_orders()
            except Exception as e: print(f"[POS ERR] {e}")
            time.sleep(config.POSITION_CHECK_INTERVAL)

    def _spread_loop(self):
        while self.state['engine_running']:
            try:
                if self.state['autopilot'] and self.state['market_open']:
                    passed, _ = self.protections.check_all('spread')
                    if passed:
                        opps = self.spread_scanner.scan()
                        self.state['spread_opportunities'] = opps[:5]
                        if opps:
                            best = opps[0]
                            sok, _ = self.protections.check_sector_limit(best['symbol'])
                            if sok:
                                result = self.spread_scanner.execute_spread(best)
                                if result:
                                    self.state['last_trade_time'] = datetime.now()
                                    self._log('entry', f"SPREAD: {best['symbol']} ${best['credit']} credit")
                                    self.alerts.send(f"NEW SPREAD: {best['symbol']}\nCredit: ${best['credit']}")
            except Exception as e: print(f"[SPREAD ERR] {e}")
            time.sleep(config.SPREAD_SCAN_INTERVAL)

    def _directional_loop(self):
        while self.state['engine_running']:
            try:
                if self.state['autopilot'] and self.state['market_open']:
                    passed, _ = self.protections.check_all('directional')
                    if passed:
                        opps = self.directional_scanner.scan()
                        self.state['directional_opportunities'] = opps[:5]
                        if opps and opps[0]['score'] >= 70:
                            best = opps[0]
                            sok, _ = self.protections.check_sector_limit(best['symbol'])
                            if sok:
                                result = self.directional_scanner.execute_trade(best)
                                if result:
                                    self.state['last_trade_time'] = datetime.now()
                                    self._log('entry', f"TRADE: {best['symbol']} {best['setup_type']} Score:{best['score']}")
                                    self.alerts.send(f"NEW: {best['symbol']} {best['setup_type']}")
            except Exception as e: print(f"[DIR ERR] {e}")
            time.sleep(config.DIRECTIONAL_SCAN_INTERVAL)

    def _account_loop(self):
        while self.state['engine_running']:
            try:
                bal = self.api.get_account_balance()
                if bal: self.state['balance'] = bal; self.state['connected'] = True
                self.state['vix'] = self.api.get_vix()
                self._calc_pnl()
            except: pass
            time.sleep(config.ACCOUNT_REFRESH_INTERVAL)

    def _greeks_loop(self):
        while self.state['engine_running']:
            try:
                if self.state['market_open']:
                    self.state['portfolio_greeks'] = self.greeks_dash.get_portfolio_greeks(self.state)
            except: pass
            time.sleep(15)

    def _screener_loop(self):
        while self.state['engine_running']:
            try:
                if self.state['market_open']:
                    syms = config.WATCHLIST; all_sp = []; all_dr = []
                    for i in range(0, len(syms), 20):
                        r = self.screener.full_scan(syms[i:i+20])
                        all_sp.extend(r.get('spreads',[])); all_dr.extend(r.get('directional',[]))
                        time.sleep(2)
                    all_sp.sort(key=lambda x:x.get('score',0), reverse=True)
                    all_dr.sort(key=lambda x:x.get('score',0), reverse=True)
                    self.state['screener_results'] = {
                        'spreads':all_sp[:20],'directional':all_dr[:20],
                        'scan_time':datetime.now().isoformat(),'symbols_scanned':len(syms),
                        'total_spread_opps':len(all_sp),'total_dir_opps':len(all_dr)}
            except Exception as e: print(f"[SCR ERR] {e}")
            time.sleep(120)

    def _clock_loop(self):
        while self.state['engine_running']:
            try:
                now = self.protections._get_et_now()
                mins = now.hour*60+now.minute; wd = now.weekday()
                self.state['market_open'] = wd<5 and 570<=mins<=960
                self.state['in_window'] = (570<=mins<=630) or (900<=mins<=955)
                if wd<5 and mins>=955: self._eod_close()
            except: pass
            time.sleep(1)

    def _reset_loop(self):
        while self.state['engine_running']:
            try:
                today = str(date.today())
                if today != self.state['today']:
                    self.state.update({'today':today,'cs_trades_today':0,'dir_trades_today':0,
                                       'daily_pnl':0,'consecutive_losses':0})
                    self.state.pop('eod_closed_today', None)
                    self._log('system', f'New day: {today}')
            except: pass
            time.sleep(60)

    def _sync_orders(self):
        try:
            orders = self.api.get_orders()
            if not orders: return
            om = {str(o.get('id','')): o.get('status','') for o in orders}
            for s in self.state['credit_spreads']:
                oid = str(s.get('order_id',''))
                if oid in om:
                    if om[oid]=='filled' and s['status']=='pending': s['status']='open'
                    elif om[oid] in ['rejected','canceled']: s['status']='rejected'
            for t in self.state['directional_trades']:
                oid = str(t.get('order_id',''))
                if oid in om:
                    if om[oid]=='filled' and t['status']=='pending': t['status']='open'
                    elif om[oid] in ['rejected','canceled']: t['status']='rejected'
        except: pass

    def _calc_pnl(self):
        total = sum(s.get('current_profit',0)*s['contracts']*100 for s in self.state['credit_spreads'] if s.get('current_profit'))
        total += sum(t.get('pnl',0) for t in self.state['directional_trades'] if t.get('pnl'))
        self.state['daily_pnl'] = round(total, 2)

    def _eod_close(self):
        if not self.state.get('eod_closed_today'):
            for t in self.state['directional_trades']:
                if t['status']=='open' and not t.get('manual_override'):
                    self.position_manager._close_directional(t, t['current_qty'], "EOD AUTO-CLOSE")
            self.state['eod_closed_today'] = True

    def toggle_autopilot(self):
        self.state['autopilot'] = not self.state['autopilot']
        s = "ON" if self.state['autopilot'] else "OFF"
        self._log('system', f'Autopilot {s}'); self.alerts.send(f"Autopilot {s}")
        return self.state['autopilot']

    def run_backtest(self, symbol='SPY', days=365):
        self.state['backtest_running'] = True
        try:
            r = self.backtester.run_credit_spread_backtest(symbol, days)
            self.state['backtest_results'] = r
            if 'error' not in r:
                self._log('system', f"Backtest: {r['win_rate']}% WR | ${r['total_pnl']} | Sharpe {r['sharpe_ratio']}")
        except Exception as e:
            self.state['backtest_results'] = {'error': str(e)}
        self.state['backtest_running'] = False
        return self.state['backtest_results']

    def get_dashboard_data(self):
        vv = config.VIRTUAL_ACCOUNT_SIZE + self.state.get('daily_pnl', 0)
        os_ = [s for s in self.state['credit_spreads'] if s['status'] in ['open','pending']]
        od = [t for t in self.state['directional_trades'] if t['status'] in ['open','pending']]
        w=self.state['wins'];l=self.state['losses']
        wr=round((w/(w+l))*100,1) if (w+l)>0 else 0
        used=sum((config.CS_SPREAD_WIDTH-s['credit'])*s['contracts']*100 for s in os_)
        used+=sum(t['entry_price']*t['current_qty']*100 for t in od)
        return {
            'autopilot':self.state['autopilot'],'connected':self.state['connected'],
            'market_open':self.state['market_open'],'in_window':self.state['in_window'],
            'vix':self.state['vix'],'account_value':round(vv,2),
            'buying_power':round(config.VIRTUAL_ACCOUNT_SIZE-used,2),
            'daily_pnl':self.state['daily_pnl'],'total_pnl':self.state['total_pnl'],
            'open_positions':len(os_)+len(od),'win_rate':wr,'wins':w,'losses':l,
            'credit_spreads':os_,'directional_trades':od,
            'spread_opportunities':self.state.get('spread_opportunities',[]),
            'directional_opportunities':self.state.get('directional_opportunities',[]),
            'activity_log':self.state['activity_log'][:50],
            'cs_trades_today':self.state['cs_trades_today'],'dir_trades_today':self.state['dir_trades_today'],
            'consecutive_losses':self.state.get('consecutive_losses',0),
            'cs_allocation':config.VIRTUAL_ACCOUNT_SIZE*config.CREDIT_SPREAD_ALLOCATION,
            'dir_allocation':config.VIRTUAL_ACCOUNT_SIZE*config.DIRECTIONAL_ALLOCATION,
            'portfolio_greeks':self.state.get('portfolio_greeks',{}),
            'screener_results':self.state.get('screener_results',{}),
            'backtest_results':self.state.get('backtest_results'),
            'backtest_running':self.state.get('backtest_running',False),
            'analytics':self.analytics.get_full_report(),
            'watchlist_count':len(config.WATCHLIST),
        }

    def _log(self, lt, msg):
        self.state['activity_log'].insert(0, {'time':datetime.now().strftime('%H:%M:%S'),'type':lt,'message':msg})
        if len(self.state['activity_log'])>200: self.state['activity_log']=self.state['activity_log'][:200]
        print(f"[{lt.upper()}] {msg}")
