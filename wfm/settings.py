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
    # Levelling planner: the AH takes this many days of your share of a product's sales; the rest go to a vendor or
    # disenchanting (the user, 2026-11-19: slow sellers must not drive the route; it was a week until then)
    'levelling_ah_days': 2.0,
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
    # Key that unlocks the shared Wowhead Forever data (data/wowhead_forever.pack): from the app's author. Local only.
    'data_key': '',
    # Pull the latest version from GitHub when the app starts (git installs only; fast-forward only, never overwrites).
    'auto_update': True,
    # Sale price on the AH: 'lower' = the lower of the current lowest buyout and the usual sale price, what you can
    # count on (the user's choice, 2026-11-14); 'min_buyout' = the current lowest buyout, what you'd list at;
    # 'actual_sales' = never above the realm's listing average or what it actually sells for (most conservative).
    # 'realm' (the user's choice, 2026-11-15) = your realm's lowest listing; region data only says how fast it sells.
    'sale_price_basis': 'realm',
    # Pools (Floating Wreckage/Debris, schools) have to be found first, so gold/hour counts open water only;
    # pool loot (trunks, Stranglekelp, Rumsey Rum) is shown as a bonus unless you turn this on.
    'fishing_pools': False,
    # The page's animations (Night watch look, 2026-11-20): 'system' = off when the system asks for less motion
    # (Windows: Settings > Accessibility > Visual effects > Animation effects), 'on', or 'off'.
    'motion': 'system',
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
