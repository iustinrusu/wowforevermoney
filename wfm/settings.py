"""User settings, stored in data/settings.json. Every number the engine assumes lives here."""
from __future__ import annotations

import json
import threading
from copy import deepcopy

from .paths import DATA

DEFAULTS = {
    'auto_detect': True,            # fill level, gold, faction, professions from your saved addon data
    'character': None,              # None = the character you played last
    'gold_scope': 'faction',        # 'faction' = all your characters' gold on this faction, 'character' = just one
    'realm': 'PvP-Horde',
    'faction': 'H',                 # H or A: which vendors you can use
    'gold': 1.0,                    # gold you have available to invest
    'level': 42,
    'professions': {                # your skill levels; anything not listed is "not learned"
        'First Aid': 225, 'Cooking': 225, 'Fishing': 225, 'Skinning': 270, 'Leatherworking': 161,
    },
    'preferred': ['Fishing', 'Cooking', 'First Aid'],   # shown first when profits are close
    'switch_bonus': 1.5,            # other professions must earn this many times more to be recommended
    'ah_cut': 0.05,                 # auction house cut on sales
    'market_share': 0.2,            # share of the region's daily sales you can expect to capture
    'min_sold_per_day': 0.5,        # hide items selling less than this (region, TSM-tracked)
    'show_other_professions': True,
    'include_unverified_recipes': False,
    'farm_rates': {},               # item id -> units you gather per hour (enables gold/hour)
    'watchlist': [],                # item ids to always alert on
    'alerts': {'enabled': True, 'min_daily_profit_gold': 5.0, 'desktop': True},
    'stale_hours': {'realm': 3, 'region': 36},
    'casts_per_hour': 240,
}


class Settings:
    def __init__(self):
        self._lock = threading.Lock()
        self.path = DATA / 'settings.json'
        self.data = deepcopy(DEFAULTS)
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding='utf-8'))
                self._merge(self.data, saved)
            except (ValueError, OSError):
                pass

    @staticmethod
    def _merge(base: dict, new: dict):
        for k, v in new.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict) and k not in ('professions', 'farm_rates'):
                Settings._merge(base[k], v)
            else:
                base[k] = v

    def update(self, changes: dict) -> dict:
        with self._lock:
            self._merge(self.data, changes)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
            return deepcopy(self.data)

    def snapshot(self) -> dict:
        with self._lock:
            return deepcopy(self.data)
