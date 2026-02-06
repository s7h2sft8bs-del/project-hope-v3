"""PROJECT HOPE v3.0 - Performance Analytics with Persistent Storage"""
import math
from datetime import datetime
import config

class Analytics:
    def __init__(self, storage=None):
        self.storage = storage
        self.trade_history = []
        # Load saved trade history on startup
        if storage:
            saved = storage.load_trade_history()
            if saved:
                self.trade_history = saved
                print(f"[ANALYTICS] Loaded {len(saved)} trades from storage")

    def record_trade(self, trade_data):
        entry = {
            'symbol': trade_data.get('symbol', ''),
            'type': trade_data.get('type', ''),
            'direction': trade_data.get('direction', ''),
            'entry_price': trade_data.get('entry_price', 0),
            'exit_price': trade_data.get('exit_price', 0),
            'pnl': trade_data.get('pnl', 0),
            'contracts': trade_data.get('contracts', 0),
            'opened_at': trade_data.get('opened_at', ''),
            'closed_at': trade_data.get('closed_at', datetime.now().isoformat()),
            'setup_type': trade_data.get('setup_type', ''),
            'close_reason': trade_data.get('close_reason', ''),
        }
        self.trade_history.append(entry)
        # Save to disk immediately
        if self.storage:
            self.storage.save_trade(entry)

    def get_full_report(self):
        if not self.trade_history:
            return self._empty_report()

        pnls = [t['pnl'] for t in self.trade_history]
        wins = [t for t in self.trade_history if t['pnl'] > 0]
        losses = [t for t in self.trade_history if t['pnl'] <= 0]
        total = len(self.trade_history)
        win_count = len(wins); loss_count = len(losses)
        win_rate = round((win_count / total) * 100, 1) if total > 0 else 0
        total_pnl = round(sum(pnls), 2)
        gross_profit = round(sum(t['pnl'] for t in wins), 2)
        gross_loss = round(abs(sum(t['pnl'] for t in losses)), 2)
        avg_win = round(gross_profit / win_count, 2) if win_count > 0 else 0
        avg_loss = round(gross_loss / loss_count, 2) if loss_count > 0 else 0
        largest_win = round(max(pnls), 2) if pnls else 0
        largest_loss = round(min(pnls), 2) if pnls else 0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 999
        expectancy = round(total_pnl / total, 2) if total > 0 else 0
        mw, ml, cur, ct = self._streaks()
        sharpe = self._sharpe(pnls)
        mdd, mddp = self._drawdown()
        monthly = self._monthly()

        spread_trades = [t for t in self.trade_history if 'spread' in t.get('type', '')]
        dir_trades = [t for t in self.trade_history if t.get('type') == 'directional']

        setup_stats = {}
        for t in self.trade_history:
            st = t.get('setup_type', 'unknown')
            if st not in setup_stats: setup_stats[st] = {'wins':0,'losses':0,'pnl':0}
            if t['pnl'] > 0: setup_stats[st]['wins'] += 1
            else: setup_stats[st]['losses'] += 1
            setup_stats[st]['pnl'] += t['pnl']
        for k in setup_stats:
            tot = setup_stats[k]['wins'] + setup_stats[k]['losses']
            setup_stats[k]['win_rate'] = round((setup_stats[k]['wins']/tot)*100,1) if tot>0 else 0
            setup_stats[k]['pnl'] = round(setup_stats[k]['pnl'], 2)

        symbol_stats = {}
        for t in self.trade_history:
            sym = t['symbol']
            if sym not in symbol_stats: symbol_stats[sym] = {'trades':0,'wins':0,'pnl':0}
            symbol_stats[sym]['trades'] += 1
            if t['pnl'] > 0: symbol_stats[sym]['wins'] += 1
            symbol_stats[sym]['pnl'] += t['pnl']
        for k in symbol_stats:
            symbol_stats[k]['win_rate'] = round((symbol_stats[k]['wins']/symbol_stats[k]['trades'])*100,1)
            symbol_stats[k]['pnl'] = round(symbol_stats[k]['pnl'], 2)
        sorted_syms = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)

        # Weekly breakdown
        weekly = self._weekly()

        return {
            'total_trades':total,'win_rate':win_rate,'wins':win_count,'losses':loss_count,
            'total_pnl':total_pnl,'gross_profit':gross_profit,'gross_loss':gross_loss,
            'avg_win':avg_win,'avg_loss':avg_loss,'largest_win':largest_win,'largest_loss':largest_loss,
            'profit_factor':profit_factor,'expectancy':expectancy,'sharpe_ratio':sharpe,
            'max_drawdown':mdd,'max_drawdown_pct':mddp,
            'max_win_streak':mw,'max_loss_streak':ml,'current_streak':cur,'streak_type':ct,
            'monthly':monthly,'weekly':weekly,
            'spread_stats':self._ss(spread_trades,'Credit Spreads'),
            'directional_stats':self._ss(dir_trades,'Directional'),
            'setup_stats':setup_stats,
            'top_symbols':[{'symbol':s[0],**s[1]} for s in sorted_syms[:5]],
            'bottom_symbols':[{'symbol':s[0],**s[1]} for s in sorted_syms[-5:]],
            'equity_curve':self._equity(),
            'recent_trades':self.trade_history[-30:],
            'first_trade_date':self.trade_history[0].get('closed_at','')[:10] if self.trade_history else '',
            'days_trading': self._days_trading(),
        }

    def _streaks(self):
        mw=ml=cur=0;ct='';last=None
        for t in self.trade_history:
            if t['pnl']>0:
                cur=cur+1 if last=='w' else 1;last='w';ct='win';mw=max(mw,cur)
            else:
                cur=cur+1 if last=='l' else 1;last='l';ct='loss';ml=max(ml,cur)
        return mw,ml,cur,ct

    def _sharpe(self, pnls):
        if len(pnls)<2: return 0
        avg=sum(pnls)/len(pnls)
        std=math.sqrt(sum((p-avg)**2 for p in pnls)/(len(pnls)-1))
        if std==0: return 0
        return round(((avg-config.RISK_FREE_RATE/252)/std)*math.sqrt(252),2)

    def _drawdown(self):
        bal=config.BACKTEST_INITIAL_BALANCE;peak=bal;mdd=0;mddp=0
        for t in self.trade_history:
            bal+=t['pnl']
            if bal>peak: peak=bal
            dd=peak-bal;ddp=(dd/peak)*100 if peak>0 else 0
            if dd>mdd: mdd=dd;mddp=ddp
        return round(mdd,2),round(mddp,1)

    def _monthly(self):
        m={}
        for t in self.trade_history:
            k=t.get('closed_at','')[:7]
            if not k: continue
            if k not in m: m[k]={'pnl':0,'trades':0,'wins':0}
            m[k]['pnl']+=t['pnl'];m[k]['trades']+=1
            if t['pnl']>0: m[k]['wins']+=1
        result=[]
        for k in sorted(m.keys()):
            d=m[k];d['month']=k;d['pnl']=round(d['pnl'],2)
            d['win_rate']=round((d['wins']/d['trades'])*100,1) if d['trades']>0 else 0
            result.append(d)
        return result

    def _weekly(self):
        w={}
        for t in self.trade_history:
            dt=t.get('closed_at','')[:10]
            if not dt: continue
            try:
                from datetime import datetime as DT
                d = DT.strptime(dt, '%Y-%m-%d')
                # Get Monday of that week
                monday = d - __import__('datetime').timedelta(days=d.weekday())
                wk = monday.strftime('%Y-%m-%d')
            except: continue
            if wk not in w: w[wk]={'pnl':0,'trades':0,'wins':0}
            w[wk]['pnl']+=t['pnl'];w[wk]['trades']+=1
            if t['pnl']>0: w[wk]['wins']+=1
        result=[]
        for k in sorted(w.keys()):
            d=w[k];d['week']=k;d['pnl']=round(d['pnl'],2)
            d['win_rate']=round((d['wins']/d['trades'])*100,1) if d['trades']>0 else 0
            result.append(d)
        return result

    def _days_trading(self):
        dates = set()
        for t in self.trade_history:
            dt = t.get('closed_at','')[:10]
            if dt: dates.add(dt)
        return len(dates)

    def _equity(self):
        curve=[];bal=config.BACKTEST_INITIAL_BALANCE
        for i,t in enumerate(self.trade_history):
            bal+=t['pnl']
            curve.append({'trade_num':i+1,'balance':round(bal,2),'date':t.get('closed_at','')[:10]})
        return curve

    def _ss(self, trades, name):
        if not trades: return {'name':name,'trades':0,'win_rate':0,'pnl':0}
        w=sum(1 for t in trades if t['pnl']>0)
        return {'name':name,'trades':len(trades),'wins':w,
                'win_rate':round((w/len(trades))*100,1),'pnl':round(sum(t['pnl'] for t in trades),2)}

    def _empty_report(self):
        return {
            'total_trades':0,'win_rate':0,'wins':0,'losses':0,'total_pnl':0,
            'gross_profit':0,'gross_loss':0,'avg_win':0,'avg_loss':0,
            'largest_win':0,'largest_loss':0,'profit_factor':0,'expectancy':0,
            'sharpe_ratio':0,'max_drawdown':0,'max_drawdown_pct':0,
            'max_win_streak':0,'max_loss_streak':0,'current_streak':0,'streak_type':'',
            'monthly':[],'weekly':[],'spread_stats':{'name':'Credit Spreads','trades':0,'win_rate':0,'pnl':0},
            'directional_stats':{'name':'Directional','trades':0,'win_rate':0,'pnl':0},
            'setup_stats':{},'top_symbols':[],'bottom_symbols':[],'equity_curve':[],'recent_trades':[],
            'first_trade_date':'','days_trading':0,
        }
