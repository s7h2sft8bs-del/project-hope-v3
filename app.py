"""PROJECT HOPE v3.0 FINAL - Web Server"""
from flask import Flask, send_file, jsonify, request, Response
from engine import TradingEngine
import threading, os

app = Flask(__name__)
engine = TradingEngine()
engine.start()

@app.route('/')
def landing(): return send_file('landing.html')

@app.route('/legal')
def legal(): return send_file('legal.html')

@app.route('/pre-trade')
def pre_trade(): return send_file('pre-trade.html')

@app.route('/dashboard')
def dashboard_page(): return send_file('index.html')

@app.route('/api/dashboard')
def dashboard(): return jsonify(engine.get_dashboard_data())

@app.route('/api/autopilot', methods=['POST'])
def toggle_ap(): return jsonify({'autopilot': engine.toggle_autopilot()})

@app.route('/api/overnight', methods=['POST'])
def toggle_overnight(): return jsonify({'overnight_hold': engine.toggle_overnight()})

@app.route('/api/theme', methods=['POST'])
def set_theme():
    d = request.json or {}
    engine.set_theme(d.get('theme', 'dark'))
    return jsonify({'theme': engine.state['theme']})

@app.route('/api/close', methods=['POST'])
def close_pos():
    d = request.json or {}
    r = engine.position_manager.manual_close_position(d.get('trade_id'), d.get('trade_type','directional'))
    engine.storage.save_state(engine.state)
    return jsonify({'success': r})

@app.route('/api/override', methods=['POST'])
def toggle_ovr():
    d = request.json or {}
    r = engine.position_manager.toggle_manual_override(d.get('trade_id'), d.get('trade_type','directional'))
    return jsonify({'manual_override': r})

@app.route('/api/close-all', methods=['POST'])
def close_all():
    c = 0
    for s in engine.state['credit_spreads']:
        if s['status'] == 'open': engine.position_manager.manual_close_position(s['order_id'],'spread'); c += 1
    for t in engine.state['directional_trades']:
        if t['status'] == 'open': engine.position_manager.manual_close_position(t['order_id'],'directional'); c += 1
    engine.storage.save_state(engine.state)
    return jsonify({'closed': c})

@app.route('/api/reset-breaker', methods=['POST'])
def reset_breaker():
    engine.state['consecutive_losses'] = 0
    engine._log('system', 'Loss breaker reset')
    return jsonify({'success': True})

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    d = request.json or {}
    symbol = d.get('symbol', 'SPY')
    days = min(d.get('days', 365), 730)
    if engine.state.get('backtest_running'): return jsonify({'error': 'Already running'})
    threading.Thread(target=engine.run_backtest, args=(symbol, days), daemon=True).start()
    return jsonify({'status': 'started', 'symbol': symbol, 'days': days})

@app.route('/api/backtest/results')
def backtest_results():
    return jsonify({'results': engine.state.get('backtest_results'), 'running': engine.state.get('backtest_running', False)})

@app.route('/api/screener')
def screener_data(): return jsonify(engine.state.get('screener_results', {}))

@app.route('/api/analytics')
def analytics_data(): return jsonify(engine.analytics.get_full_report())

@app.route('/api/greeks')
def greeks_data(): return jsonify(engine.state.get('portfolio_greeks', {}))

@app.route('/api/storage')
def storage_stats(): return jsonify(engine.storage.get_storage_stats())

@app.route('/api/storage/save', methods=['POST'])
def force_save():
    engine.storage.save_state(engine.state)
    return jsonify({'saved': True})

@app.route('/api/trade-history')
def trade_history():
    h = engine.storage.load_trade_history()
    return jsonify({'total': len(h), 'trades': h[-100:]})

@app.route('/api/daily-logs')
def daily_logs(): return jsonify(engine.storage.load_daily_logs())

# === NEW ENDPOINTS ===

@app.route('/api/earnings')
def earnings_data(): return jsonify(engine.earnings.get_data())

@app.route('/api/earnings/add', methods=['POST'])
def add_earnings():
    d = request.json or {}
    engine.earnings.add_manual_earnings(d.get('symbol',''), d.get('date',''), d.get('timing',''))
    return jsonify({'success': True})

@app.route('/api/iv-rank')
def iv_rank_data(): return jsonify(engine.iv_rank.get_data())

@app.route('/api/iv-rank/top')
def iv_rank_top(): return jsonify(engine.iv_rank.get_top_iv_symbols(20))

@app.route('/api/risk')
def risk_data(): return jsonify(engine.risk.stress_test(engine.state))

@app.route('/api/risk/correlations')
def correlations():
    open_syms = [s['symbol'] for s in engine.state['credit_spreads'] if s['status'] in ['open','pending']]
    open_syms += [t['symbol'] for t in engine.state['directional_trades'] if t['status'] in ['open','pending']]
    if not open_syms: open_syms = ['SPY','QQQ','AAPL','MSFT','NVDA']
    return jsonify(engine.risk.calculate_correlations(list(set(open_syms))))

@app.route('/api/risk/heatmap')
def heatmap(): return jsonify(engine.risk.get_sector_heatmap())

@app.route('/api/journal')
def journal_data(): return jsonify(engine.journal.get_data())

@app.route('/api/journal/add', methods=['POST'])
def journal_add():
    d = request.json or {}
    entry = engine.journal.add_entry(d)
    return jsonify(entry)

@app.route('/api/journal/update', methods=['POST'])
def journal_update():
    d = request.json or {}
    entry = engine.journal.update_entry(d.get('id'), d)
    return jsonify(entry or {'error': 'Not found'})

@app.route('/api/calendar')
def calendar_data(): return jsonify(engine.econ_cal.get_data())

@app.route('/api/export/csv')
def export_csv():
    csv_data = engine.export_trades_csv()
    return Response(csv_data, mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=project_hope_trades.csv'})


@app.route('/api/agreement', methods=['POST'])
def save_agreement():
    d = request.json or {}
    d['ip'] = request.remote_addr
    success = engine.storage.save_agreement(d)
    return jsonify({'saved': success})

@app.route('/api/agreements')
def list_agreements():
    records = engine.storage.load_agreements()
    q = request.args.get('search','').lower()
    if q:
        records = [r for r in records if q in r.get('name','').lower() or q in r.get('email','').lower() or q in r.get('ip','').lower()]
    return jsonify({'total': len(records), 'records': records})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
