"""PROJECT HOPE v3.0 - Web Server with Persistent Storage"""
from flask import Flask, send_file, jsonify, request
from engine import TradingEngine
import threading, os

app = Flask(__name__)
engine = TradingEngine()
engine.start()

@app.route('/')
def home(): return send_file('index.html')

@app.route('/api/dashboard')
def dashboard(): return jsonify(engine.get_dashboard_data())

@app.route('/api/autopilot', methods=['POST'])
def toggle_ap(): return jsonify({'autopilot': engine.toggle_autopilot()})

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
    engine._log('system', 'Loss breaker reset'); return jsonify({'success': True})

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    d = request.json or {}
    symbol = d.get('symbol', 'SPY')
    days = min(d.get('days', 365), 730)
    if engine.state.get('backtest_running'): return jsonify({'error': 'Backtest already running'})
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
    engine.storage.save_analytics(engine.analytics.get_full_report())
    return jsonify({'saved': True, 'stats': engine.storage.get_storage_stats()})

@app.route('/api/trade-history')
def trade_history():
    h = engine.storage.load_trade_history()
    return jsonify({'total': len(h), 'trades': h[-100:]})

@app.route('/api/daily-logs')
def daily_logs(): return jsonify(engine.storage.load_daily_logs())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
