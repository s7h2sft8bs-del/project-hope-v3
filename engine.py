"""PROJECT HOPE v3.0 FINAL - Trading Engine - All Systems Integrated"""
import threading, time, csv, io
from datetime import datetime, date
from tradier_api import TradierAPI
from credit_spread_scanner import CreditSpreadScanner
from position_manager import PositionManager
from protections import Protections
from alerts import Alerts
from analytics import Analytics
from greeks import GreeksDashboard
from screener import OptionsScreener
from backtester import Backtester
from storage import Storage, AutoSaver
from earnings import EarningsCalendar
from iv_rank import IVRankCalculator
from risk_analyzer import RiskAnalyzer
from journal import TradeJournal
from economic_calendar import EconomicCalendar
import config

class TradingEngine:
    def __init__(self):
        self.api = TradierAPI()
        self.alerts = Alerts()
        self.storage = Storage()
        self.state = {
            'autopilot':True,'connected':False,'balance':{},'vix':20,
            'daily_pnl':0,'last_trade_time':None,
            'credit_spreads':[],'cs_trades_today':0,
            
            'wins':0,'losses':0,'consecutive_losses':0,'total_pnl':0,
            'activity_log':[],'engine_running':False,'last_scan':None,
            'market_open':False,'in_window':False,'today':str(date.today()),
            'spread_opportunities':[],
            'portfolio_greeks':{'delta':0,'gamma':0,'theta':0,'vega':0,'positions':[]},
            'screener_results':{'spreads':[],'scan_time':None,'symbols_scanned':0},
            'backtest_results':None,'backtest_running':False,
            'theme':'dark',
            'tier': config.TIER,
            'auto_close': config.AUTO_CLOSE_ENABLED,
            'overnight_hold': False,  # User can toggle this on
        }

        # === RESTORE SAVED STATE ===
        saved = self.storage.load_state()
        if saved:
            for key in ['credit_spreads','wins','losses',
                        'consecutive_losses','total_pnl','daily_pnl',
                        'cs_trades_today','theme','autopilot']:
                if key in saved: self.state[key] = saved[key]
            if saved.get('today','') != str(date.today()):
                self.state.update({'cs_trades_today':0,'daily_pnl':0,'consecutive_losses':0})
            self._log('system', f"RESTORED: {self.state['wins']}W/{self.state['losses']}L | P&L: ${self.state['total_pnl']:.2f}")
        else:
            self._log('system', 'Fresh start - no saved state')

        # === INIT ALL MODULES ===
        self.spread_scanner = CreditSpreadScanner(self.api, self.state)
        self.protections = Protections(self.api, self.state)
        self.analytics = Analytics(self.storage)
        self.position_manager = PositionManager(self.api, self.state, self.alerts, self.analytics)
        self.greeks_dash = GreeksDashboard(self.api)
        self.screener = OptionsScreener(self.api)
        self.backtester = Backtester(self.api)
        self.autosaver = AutoSaver(self.storage, self, interval=30)
        self.earnings = EarningsCalendar(self.api, self.storage)
        self.iv_rank = IVRankCalculator(self.api)
        self.risk = RiskAnalyzer(self.api)
        self.journal = TradeJournal(self.storage)
        self.econ_cal = EconomicCalendar()
        self._log('system', f'Engine initialized. {len(config.WATCHLIST)} symbols. {len(self.analytics.trade_history)} trades loaded.')
        self._log('system', f'Tier: {config.ACTIVE_TIER["name"]} | Max Positions: {config.ACTIVE_TIER["max_positions"]} | Spreads: {"YES" if config.ACTIVE_TIER["allow_spreads"] else "NO"}')

    def start(self):
        self.state['engine_running'] = True
        balance = self.api.get_account_balance()
        if balance:
            self.state['connected'] = True; self.state['balance'] = balance
            self._log('system', f"Connected. Balance: ${balance['total_value']:,.2f}")
        else:
            self._log('alert', 'API connection - using virtual balance')

        self.autosaver.start()
        self.earnings.start_refresh_loop()
        self.iv_rank.start_refresh_loop()

        for fn in [self._position_loop, self._spread_loop,
                   self._account_loop, self._clock_loop, self._reset_loop,
                   self._greeks_loop, self._screener_loop]:
            threading.Thread(target=fn, daemon=True).start()

        # Check economic calendar on start
        is_high, events = self.econ_cal.is_high_impact_day()
        if is_high:
            names = ', '.join(e['event'] for e in events)
            self._log('alert', f"HIGH IMPACT DAY: {names}")

        self._log('system', 'All 9 threads started + earnings + IV rank active')

    def _position_loop(self):
        while self.state['engine_running']:
            try:
                if self.state['autopilot'] and self.state['market_open']:
                    self.position_manager.check_all_positions()
                    self._sync_orders()
                    # Auto-journal closed trades
                    self._auto_journal_closed()
            except Exception as e: print(f"[POS ERR] {e}")
            time.sleep(config.POSITION_CHECK_INTERVAL)

    def _spread_loop(self):
        while self.state['engine_running']:
            try:
                if self.state['autopilot'] and self.state['market_open']:
                    # Tier check - Starter cannot trade spreads
                    if not config.ACTIVE_TIER['allow_spreads']:
                        time.sleep(config.SPREAD_SCAN_INTERVAL)
                        continue
                    # Position limit check based on tier
                    total_open = len([s for s in self.state['credit_spreads'] if s['status'] in ['open','pending']])
                    if total_open >= config.ACTIVE_TIER['max_positions']:
                        time.sleep(config.SPREAD_SCAN_INTERVAL)
                        continue
                    passed, reason = self.protections.check_all('spread')
                    if passed:
                        opps = self.spread_scanner.scan()
                        self.state['spread_opportunities'] = opps[:5]
                        if opps:
                            best = opps[0]
                            # Earnings blackout check
                            blk, blk_msg = self.earnings.is_earnings_blackout(best['symbol'])
                            if blk:
                                self._log('alert', f"BLOCKED: {blk_msg}")
                            else:
                                # Sector + duplicate check
                                sok, _ = self.protections.check_sector_limit(best['symbol'])
                                if sok:
                                    # IV rank check
                                    iv_ok, iv_msg = self.iv_rank.is_iv_favorable(best['symbol'], 'spread')
                                    if iv_ok:
                                        # Tier spread width check
                                        spread_w = best.get('width', config.CS_SPREAD_WIDTH)
                                        if spread_w > config.ACTIVE_TIER['max_spread_width']:
                                            self._log('system', f"Tier {config.ACTIVE_TIER['name']}: spread too wide (${spread_w} > ${config.ACTIVE_TIER['max_spread_width']})")
                                        else:
                                            result = self.spread_scanner.execute_spread(best)
                                            if result:
                                                self.state['last_trade_time'] = datetime.now()
                                                self._log('entry', f"SPREAD: {best['symbol']} ${best['credit']} credit")
                                                self.alerts.send(f"NEW SPREAD: {best['symbol']}\nCredit: ${best['credit']}")
                                                self.storage.save_state(self.state)
                                    else:
                                        self._log('system', f"IV skip: {iv_msg}")
            except Exception as e: print(f"[SPREAD ERR] {e}")
            time.sleep(config.SPREAD_SCAN_INTERVAL)

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
                        all_sp.extend(r.get('spreads',[]))
                        time.sleep(2)
                    all_sp.sort(key=lambda x:x.get('score',0), reverse=True)
                    all_dr.sort(key=lambda x:x.get('score',0), reverse=True)
                    self.state['screener_results'] = {
                        'spreads':all_sp[:20],
                        'scan_time':datetime.now().isoformat(),'symbols_scanned':len(syms),
                        'total_spread_opps':len(all_sp),'total_dir_opps':len(all_dr)}
            except Exception as e: print(f"[SCR ERR] {e}")
            time.sleep(120)

    def _clock_loop(self):
        while self.state['engine_running']:
            try:
                try:
                    import pytz; now = datetime.now(pytz.timezone('US/Eastern'))
                except: now = datetime.now()
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
                    self.storage.update_daily_summary(
                        self.state['today'],
                        self.state['cs_trades_today'] + self.state['dir_trades_today'],
                        self.state['wins'], self.state['losses'], self.state['daily_pnl'])
                    self.state.update({'today':today,'cs_trades_today':0,'dir_trades_today':0,
                                       'daily_pnl':0,'consecutive_losses':0})
                    self.state.pop('eod_closed_today', None)
                    self._log('system', f'New day: {today}')
                    self.storage.save_state(self.state)
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
        except: pass

    def _auto_journal_closed(self):
        """Auto-create journal entries for newly closed trades"""
        for s in self.state['credit_spreads']:
            if s.get('status') == 'closed' and not s.get('journaled'):
                self.journal.add_auto_entry(s, s.get('close_reason', 'unknown'))
                s['journaled'] = True

    def _calc_pnl(self):
        total = sum(s.get('current_profit',0)*s['contracts']*100 for s in self.state['credit_spreads'] if s.get('current_profit'))
        self.state['daily_pnl'] = round(total, 2)

    def _eod_close(self):
        if not self.state.get('eod_closed_today'):
            # Skip auto-close if user toggled overnight holds ON
            if self.state.get('overnight_hold', False):
                self._log('system', 'Overnight hold ON - skipping auto-close')
                self.state['eod_closed_today'] = True
                return
            # Credit spreads managed by position_manager, no EOD force-close needed
            self.state['eod_closed_today'] = True
            self.storage.save_state(self.state)

    def toggle_autopilot(self):
        self.state['autopilot'] = not self.state['autopilot']
        s = "ON" if self.state['autopilot'] else "OFF"
        self._log('system', f'Autopilot {s}'); self.alerts.send(f"Autopilot {s}")
        self.storage.save_state(self.state)
        return self.state['autopilot']

    def toggle_overnight(self):
        self.state['overnight_hold'] = not self.state.get('overnight_hold', False)
        s = "ON" if self.state['overnight_hold'] else "OFF"
        self._log('system', f'Overnight hold {s} — {"positions will NOT auto-close at 3:55 PM" if self.state["overnight_hold"] else "positions WILL auto-close at 3:55 PM"}')
        self.storage.save_state(self.state)
        return self.state['overnight_hold']

    def set_theme(self, theme):
        self.state['theme'] = theme
        self.storage.save_state(self.state)

    def run_backtest(self, symbol='SPY', days=365):
        self.state['backtest_running'] = True
        try:
            r = self.backtester.run_credit_spread_backtest(symbol, days)
            self.state['backtest_results'] = r
            if 'error' not in r:
                self.storage.save_backtest(r)
                self._log('system', f"Backtest: {r['win_rate']}% WR | ${r['total_pnl']} | Sharpe {r['sharpe']}")
        except Exception as e:
            self.state['backtest_results'] = {'error': str(e)}
        self.state['backtest_running'] = False
        return self.state['backtest_results']

    def export_trades_csv(self):
        """Export all trades to CSV string"""
        history = self.storage.load_trade_history()
        if not history: return ""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date','Symbol','Type','Direction','Entry','Exit','P&L','Reason','Setup'])
        for t in history:
            writer.writerow([
                t.get('closed_at','')[:10], t.get('symbol',''), t.get('type',''),
                t.get('direction',''), t.get('entry_price',''), t.get('exit_price',''),
                t.get('pnl',0), t.get('close_reason',''), t.get('setup_type',''),
            ])
        return output.getvalue()

    def get_dashboard_data(self):
        vv = config.VIRTUAL_ACCOUNT_SIZE + self.state.get('total_pnl', 0)
        os_ = [s for s in self.state['credit_spreads'] if s['status'] in ['open','pending']]
        w=self.state['wins'];l=self.state['losses']
        wr=round((w/(w+l))*100,1) if (w+l)>0 else 0
        used=sum((config.CS_SPREAD_WIDTH-s['credit'])*s['contracts']*100 for s in os_)
        used+=sum(t['entry_price']*t['current_qty']*100 for t in od)
        
        # Sector heatmap (cached, only refresh occasionally)
        heatmap = []
        try: heatmap = self.risk.get_sector_heatmap()
        except: pass

        return {
            'autopilot':self.state['autopilot'],'connected':self.state['connected'],
            'market_open':self.state['market_open'],'in_window':self.state['in_window'],
            'vix':self.state['vix'],'account_value':round(vv,2),
            'buying_power':round(config.VIRTUAL_ACCOUNT_SIZE-used,2),
            'daily_pnl':self.state['daily_pnl'],'total_pnl':self.state['total_pnl'],
            'open_positions':len(os_)+len(od),'win_rate':wr,'wins':w,'losses':l,
            'credit_spreads':os_,
            'spread_opportunities':self.state.get('spread_opportunities',[]),
                        'activity_log':self.state['activity_log'][:50],
            'cs_trades_today':self.state['cs_trades_today'],'dir_trades_today':self.state['dir_trades_today'],
            'consecutive_losses':self.state.get('consecutive_losses',0),
            'portfolio_greeks':self.state.get('portfolio_greeks',{}),
            'screener_results':self.state.get('screener_results',{}),
            'backtest_results':self.state.get('backtest_results'),
            'backtest_running':self.state.get('backtest_running',False),
            'analytics':self.analytics.get_full_report(),
            'watchlist_count':len(config.WATCHLIST),
            'storage_stats':self.storage.get_storage_stats(),
            'earnings':self.earnings.get_data(),
            'iv_rank':self.iv_rank.get_data(),
            'econ_calendar':self.econ_cal.get_data(),
            'journal_stats':self.journal.get_stats(),
            'sector_heatmap':heatmap,
            'theme':self.state.get('theme','dark'),
            'tier': config.ACTIVE_TIER,
            'tier_name': config.ACTIVE_TIER['name'],
            'overnight_hold': self.state.get('overnight_hold', False),
            'auto_close': not self.state.get('overnight_hold', False),
        }

    def _log(self, lt, msg):
        self.state['activity_log'].insert(0, {'time':datetime.now().strftime('%H:%M:%S'),'type':lt,'message':msg})
        if len(self.state['activity_log'])>200: self.state['activity_log']=self.state['activity_log'][:200]
        print(f"[{lt.upper()}] {msg}")
