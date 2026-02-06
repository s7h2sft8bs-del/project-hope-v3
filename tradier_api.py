"""
PROJECT HOPE v3.0 - Tradier API Wrapper
"""
import requests
from datetime import datetime, timedelta
import config

class TradierAPI:
    def __init__(self):
        self.api_key = config.TRADIER_API_KEY
        self.account_id = config.TRADIER_ACCOUNT_ID
        self.base_url = config.TRADIER_BASE_URL
        self.headers = {'Authorization': f'Bearer {self.api_key}', 'Accept': 'application/json'}

    def _get(self, endpoint, params=None):
        try:
            r = requests.get(f"{self.base_url}{endpoint}", headers=self.headers, params=params, timeout=10)
            return r.json() if r.status_code == 200 else None
        except Exception as e:
            print(f"[API ERROR] {endpoint}: {e}")
            return None

    def _post(self, endpoint, data=None):
        try:
            r = requests.post(f"{self.base_url}{endpoint}", headers=self.headers, data=data, timeout=10)
            return r.json() if r.status_code in [200, 201] else None
        except Exception as e:
            print(f"[API ERROR] {endpoint}: {e}")
            return None

    def get_account_balance(self):
        data = self._get(f'/v1/accounts/{self.account_id}/balances')
        if data and 'balances' in data:
            b = data['balances']
            return {'total_value': b.get('total_equity', 0), 'option_bp': b.get('option_buying_power', 0),
                    'stock_bp': b.get('stock_buying_power', 0), 'cash': b.get('total_cash', 0),
                    'open_pl': b.get('open_pl', 0), 'close_pl': b.get('close_pl', 0)}
        return None

    def get_positions(self):
        data = self._get(f'/v1/accounts/{self.account_id}/positions')
        if data and 'positions' in data:
            pos = data['positions']
            if pos == 'null' or pos is None: return []
            if 'position' in pos:
                p = pos['position']
                return [p] if isinstance(p, dict) else p
        return []

    def get_orders(self):
        data = self._get(f'/v1/accounts/{self.account_id}/orders')
        if data and 'orders' in data:
            orders = data['orders']
            if orders == 'null' or orders is None: return []
            if 'order' in orders:
                o = orders['order']
                return [o] if isinstance(o, dict) else o
        return []

    def get_quote(self, symbol):
        data = self._get('/v1/markets/quotes', {'symbols': symbol})
        if data and 'quotes' in data and 'quote' in data['quotes']:
            q = data['quotes']['quote']
            return q[0] if isinstance(q, list) else q
        return None

    def get_quotes(self, symbols):
        if not symbols: return {}
        data = self._get('/v1/markets/quotes', {'symbols': ','.join(symbols)})
        result = {}
        if data and 'quotes' in data and 'quote' in data['quotes']:
            quotes = data['quotes']['quote']
            if isinstance(quotes, dict): quotes = [quotes]
            for q in quotes: result[q['symbol']] = q
        return result

    def get_option_chain(self, symbol, expiration):
        data = self._get('/v1/markets/options/chains', {'symbol': symbol, 'expiration': expiration, 'greeks': 'true'})
        if data and 'options' in data and 'option' in data['options']:
            o = data['options']['option']
            return [o] if isinstance(o, dict) else o
        return []

    def get_option_expirations(self, symbol):
        data = self._get('/v1/markets/options/expirations', {'symbol': symbol, 'includeAllRoots': 'true'})
        if data and 'expirations' in data and 'date' in data['expirations']:
            d = data['expirations']['date']
            return [d] if isinstance(d, str) else d
        return []

    def buy_option(self, symbol, option_symbol, quantity, limit_price=None):
        data = {'class':'option','symbol':symbol,'option_symbol':option_symbol,
                'side':'buy_to_open','quantity':quantity,'type':'limit' if limit_price else 'market','duration':'day'}
        if limit_price: data['price'] = str(limit_price)
        return self._post(f'/v1/accounts/{self.account_id}/orders', data)

    def sell_option(self, symbol, option_symbol, quantity, limit_price=None):
        data = {'class':'option','symbol':symbol,'option_symbol':option_symbol,
                'side':'sell_to_close','quantity':quantity,'type':'limit' if limit_price else 'market','duration':'day'}
        if limit_price: data['price'] = str(limit_price)
        return self._post(f'/v1/accounts/{self.account_id}/orders', data)

    def place_credit_spread(self, symbol, sell_option, buy_option, quantity, credit_limit):
        data = {'class':'multileg','symbol':symbol,'type':'credit','duration':'day','price':str(credit_limit),
                'side[0]':'sell_to_open','option_symbol[0]':sell_option,'quantity[0]':quantity,
                'side[1]':'buy_to_open','option_symbol[1]':buy_option,'quantity[1]':quantity}
        return self._post(f'/v1/accounts/{self.account_id}/orders', data)

    def close_credit_spread(self, symbol, sell_option, buy_option, quantity, debit_limit):
        data = {'class':'multileg','symbol':symbol,'type':'debit','duration':'day','price':str(debit_limit),
                'side[0]':'buy_to_close','option_symbol[0]':sell_option,'quantity[0]':quantity,
                'side[1]':'sell_to_close','option_symbol[1]':buy_option,'quantity[1]':quantity}
        return self._post(f'/v1/accounts/{self.account_id}/orders', data)

    def get_vix(self):
        q = self.get_quote('VIX')
        return q.get('last', 20) if q else 20

    def find_expiration_in_range(self, symbol, min_dte, max_dte):
        exps = self.get_option_expirations(symbol)
        today = datetime.now().date()
        for exp_str in exps:
            try:
                dte = (datetime.strptime(exp_str, '%Y-%m-%d').date() - today).days
                if min_dte <= dte <= max_dte: return exp_str, dte
            except: continue
        return None, None
