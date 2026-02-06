"""
PROJECT HOPE v3.0 - Economic Calendar
Major market-moving events: Fed meetings, CPI, Jobs, GDP
Auto-blocks aggressive trading during high-impact events
"""
from datetime import datetime, timedelta

# 2025-2026 Major Economic Events (pre-loaded, update periodically)
ECONOMIC_EVENTS = [
    # 2025 FOMC Meetings
    {'date':'2025-01-29','event':'FOMC Decision','impact':'HIGH','category':'fed'},
    {'date':'2025-03-19','event':'FOMC Decision + Dot Plot','impact':'HIGH','category':'fed'},
    {'date':'2025-05-07','event':'FOMC Decision','impact':'HIGH','category':'fed'},
    {'date':'2025-06-18','event':'FOMC Decision + Dot Plot','impact':'HIGH','category':'fed'},
    {'date':'2025-07-30','event':'FOMC Decision','impact':'HIGH','category':'fed'},
    {'date':'2025-09-17','event':'FOMC Decision + Dot Plot','impact':'HIGH','category':'fed'},
    {'date':'2025-10-29','event':'FOMC Decision','impact':'HIGH','category':'fed'},
    {'date':'2025-12-17','event':'FOMC Decision + Dot Plot','impact':'HIGH','category':'fed'},
    # 2026 FOMC (estimated)
    {'date':'2026-01-28','event':'FOMC Decision','impact':'HIGH','category':'fed'},
    {'date':'2026-03-18','event':'FOMC Decision + Dot Plot','impact':'HIGH','category':'fed'},
    {'date':'2026-05-06','event':'FOMC Decision','impact':'HIGH','category':'fed'},
    {'date':'2026-06-17','event':'FOMC Decision + Dot Plot','impact':'HIGH','category':'fed'},
    # 2025 CPI Reports (typically 2nd week of month)
    {'date':'2025-01-15','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-02-12','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-03-12','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-04-10','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-05-13','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-06-11','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-07-11','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-08-12','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-09-10','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-10-14','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-11-12','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2025-12-10','event':'CPI Report','impact':'HIGH','category':'inflation'},
    # 2026 CPI
    {'date':'2026-01-14','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2026-02-11','event':'CPI Report','impact':'HIGH','category':'inflation'},
    {'date':'2026-03-11','event':'CPI Report','impact':'HIGH','category':'inflation'},
    # 2025 Jobs Reports (first Friday of month)
    {'date':'2025-01-10','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-02-07','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-03-07','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-04-04','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-05-02','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-06-06','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-07-03','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-08-01','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-09-05','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-10-03','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-11-07','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2025-12-05','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    # 2026 Jobs
    {'date':'2026-01-09','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2026-02-06','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    {'date':'2026-03-06','event':'Non-Farm Payrolls','impact':'HIGH','category':'jobs'},
    # GDP Reports (quarterly)
    {'date':'2025-01-30','event':'GDP Q4 Advance','impact':'MEDIUM','category':'gdp'},
    {'date':'2025-03-27','event':'GDP Q4 Final','impact':'MEDIUM','category':'gdp'},
    {'date':'2025-04-30','event':'GDP Q1 Advance','impact':'MEDIUM','category':'gdp'},
    {'date':'2025-06-26','event':'GDP Q1 Final','impact':'MEDIUM','category':'gdp'},
    {'date':'2025-07-30','event':'GDP Q2 Advance','impact':'MEDIUM','category':'gdp'},
    {'date':'2025-10-30','event':'GDP Q3 Advance','impact':'MEDIUM','category':'gdp'},
    # Options Expiration (Triple/Quad Witching)
    {'date':'2025-01-17','event':'Monthly OpEx','impact':'MEDIUM','category':'opex'},
    {'date':'2025-02-21','event':'Monthly OpEx','impact':'MEDIUM','category':'opex'},
    {'date':'2025-03-21','event':'Quad Witching','impact':'HIGH','category':'opex'},
    {'date':'2025-04-17','event':'Monthly OpEx','impact':'MEDIUM','category':'opex'},
    {'date':'2025-06-20','event':'Quad Witching','impact':'HIGH','category':'opex'},
    {'date':'2025-09-19','event':'Quad Witching','impact':'HIGH','category':'opex'},
    {'date':'2025-12-19','event':'Quad Witching','impact':'HIGH','category':'opex'},
    # Market Holidays (no trading)
    {'date':'2025-01-20','event':'MLK Day - Market Closed','impact':'INFO','category':'holiday'},
    {'date':'2025-02-17','event':'Presidents Day - Market Closed','impact':'INFO','category':'holiday'},
    {'date':'2025-04-18','event':'Good Friday - Market Closed','impact':'INFO','category':'holiday'},
    {'date':'2025-05-26','event':'Memorial Day - Market Closed','impact':'INFO','category':'holiday'},
    {'date':'2025-06-19','event':'Juneteenth - Market Closed','impact':'INFO','category':'holiday'},
    {'date':'2025-07-04','event':'Independence Day - Market Closed','impact':'INFO','category':'holiday'},
    {'date':'2025-09-01','event':'Labor Day - Market Closed','impact':'INFO','category':'holiday'},
    {'date':'2025-11-27','event':'Thanksgiving - Market Closed','impact':'INFO','category':'holiday'},
    {'date':'2025-12-25','event':'Christmas - Market Closed','impact':'INFO','category':'holiday'},
]

class EconomicCalendar:
    def __init__(self):
        self.events = ECONOMIC_EVENTS
        self.custom_events = []

    def get_upcoming(self, days_ahead=14):
        """Get upcoming economic events"""
        today = datetime.now().date()
        end = today + timedelta(days=days_ahead)
        upcoming = []
        
        all_events = self.events + self.custom_events
        for event in all_events:
            try:
                ed = datetime.strptime(event['date'], '%Y-%m-%d').date()
                if today <= ed <= end:
                    days_until = (ed - today).days
                    upcoming.append({**event, 'days_until': days_until})
            except: continue
        
        upcoming.sort(key=lambda x: x['date'])
        return upcoming

    def get_today_events(self):
        """Get events happening today"""
        today = datetime.now().strftime('%Y-%m-%d')
        return [e for e in (self.events + self.custom_events) if e['date'] == today]

    def is_high_impact_day(self):
        """Check if today has high-impact events (reduce position sizing)"""
        today_events = self.get_today_events()
        high = [e for e in today_events if e.get('impact') == 'HIGH']
        return len(high) > 0, high

    def is_market_holiday(self):
        """Check if today is a market holiday"""
        today_events = self.get_today_events()
        holidays = [e for e in today_events if e.get('category') == 'holiday']
        return len(holidays) > 0

    def add_custom_event(self, date_str, event_name, impact='MEDIUM', category='custom'):
        """Add a custom event"""
        self.custom_events.append({
            'date': date_str,
            'event': event_name,
            'impact': impact,
            'category': category,
        })

    def get_data(self):
        """Full calendar data for dashboard"""
        upcoming = self.get_upcoming(30)
        is_high, high_events = self.is_high_impact_day()
        return {
            'upcoming': upcoming,
            'today_events': self.get_today_events(),
            'is_high_impact_today': is_high,
            'high_impact_events': [e['event'] for e in high_events],
            'next_fomc': self._next_event('fed'),
            'next_cpi': self._next_event('inflation'),
            'next_jobs': self._next_event('jobs'),
            'next_opex': self._next_event('opex'),
        }

    def _next_event(self, category):
        """Get next event of a specific category"""
        today = datetime.now().date()
        for e in sorted(self.events + self.custom_events, key=lambda x: x['date']):
            try:
                ed = datetime.strptime(e['date'], '%Y-%m-%d').date()
                if ed >= today and e.get('category') == category:
                    return {'event': e['event'], 'date': e['date'], 'days_until': (ed - today).days}
            except: continue
        return None
