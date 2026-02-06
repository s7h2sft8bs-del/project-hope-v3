"""
PROJECT HOPE v3.0 - Trade Journal
Persistent trade journal with notes, tags, and lessons learned
"""
from datetime import datetime

class TradeJournal:
    def __init__(self, storage):
        self.storage = storage
        self.entries = []
        self._load()

    def _load(self):
        """Load journal from storage"""
        try:
            data = self.storage._read(self.storage.STORAGE_DIR + '/journal.json')
            if data:
                self.entries = data
                print(f"[JOURNAL] Loaded {len(self.entries)} entries")
        except:
            self.entries = []

    def _save(self):
        """Save journal to storage"""
        try:
            self.storage._write(self.storage.STORAGE_DIR + '/journal.json', self.entries)
        except Exception as e:
            print(f"[JOURNAL ERR] Save: {e}")

    def add_entry(self, data):
        """Add a journal entry"""
        entry = {
            'id': len(self.entries) + 1,
            'date': data.get('date', datetime.now().strftime('%Y-%m-%d')),
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': data.get('type', 'note'),  # trade, note, lesson, review
            'symbol': data.get('symbol', ''),
            'direction': data.get('direction', ''),
            'setup': data.get('setup', ''),
            'entry_reason': data.get('entry_reason', ''),
            'exit_reason': data.get('exit_reason', ''),
            'pnl': data.get('pnl', 0),
            'notes': data.get('notes', ''),
            'lesson': data.get('lesson', ''),
            'emotion': data.get('emotion', 'neutral'),  # confident, fearful, greedy, neutral, frustrated
            'tags': data.get('tags', []),
            'rating': data.get('rating', 0),  # 1-5 self-grade
            'market_context': data.get('market_context', ''),
            'screenshot_note': data.get('screenshot_note', ''),
        }
        self.entries.append(entry)
        self._save()
        return entry

    def add_auto_entry(self, trade_data, close_reason):
        """Auto-create journal entry when a trade closes"""
        entry = {
            'id': len(self.entries) + 1,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': 'trade',
            'symbol': trade_data.get('symbol', ''),
            'direction': trade_data.get('direction', ''),
            'setup': trade_data.get('setup_type', trade_data.get('type', '')),
            'entry_reason': 'Autopilot entry',
            'exit_reason': close_reason,
            'pnl': trade_data.get('pnl', 0),
            'notes': f"Auto-closed: {close_reason}",
            'lesson': '',
            'emotion': 'neutral',
            'tags': ['autopilot'],
            'rating': 0,
            'market_context': '',
            'needs_review': True,  # Flag for user to add notes later
        }
        self.entries.append(entry)
        self._save()
        return entry

    def update_entry(self, entry_id, updates):
        """Update an existing journal entry"""
        for entry in self.entries:
            if entry.get('id') == entry_id:
                entry.update(updates)
                entry['updated_at'] = datetime.now().isoformat()
                self._save()
                return entry
        return None

    def get_entries(self, limit=50, entry_type=None, symbol=None):
        """Get journal entries with optional filters"""
        filtered = self.entries
        if entry_type:
            filtered = [e for e in filtered if e.get('type') == entry_type]
        if symbol:
            filtered = [e for e in filtered if e.get('symbol', '').upper() == symbol.upper()]
        return list(reversed(filtered[-limit:]))

    def get_needs_review(self):
        """Get entries that need user review/notes"""
        return [e for e in self.entries if e.get('needs_review')]

    def get_stats(self):
        """Get journal statistics"""
        total = len(self.entries)
        trades = [e for e in self.entries if e.get('type') == 'trade']
        lessons = [e for e in self.entries if e.get('type') == 'lesson']
        needs_review = len(self.get_needs_review())
        
        # Emotion breakdown
        emotions = {}
        for e in trades:
            em = e.get('emotion', 'neutral')
            emotions[em] = emotions.get(em, 0) + 1

        # Best/worst rated trades
        rated = [e for e in trades if e.get('rating', 0) > 0]
        
        return {
            'total_entries': total,
            'trade_entries': len(trades),
            'lesson_entries': len(lessons),
            'needs_review': needs_review,
            'emotions': emotions,
            'avg_rating': round(sum(e['rating'] for e in rated) / len(rated), 1) if rated else 0,
        }

    def get_data(self):
        """Full journal data for dashboard"""
        return {
            'entries': self.get_entries(50),
            'stats': self.get_stats(),
            'needs_review': self.get_needs_review()[:10],
        }
