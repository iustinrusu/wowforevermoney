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
    'realm': 'PvP-Horde',           # if your TSM data doesn't have it, the first realm TSM has is used
    'faction': 'H',                 # H or A: which vendors you can use (detected from your characters)
    'gold': 0.0,                    # gold you have available to invest (detected from your characters)
    'level': 1,
    'professions': {},              # your skill levels (detected by the addon); anything not listed is "not learned"
    'preferred': [],                # professions shown first when profits are close, e.g. ['Fishing', 'Cooking']
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
    'fishing_skill_bonus': None,    # None = from your bags, bank and gear; a number overrides (pole + gear + lure)
    'kills_per_hour': 60,           # mobs killed and skinned per hour (your own logged time is never used)
    'herb_nodes_per_hour': 40,      # herb nodes gathered per hour (until the addon measures it)
    'ore_nodes_per_hour': 40,       # ore nodes mined per hour (until the addon measures it)
    # Drop rates come from Wowhead Forever's large samples. Your own catch logs are small, mix pools with open
    # water and can be incomplete, so they're only used for your pace and got-away rate unless you turn this on.
    'own_logs_for_rates': False,
    # Sale price on the AH: 'min_buyout' = the current lowest buyout, what you'd list at (the user's choice);
    # 'actual_sales' = never above what the item actually sells for (more conservative).
    'sale_price_basis': 'min_buyout',
    # Pools (Floating Wreckage/Debris, schools) have to be found first, so gold/hour counts open water only;
    # pool loot (trunks, Stranglekelp, Rumsey Rum) is shown as a bonus unless you turn this on.
    'fishing_pools': False,
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
