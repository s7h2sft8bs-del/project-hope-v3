"""
PROJECT HOPE v3.0 - Persistent Storage
Saves all trade data, analytics, and state to disk
Auto-saves every 30 seconds, auto-loads on startup
Nothing is lost on restart
"""
import json
import os
import time
import threading
from datetime import datetime
from copy import deepcopy

# Storage location - use Render persistent disk if available, else local
STORAGE_DIR = os.environ.get('STORAGE_PATH', '/opt/render/project/data')
if not os.path.exists(STORAGE_DIR):
    try:
        os.makedirs(STORAGE_DIR, exist_ok=True)
    except:
        STORAGE_DIR = '/tmp/project-hope-data'
        os.makedirs(STORAGE_DIR, exist_ok=True)

STATE_FILE = os.path.join(STORAGE_DIR, 'engine_state.json')
TRADES_FILE = os.path.join(STORAGE_DIR, 'trade_history.json')
ANALYTICS_FILE = os.path.join(STORAGE_DIR, 'analytics_data.json')
BACKTEST_FILE = os.path.join(STORAGE_DIR, 'backtest_results.json')
DAILY_LOG_FILE = os.path.join(STORAGE_DIR, 'daily_log.json')
AGREEMENTS_FILE = os.path.join(STORAGE_DIR, 'user_agreements.json')


