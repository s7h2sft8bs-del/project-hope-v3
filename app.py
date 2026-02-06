"""PROJECT HOPE v3.0 - Web Server"""
from flask import Flask, send_file, jsonify, request
from engine import TradingEngine
import os, threading

app = Flask(__name__)
engine = TradingEngine()
engine.start()

@app.route('/')
def home(): return send_file('index.html')

@app.route('/api/dashboard')
def dashboard(): return jsonify(engine.get_dashboard_data())

@app.route('/api/autopilot', methods=['POST'])
def autopilot(): return jsonify({'autopilot': engine.toggle_autopilot()})

@app.route('/api/close', methods=['POST'])
def close_pos():
    d = request.json or {}
    return jsonify({'success': engine.position_manager.manual_close_position(d.get('trade_id'), d.get('trade_type', 'directional'))})

@app.route('/api/override', methods=['POST'])
def override():
    d = request.json or {}
    return jsonify({'manual_override': engine.position_manager.toggle_manual_override(d.get('trade_id'), d.get('trade_type', 'directional'))})

@app.route('/api/close-all', methods=['POST'])
def close_all():
    c = 0
    for s in engine.state['credit_spreads']:
        if s['status'] == 'open': engine.position_manager.manual_close_position(s['order_id'], 'spread'); c += 1
    for t in engine.state['directional_trades']:
        if t['status'] == 'open': engine.position_manager.manual_close_position(t['order_id'], 'directional'); c += 1
    return jsonify({'closed': c})

@app.route('/api/reset-breaker', methods=['POST'])
def reset():
    engine.state['consecutive_losses'] = 0
    return jsonify({'success': True})

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    d = request.json or {}
    symbols = d.get('symbols', ['SPY','QQQ','AAPL','MSFT','AMZN','NVDA','AMD','TSLA','META','GOOGL','NFLX','BA','JPM','XOM','GS'])
    days = d.get('days', 365)
    def _run(): engine.backtest_results = engine.run_backtest(symbols, days)
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'status': 'running', 'symbols': len(symbols), 'days': days})

@app.route('/api/backtest/results')
def backtest_results():
    if engine.backtest_results: return jsonify(engine.backtest_results)
    return jsonify({'status': 'no results yet'})

@app.route('/api/greeks')
def greeks(): return jsonify(engine.greeks.get_data())

@app.route('/api/analytics')
def analytics(): return jsonify(engine.analytics.get_full_analytics())

@app.route('/api/screener')
def screener(): return jsonify(engine.screener.get_scan_data())

@app.route('/api/screener/scan', methods=['POST'])
def run_scan(): return jsonify(engine.screener.full_scan())

@app.route('/api/probability', methods=['POST'])
def probability():
    d = request.json or {}
    return jsonify({'probability_otm': engine.screener.probability_calculator(d.get('price',0), d.get('strike',0), d.get('dte',30), d.get('iv',30))})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
