"""
PROJECT HOPE v3.0 - Configuration
Built by Stephen Martinez | Lancaster, PA
TIER 2 BUILD - 150+ Watchlist, Backtesting, Greeks, Analytics
"""
import os

# ============ BROKER ============
TRADIER_API_KEY = os.environ.get('TRADIER_API_KEY', '')
TRADIER_ACCOUNT_ID = os.environ.get('TRADIER_ACCOUNT_ID', '')
TRADIER_BASE_URL = os.environ.get('TRADIER_BASE_URL', 'https://sandbox.tradier.com')

# ============ TWILIO ============
TWILIO_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE = os.environ.get('TWILIO_PHONE_NUMBER', '')
MY_PHONE = os.environ.get('MY_PHONE_NUMBER', '')

# ============ ACCOUNT ============
VIRTUAL_ACCOUNT_SIZE = 6000
CREDIT_SPREAD_ALLOCATION = 0.80
DIRECTIONAL_ALLOCATION = 0.20

# ============ CREDIT SPREAD SETTINGS ============
CS_MAX_OPEN = 8
CS_MAX_NEW_PER_DAY = 3
CS_SPREAD_WIDTH = 5
CS_MIN_CREDIT = 0.80
CS_MAX_CREDIT = 2.50
CS_MIN_DTE = 28
CS_MAX_DTE = 45
CS_TARGET_DELTA = 0.30
CS_TAKE_PROFIT_PCT = 50
CS_STOP_LOSS_PCT = 200
CS_CLOSE_DTE = 21
CS_EMERGENCY_DTE = 7
CS_CONTRACTS = 1

# ============ DIRECTIONAL SETTINGS ============
DIR_MAX_OPEN = 3
DIR_MAX_NEW_PER_DAY = 2
DIR_MAX_CONTRACTS = 5
DIR_TP1_PCT = 15
DIR_TP1_SELL_PCT = 50
DIR_TP2_PCT = 25
DIR_TP2_SELL_PCT = 25
DIR_TP3_PCT = 30
DIR_STOP_LOSS_PCT = 15
DIR_COOLDOWN_SECONDS = 120

# ============ 150+ WATCHLIST BY SECTOR ============
WATCHLIST_BY_SECTOR = {
    'Tech': ['AAPL','MSFT','GOOGL','META','NVDA','CRM','ADBE','ORCL','CSCO','NOW','SHOP','PLTR','SNOW','NET','DDOG','CRWD','PANW','ZS','FTNT','DELL','IBM','ANET'],
    'Semiconductor': ['AMD','INTC','QCOM','MU','AVGO','MRVL','ARM','SMCI','TXN','KLAC','LRCX','ASML'],
    'Finance': ['JPM','BAC','WFC','GS','MS','C','AXP','V','MA','PYPL','SQ','COF','SCHW','BLK','USB','PNC'],
    'Healthcare': ['UNH','JNJ','PFE','ABBV','MRK','LLY','BMY','AMGN','GILD','ISRG','MRNA','TMO','ABT','CVS','CI','DXCM'],
    'Consumer': ['AMZN','TSLA','HD','LOW','NKE','SBUX','MCD','TGT','COST','WMT','DIS','NFLX','BKNG','CMG','LULU','TJX','KO','PEP','PG','CL','PM','MO'],
    'Energy': ['XOM','CVX','COP','SLB','OXY','DVN','EOG','MPC','PSX','VLO','HAL','FANG'],
    'Travel': ['DAL','UAL','AAL','LUV','CCL','ABNB','UBER','LYFT','MAR'],
    'Media': ['ROKU','SPOT','SNAP','PINS','RBLX'],
    'Industrial': ['BA','CAT','DE','GE','HON','UPS','FDX','LMT','RTX','NOC','GD','WM'],
    'Crypto': ['COIN','MARA','RIOT','MSTR'],
    'China': ['BABA','JD','NIO','XPEV','PDD'],
    'Telecom': ['T','VZ','CMCSA','TMUS'],
    'ETF': ['SPY','QQQ','IWM','DIA','XLF','XLE','XLK','XLV','XLI','XLP','XLY','ARKK','GLD','SLV','TLT','HYG','EEM','SOXL','TQQQ'],
    'Meme': ['GME','AMC','SOFI','HOOD'],
}

# Flat list (deduplicated)
WATCHLIST = list(dict.fromkeys(s for syms in WATCHLIST_BY_SECTOR.values() for s in syms))

# Reverse lookup
SECTOR_MAP = {}
for sector, syms in WATCHLIST_BY_SECTOR.items():
    for s in syms:
        SECTOR_MAP[s] = sector

# ============ PROTECTIONS ============
MAX_DAILY_LOSS = -300
MAX_PORTFOLIO_DELTA = 50
EARNINGS_BLACKOUT_DAYS = 3
VIX_HIGH_THRESHOLD = 30
VIX_LOW_THRESHOLD = 15
MAX_SAME_SECTOR = 3

# ============ SCAN INTERVALS ============
POSITION_CHECK_INTERVAL = 5
SPREAD_SCAN_INTERVAL = 30
DIRECTIONAL_SCAN_INTERVAL = 15
ACCOUNT_REFRESH_INTERVAL = 10

# ============ BACKTESTING ============
BACKTEST_INITIAL_BALANCE = 6000

# ============ GREEKS THRESHOLDS ============
GREEKS_DELTA_WARNING = 0.40
GREEKS_THETA_TARGET = 5.0
GREEKS_IV_RANK_MIN = 20
GREEKS_IV_RANK_MAX = 80