class Storage:
    def __init__(self):
        self._lock = threading.Lock()
        self._save_count = 0
        print(f"[STORAGE] Using directory: {STORAGE_DIR}")

    # ========== SAVE FUNCTIONS ==========

    def save_state(self, state):
        """Save current engine state (positions, P&L, counters)"""
        try:
            data = {
                'saved_at': datetime.now().isoformat(),
                'autopilot': state.get('autopilot', False),
                'credit_spreads': state.get('credit_spreads', []),
                'directional_trades': state.get('directional_trades', []),
                'wins': state.get('wins', 0),
                'losses': state.get('losses', 0),
                'consecutive_losses': state.get('consecutive_losses', 0),
                'total_pnl': state.get('total_pnl', 0),
                'daily_pnl': state.get('daily_pnl', 0),
                'cs_trades_today': state.get('cs_trades_today', 0),
                'dir_trades_today': state.get('dir_trades_today', 0),
                'today': state.get('today', ''),
            }
            self._write(STATE_FILE, data)
        except Exception as e:
            print(f"[STORAGE ERROR] save_state: {e}")

    def save_trade(self, trade_data):
        """Append a completed trade to permanent history"""
        try:
            history = self._read(TRADES_FILE) or []
            trade_data['saved_at'] = datetime.now().isoformat()
            history.append(trade_data)
            self._write(TRADES_FILE, history)
            self._save_count += 1
            print(f"[STORAGE] Trade #{len(history)} saved: {trade_data.get('symbol','')} {trade_data.get('pnl','')}")
        except Exception as e:
            print(f"[STORAGE ERROR] save_trade: {e}")

    def save_analytics(self, analytics_data):
        """Save analytics snapshot"""
        try:
            data = {'saved_at': datetime.now().isoformat(), **analytics_data}
            self._write(ANALYTICS_FILE, data)
        except Exception as e:
            print(f"[STORAGE ERROR] save_analytics: {e}")

    def save_backtest(self, results):
        """Save backtest results"""
        try:
            all_results = self._read(BACKTEST_FILE) or []
            results['saved_at'] = datetime.now().isoformat()
            all_results.append(results)
            # Keep last 20 backtests
            if len(all_results) > 20:
                all_results = all_results[-20:]
            self._write(BACKTEST_FILE, all_results)
        except Exception as e:
            print(f"[STORAGE ERROR] save_backtest: {e}")

    def save_daily_log(self, date_str, log_entry):
        """Save daily summary log"""
        try:
            logs = self._read(DAILY_LOG_FILE) or {}
            if date_str not in logs:
                logs[date_str] = {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0, 'entries': []}
            logs[date_str]['entries'].append(log_entry)
            self._write(DAILY_LOG_FILE, logs)
        except Exception as e:
            print(f"[STORAGE ERROR] save_daily_log: {e}")

    def update_daily_summary(self, date_str, trades, wins, losses, pnl):
        """Update daily summary stats"""
        try:
            logs = self._read(DAILY_LOG_FILE) or {}
            if date_str not in logs:
                logs[date_str] = {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0, 'entries': []}
            logs[date_str]['trades'] = trades
            logs[date_str]['wins'] = wins
            logs[date_str]['losses'] = losses
            logs[date_str]['pnl'] = round(pnl, 2)
            self._write(DAILY_LOG_FILE, logs)
        except Exception as e:
            print(f"[STORAGE ERROR] update_daily: {e}")

    # ========== LOAD FUNCTIONS ==========

    def load_state(self):
        """Load saved engine state"""
        try:
            data = self._read(STATE_FILE)
            if data:
                print(f"[STORAGE] State loaded from {data.get('saved_at', 'unknown')}")
                return data
            print("[STORAGE] No saved state found - starting fresh")
            return None
        except Exception as e:
            print(f"[STORAGE ERROR] load_state: {e}")
            return None

    def load_trade_history(self):
        """Load all trade history"""
        try:
            history = self._read(TRADES_FILE) or []
            print(f"[STORAGE] Loaded {len(history)} historical trades")
            return history
        except Exception as e:
            print(f"[STORAGE ERROR] load_history: {e}")
            return []

    def load_backtests(self):
        """Load saved backtest results"""
        try:
            return self._read(BACKTEST_FILE) or []
        except:
            return []

    def load_daily_logs(self):
        """Load all daily logs"""
        try:
            return self._read(DAILY_LOG_FILE) or {}
        except:
            return {}

    # ========== STATS ==========

    def get_storage_stats(self):
        """Get storage status info"""
        try:
            history = self._read(TRADES_FILE) or []
            logs = self._read(DAILY_LOG_FILE) or {}
            backtests = self._read(BACKTEST_FILE) or []
            state_exists = os.path.exists(STATE_FILE)
            return {
                'storage_dir': STORAGE_DIR,
                'total_trades_saved': len(history),
                'total_days_logged': len(logs),
                'total_backtests': len(backtests),
                'state_saved': state_exists,
                'state_file_size': os.path.getsize(STATE_FILE) if state_exists else 0,
                'trades_file_size': os.path.getsize(TRADES_FILE) if os.path.exists(TRADES_FILE) else 0,
                'save_count_this_session': self._save_count,
            }
        except:
            return {'storage_dir': STORAGE_DIR, 'error': 'Could not read stats'}


    def save_agreement(self, data):
        try:
            records = self._read(AGREEMENTS_FILE) or []
            data['saved_at'] = datetime.now().isoformat()
            records.append(data)
            self._write(AGREEMENTS_FILE, records)
            print(f'[STORAGE] Agreement saved: {data.get("type","unknown")}')
            return True
        except Exception as e:
            print(f'[STORAGE ERROR] {e}')
            return False

    def load_agreements(self):
        return self._read(AGREEMENTS_FILE) or []

    # ========== INTERNAL ==========

    def _write(self, filepath, data):
        with self._lock:
            # Write to temp file first, then rename (atomic)
            tmp = filepath + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(data, f, default=str)
            os.replace(tmp, filepath)

    def _read(self, filepath):
        with self._lock:
            if not os.path.exists(filepath):
                return None
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"[STORAGE WARNING] Corrupt file: {filepath}")
                return None


class AutoSaver:
    """Background thread that auto-saves engine state every N seconds"""

    def __init__(self, storage, engine, interval=30):
        self.storage = storage
        self.engine = engine
        self.interval = interval
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()
        print(f"[STORAGE] Auto-save started (every {self.interval}s)")

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                self.storage.save_state(self.engine.state)
            except Exception as e:
                print(f"[AUTOSAVE ERROR] {e}")
            time.sleep(self.interval)
