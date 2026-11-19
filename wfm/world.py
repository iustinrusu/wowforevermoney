"""Everything the engine needs, loaded from disk, with a freshness record for every source.

Each source is re-read when its files change (addons update almost daily), and the game tables
are re-downloaded when the installed WoW client build changes.
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import json

from . import classicdb, gamedata, hotfix
from .lua import parse_assignments
from .paths import DATA, GamePaths

WOWHEAD_FISHING = DATA / 'wowhead_forever_fishing.json'
WOWHEAD_CONTAINERS = DATA / 'wowhead_forever_containers.json'
from . import profile as profile_mod
from . import skinning as skinning_mod
from . import datapack as datapack_mod
from . import everloot as everloot_mod
from . import gatherlite as gatherlite_mod
from . import wowhead_items
from .questie import QuestieDB, load_drop_rates, load_questie
from .skillup import SkillUpData, load_skillup
from . import foreverrecipes as foreverrecipes_mod
from .tooltips import TooltipCache
from .tsm import PriceData, parse_appdata


@dataclass
class SourceStatus:
    name: str
    label: str
    status: str = 'missing'       # ok | warn | stale | error | missing
    note: str = ''
    version: str | None = None
    data_time: int | None = None  # when the data itself was produced (epoch seconds)
    file_time: int | None = None  # file modification time
    loaded_at: int | None = None
    files: list = field(default_factory=list)

    def to_dict(self):
        return dict(self.__dict__)


def _mtime(paths) -> int:
    best = 0
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in p.glob('*.lua'):
                best = max(best, int(f.stat().st_mtime))
        elif p.exists():
            best = max(best, int(p.stat().st_mtime))
    return best


def _hours(seconds: float) -> str:
    h = seconds / 3600
    return f'{h * 60:.0f} min' if h < 1 else (f'{h:.1f} h' if h < 48 else f'{h / 24:.1f} days')


class World:
    def __init__(self, paths: GamePaths, settings, log=print):
        self.paths = paths
        self.settings = settings
        self.log = log
        self.lock = threading.RLock()
        self.gamedata: gamedata.GameData | None = None
        self.price_data: PriceData | None = None
        self.prices: dict[int, dict] = {}
        self.questie: QuestieDB | None = None
        self.drop_rates: dict = {}
        self.syndicator: dict = {}
        self.source_grades: dict = {}
        self.untrusted_items = 0
        self.skillup: SkillUpData = SkillUpData()          # SkillUpForever with ForeverRecipes filling its holes
        self.skillup_raw: SkillUpData = SkillUpData()      # SkillUpForever alone (for the cross-check)
        self.forever_recipes = None                        # ForeverRecipes addon data (foreverrecipes.py)
        self.angler: dict | None = None
        self.classic_fishing: classicdb.ClassicFishing | None = None
        self.forever_fishing: dict = {}      # zone name -> Wowhead Forever counts (read by hand)
        self.forever_containers: dict = {}   # item id -> what it contains in Forever (Wowhead, read by hand)
        self.forever_skinning: dict = {}     # Wowhead Forever "Skinned from" counts (read by hand)
        self.forever_pages: dict = {}        # Wowhead Forever item/object/npc pages (wowhead_items.py)
        self.everloot: dict = {}             # Everloot drop rates (everloot.py): cross-checked, not used in rows
        self.known_crafts: dict = {}         # character -> recipe spells it knows (TSM crafting data)
        self.gatherlite: dict = {}           # GatherLite node positions per object and zone (gatherlite.py)
        self.inventory: dict = {}
        self.hotfix_info: dict = {}
        self.profile: dict = {'characters': {}, 'active': None, 'activity': {}}
        self.status: dict[str, SourceStatus] = {}
        self._mtimes: dict[str, int] = {}
        self.client_build: str | None = None
        self.wago_latest: str | None = None
        self.wago_checked: int = 0
        self.version = 0     # bumps whenever anything reloads
        self.tooltips = TooltipCache(log)
        self._tooltips_dirty = threading.Event()
        self.tooltips.on_batch = self._tooltips_dirty.set
        self.fetch_tooltips = True

    # ---------- loaders ----------
    def _sv(self, filename: str) -> Path | None:
        for d in self.paths.account_savedvariables():
            p = d / filename
            if p.exists():
                return p
        return None

    def _load_gamedata(self, force_check=False):
        st = self.status.setdefault('gamedata', SourceStatus('gamedata', 'Game data (wago.tools)'))
        self.client_build = self.paths.client_build()
        now = time.time()
        if force_check or now - self.wago_checked > 24 * 3600:
            try:
                self.wago_latest = gamedata.latest_wago_build()
            except Exception as e:  # offline is fine; we keep using the cache
                self.log(f'wago.tools build check failed: {e}')
            self.wago_checked = int(now)
        wanted = self.client_build or self.wago_latest
        cached = gamedata.cached_builds()
        if wanted and wanted not in cached:
            try:
                gamedata.ensure_tables(wanted, self.log)
                cached = gamedata.cached_builds()
            except Exception as e:
                self.log(f'Could not download game data for {wanted}: {e}')
        build = wanted if wanted in cached else (cached[-1] if cached else None)
        if not build:
            st.status, st.note = 'error', 'No game data yet and wago.tools could not be reached.'
            return
        if not self.gamedata or self.gamedata.build != build:
            self.gamedata = gamedata.load(build)
            self.version += 1
        st.version, st.data_time, st.loaded_at = build, self.gamedata.downloaded, int(now)
        st.files = [str(gamedata.build_dir(build))]
        if self.client_build and build != self.client_build:
            st.status, st.note = 'stale', f'Your client is {self.client_build}, using tables for {build}.'
        elif self.wago_latest and build != self.wago_latest:
            st.status, st.note = 'warn', f'wago.tools has a newer build ({self.wago_latest}).'
        else:
            st.status, st.note = 'ok', f'Matches your client build {self.client_build or "?"}.'

    def _load_tsm(self):
        st = self.status.setdefault('tsm', SourceStatus('tsm', 'TSM prices (AppData.lua)'))
        path = self.paths.tsm_appdata
        st.files = [str(path)]
        if not path.exists():
            st.status, st.note = 'missing', 'TSM AppHelper AppData.lua not found.'
            return
        self.price_data = parse_appdata(path)
        realm = self.settings.snapshot().get('realm')
        if realm not in self.price_data.realms() and self.price_data.realms():
            realm = self.price_data.realms()[0]
        self.prices = self.price_data.merged(realm)
        st.file_time, st.loaded_at = int(path.stat().st_mtime), int(time.time())
        st.version = self.paths.addon_version('TradeSkillMaster_AppHelper')
        st.status = 'ok'
        self.version += 1

    def _load_questie(self):
        st = self.status.setdefault('questie', SourceStatus('questie', 'QuestieDB (vendors, NPCs, drops)'))
        toc, drops = self.paths.questie_toc, self.paths.questie_drops
        st.files = [str(toc), str(drops)]
        if not toc.exists():
            st.status, st.note = 'missing', 'QuestieDB not installed; vendor and drop info unavailable.'
            self.questie = QuestieDB()
            return
        self.questie = load_questie(toc)
        self.drop_rates = load_drop_rates(drops) if drops.exists() else {}
        st.version = self.paths.addon_version('QuestieDB')
        st.file_time, st.loaded_at, st.status = _mtime(st.files), int(time.time()), 'ok'
        st.note = f'{len(self.questie.items)} items, {len(self.questie.npcs)} NPCs.'
        self.version += 1

    def _load_skillup(self):
        st = self.status.setdefault('skillup', SourceStatus('skillup', 'SkillUpForever (recipe skill, trainers, stock)'))
        d = self.paths.skillup_data
        st.files = [str(d)]
        if not d.exists():
            st.status, st.note = 'missing', ('Not installed: recipes can\'t be checked as learnable in Forever, so crafts '
                                             'are marked "unverified recipe" and kept out of Top picks, and recipe skill '
                                             'levels are estimated. Install the SkillUpForever addon.')
            self.skillup_raw = SkillUpData()
        else:
            self.skillup_raw = load_skillup(d)
        self._load_forever_recipes()
        self.skillup = foreverrecipes_mod.merged(self.skillup_raw, self.forever_recipes)
        if not d.exists():
            if self.forever_recipes and self.forever_recipes.recipes:
                st.note += ' ForeverRecipes is installed and fills in for it where it can.'
            self.version += 1
            return
        st.version = self.paths.addon_version('SkillUpForever')
        st.file_time, st.loaded_at = _mtime([d]), int(time.time())
        cb = self.client_build or self.paths.client_build()
        if self.skillup.source_build and cb and self.skillup.source_build != cb:
            st.status = 'warn'
            st.note = f'Its data was generated for build {self.skillup.source_build}; your client is {cb}.'
        else:
            st.status, st.note = 'ok', ''
        self.version += 1

    def _load_forever_recipes(self):
        """ForeverRecipes (a second source of Forever recipe facts; merged into self.skillup by _load_skillup)."""
        st = self.status.setdefault('foreverrecipes', SourceStatus(
            'foreverrecipes', 'ForeverRecipes (recipe skill, poisons, trainers: second source)'))
        d = self.paths.foreverrecipes_data
        st.files = [str(d)]
        if not d.exists():
            self.forever_recipes = None
            st.status, st.note = 'missing', ('Optional. Not installed: SkillUpForever alone gives recipe skill levels, '
                                             'and rogue poisons are not covered.')
            return
        self.forever_recipes = foreverrecipes_mod.load(d)
        st.version = self.paths.addon_version('ForeverRecipes')
        st.file_time, st.loaded_at = _mtime([d]), int(time.time())
        n = len(self.forever_recipes.recipes)
        st.status = 'ok' if n else 'warn'
        st.note = f'{n} recipes (data from client build {self.forever_recipes.source_build or "?"})'

    def _load_gatherlite(self):
        st = self.status.setdefault('gatherlite', SourceStatus('gatherlite', 'GatherLite node positions (Forever)'))
        f = gatherlite_mod.data_file(self.paths.addons)
        nf = gatherlite_mod.nodes_file(self.paths.addons)
        st.files = [str(x) for x in (f, nf) if x]
        if not f or not self.gamedata:
            st.status, st.note = 'missing', 'GatherLite is not installed (optional: node and pool positions).'
            self.gatherlite = {}
            return
        self.gatherlite = gatherlite_mod.load(self.paths.addons, gamedata.build_dir(self.gamedata.build))
        st.file_time, st.loaded_at, st.status = int(f.stat().st_mtime), int(time.time()), 'ok'
        st.version = self.paths.addon_version('GatherLite')
        g = self.gatherlite
        st.note = (f"{g.get('objects', 0)} nodes, chests and pools, {g.get('points', 0):,} positions "
                   f"({sum(sum(z.values()) for z in (g.get('nodes') or {}).values()):,} distinct after merging repeats). "
                   f"Compared with QuestieDB on Data health. {len(g.get('types') or {})} node types (which ore and herb "
                   'nodes there are: with QuestieDB, which materials you gather).')
        self.version += 1

    def _load_angler(self):
        st = self.status.setdefault('angler', SourceStatus('angler', 'ForeverAngler catch log'))
        p = self._sv('ForeverAngler.lua')
        st.files = [str(p)] if p else []
        if not p:
            st.status, st.note = 'missing', 'No catch log yet (written on logout or /reload).'
            self.angler = None
            return
        self.angler = parse_assignments(p.read_text(encoding='utf-8', errors='replace')).get('ForeverAnglerDB') or {}
        st.file_time, st.loaded_at, st.status = int(p.stat().st_mtime), int(time.time()), 'ok'
        st.version = self.paths.addon_version('ForeverAngler')
        zones = self.angler.get('zones') or {}
        st.note = f'{len(zones)} zones, {sum(int(z.get("c") or 0) for z in zones.values())} casts. Updates on logout or /reload.'
        self.version += 1

    def _load_hotfix(self):
        """Overlay the server's item data from your client's hotfix cache (exact Forever data, see hotfix.py)."""
        st = self.status.setdefault('hotfix', SourceStatus('hotfix', "Server item data (your client's hotfix cache)"))
        p = self.paths.hotfix_cache()
        st.files = [str(p)] if p else []
        if not p or not self.gamedata:
            st.status = 'missing'
            st.note = ('No hotfix cache found (Cache/ADB/<locale>/DBCache.bin): items the client tables lack come '
                       'from Wowhead tooltips instead.')
            return
        folder = gamedata.build_dir(self.gamedata.build)
        if not self.gamedata.build.endswith(str(hotfix.read_cache_build(p))):
            st.status = 'warn'
            st.note = 'The hotfix cache is from another client build; start the game once to refresh it.'
            return
        h = hotfix.load_item_hotfixes(p, folder / 'ItemSparse.csv', folder / 'itemsparse_hotfix_layout.json')
        counts = gamedata.apply_hotfixes(self.gamedata, h.rows)
        self.hotfix_info = {'added': counts['added'], 'updated': counts['updated'], 'agreement': h.agreement,
                            'unreliable': h.unreliable, 'changed_fields': h.changed_fields, 'inferred': h.inferred}
        st.file_time, st.loaded_at, st.version = int(p.stat().st_mtime), int(time.time()), f'build {h.cache_build}'
        st.status = 'ok' if h.agreement >= 0.95 else 'warn'
        st.note = (f'{counts["added"]:,} items added and {counts["updated"]:,} updated from the data the Forever '
                   f'server sent your client. Check: {h.agreement:.1%} of items in both decode exactly to the client '
                   f'tables (the rest differ only where the server changed them). Fields not trusted: '
                   f'{", ".join(h.unreliable) or "none"}.')
        self.version += 1

    def _load_classic(self):
        st = self.status.setdefault('classicdb', SourceStatus(
            'classicdb', 'Fishing tables (Classic 1.12 from cMaNGOS, not Forever)'))
        st.files = [str(classicdb.CACHE)]
        cf = classicdb.load_cached()
        if not cf and classicdb.latest_dump():
            cf = classicdb.rebuild(classicdb.latest_dump())
        self.classic_fishing = cf
        st.loaded_at = int(time.time())
        if not cf:
            st.status = 'missing'
            st.note = ('Not downloaded. Run "python -m wfm.classicdb --update" (about 13 MB from github.com/cmangos/'
                       'classic-db). Until then, fishing spots come only from your own logs.')
            return
        st.version = cf.source.get('file')
        st.data_time = cf.source.get('extracted_at')
        st.file_time = int(classicdb.CACHE.stat().st_mtime) if classicdb.CACHE.exists() else None
        check = classicdb.last_check()
        remote = check.get('remote') or {}
        notes = [f'{len(cf.loot)} fishing areas and {len(cf.pools)} pool types. This is Classic WoW 1.12 data, '
                 f'not Forever: used only where there is no Forever data yet, shown as "Classic table" rows, and '
                 f'never in Top picks.']
        if cf.source.get('updates'):
            notes.append(f'Applied updates: {", ".join(cf.source["updates"])}.')
        if cf.warnings:
            notes.append(f'{len(cf.warnings)} update statements could not be applied.')
        if remote.get('sha') and cf.source.get('sha') and remote['sha'] != cf.source['sha']:
            st.status = 'warn'
            notes.append(f'GitHub has a newer dump ({remote.get("name")}, {remote.get("size", 0) / 1e6:.0f} MB): '
                         f'run "python -m wfm.classicdb --update".')
        else:
            st.status = 'warn' if cf.warnings else 'ok'
        if check.get('checked'):
            notes.append(f'Checked GitHub for a newer dump {_hours(time.time() - check["checked"])} ago.')
        st.note = ' '.join(notes)
        self.version += 1

    def _check_classic_remote(self):
        """Once a month: is there a newer Classic dump on GitHub? (Only checks; downloading is up to you.)"""
        if time.time() - (classicdb.last_check().get('checked') or 0) < 30 * 86400:
            return False
        try:
            classicdb.save_check(classicdb.remote_dump())
        except Exception as e:      # offline is fine
            self.log(f'classic-db update check failed: {e}')
            classicdb.save_check(None)
        self._load_classic()
        return True

    def _load_checks(self):
        st = self.status.setdefault('checks', SourceStatus('checks', 'Wowhead Forever pages (read by hand): fishing, containers, skinning, item sources'))
        # the shared pack (encrypted, in the repository) unlocks into data/ when the data key is set in Settings
        self.pack_status = datapack_mod.unpack(self.settings.snapshot().get('data_key') or '')
        p = WOWHEAD_FISHING
        st.files = [str(p)]
        data = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        self.forever_fishing = {z: {**v, 'items': {int(k): int(c) for k, c in v.get('items', {}).items()}}
                                for z, v in (data.get('zones') or {}).items()}
        st.files.append(str(WOWHEAD_CONTAINERS))
        cdata = json.loads(WOWHEAD_CONTAINERS.read_text(encoding='utf-8')) if WOWHEAD_CONTAINERS.exists() else {}
        self.forever_containers = cdata.get('containers') or {}
        st.files += [str(skinning_mod.SNAPSHOT), str(wowhead_items.SNAPSHOT)]
        self.forever_pages = wowhead_items.load()
        # item pages read in full add their "Skinned from" rows to the skinning snapshot (an item page wins)
        self.forever_skinning = wowhead_items.merge_skinning(skinning_mod.load(), self.forever_pages)
        self.everloot = everloot_mod.load()          # a second source, cross-checked on Data health only
        st.files += [str(f) for f in everloot_mod.files()]
        st.loaded_at = int(time.time())
        st.file_time = _mtime([p, WOWHEAD_CONTAINERS, skinning_mod.SNAPSHOT, wowhead_items.SNAPSHOT]) or None
        dates = sorted({v.get('checked', '') for v in list(self.forever_fishing.values()) + list(self.forever_containers.values())}
                       | {pg.get('read', '') for sec in wowhead_items.SECTIONS
                          for pg in (self.forever_pages.get(sec) or {}).values()} - {''})
        st.version = dates[-1] if dates else None
        if not self.forever_fishing:
            st.status, st.note = 'missing', 'No zones read from Wowhead Forever yet.'
        else:
            st.status = 'ok'
            st.note = (f'{len(self.forever_fishing)} zones ({", ".join(sorted(self.forever_fishing))}), '
                       f'{sum(v.get("fished", 0) for v in self.forever_fishing.values()):,} Forever catches. '
                       f'Contents of {len(self.forever_containers)} containers '
                       f'({", ".join(v.get("name", k) for k, v in self.forever_containers.items())}). '
                       f'Skinning: {len((self.forever_skinning or {}).get("items") or {})} items. '
                       f'Pages read in full: {len(self.forever_pages.get("items") or {})} items, '
                       f'{len(self.forever_pages.get("objects") or {})} objects, '
                       f'{len(self.forever_pages.get("npcs") or {})} mobs. '
                       f'A snapshot from {", ".join(dates)}; refresh by re-reading the pages.')
        self.version += 1

    def _load_inventory(self):
        st = self.status.setdefault('inventory', SourceStatus('inventory', 'Your bags (Syndicator)'))
        p = self._sv('Syndicator.lua')
        st.files = [str(p)] if p else []
        if not p:
            st.status, st.note = 'missing', 'Syndicator not found.'
            return
        data = parse_assignments(p.read_text(encoding='utf-8', errors='replace')).get('SYNDICATOR_DATA') or {}
        inv: dict[str, dict[int, int]] = {}
        for char, cd in (data.get('Characters') or {}).items():
            counts: dict[int, int] = {}
            for section in ('bags', 'bank'):
                for bag in _as_list(cd.get(section)):
                    for slot in _as_list(bag):
                        if isinstance(slot, dict) and slot.get('itemID'):
                            counts[int(slot['itemID'])] = counts.get(int(slot['itemID']), 0) + int(slot.get('itemCount') or 1)
            inv[char] = counts
        self.inventory = inv
        # gold, mail and your current auctions per character (Syndicator doesn't record listing prices)
        self.syndicator = {}
        for char, cd in (data.get('Characters') or {}).items():
            det = cd.get('details') or {}
            self.syndicator[char] = {
                'name': det.get('character') or char.split('-')[0], 'realm': det.get('realm') or '',
                'faction': det.get('faction') or '', 'money': int(cd.get('money') or 0),
                'mail': _item_counts(cd.get('mail')), 'equipped': _item_counts(cd.get('equipped')),
                'auctions': [{'item': int(a['itemID']), 'count': int(a.get('itemCount') or 1),
                              'expires': int(a.get('expirationTime') or 0)}
                             for a in _as_list(cd.get('auctions')) if isinstance(a, dict) and a.get('itemID')]}
        self._merge_money()
        st.file_time, st.loaded_at, st.status = int(p.stat().st_mtime), int(time.time()), 'ok'
        st.version = self.paths.addon_version('Syndicator')
        st.note = f'{len(inv)} characters. Updates on logout or /reload.'
        self.version += 1

    def _merge_money(self):
        """Gold per character: Syndicator's figure wins over the addon's. Found 2026-11-14: ForeverMoneyBridge 1.4.0
        saved 0 gold on logout/reload (the game can report 0 while logging out) while Syndicator had 26g 78s."""
        chars = (getattr(self, 'profile', None) or {}).get('characters') or {}
        for c in (getattr(self, 'syndicator', None) or {}).values():
            for name, pc in chars.items():
                if name.split('-')[0] == c['name'] and _same_realm(pc.get('realm') or '', c['realm']):
                    if pc.get('money') != c['money']:
                        pc['money_addon'] = pc.get('money')
                    pc['money'], pc['money_source'] = c['money'], 'Syndicator'

    def _char_mtimes(self) -> dict[str, float]:
        out = {}
        for sv in self.paths.character_savedvariables():
            name = sv.parent.name.replace('-', ' ')
            files = list(sv.glob('*.lua'))
            if files:
                out[name] = max(f.stat().st_mtime for f in files)
        return out

    def _load_profile(self):
        st = self.status.setdefault('profile', SourceStatus('profile', 'Your characters (ForeverMoneyBridge + TSM)'))
        bridge_path, tsm_path = self._sv('ForeverMoneyBridge.lua'), self._sv('TradeSkillMaster.lua')
        st.files = [str(p) for p in (bridge_path, tsm_path) if p]
        bridge = profile_mod.read_bridge(bridge_path)
        tsm_db = profile_mod.read_tsm_db(tsm_path)
        tsm_chars = profile_mod.read_tsm_characters(tsm_path, tsm_db)
        self.known_crafts = profile_mod.known_crafts(tsm_db)      # recipes each character knows (TSM)
        self.profile = profile_mod.build_profile(bridge, tsm_chars, self._char_mtimes())
        self._merge_money()
        st.loaded_at = int(time.time())
        st.file_time = _mtime(st.files) or None
        st.version = self.paths.addon_version(profile_mod.ADDON_NAME)
        n = len(self.profile['characters'])
        if bridge:
            st.status = 'ok'
            st.note = f'{n} characters; active: {self.profile["active"]}. Updates on logout or /reload.'
        elif n:
            st.status = 'warn'
            st.note = (f'{n} characters from TSM (gold, professions; no level). Log in once with ForeverMoneyBridge '
                       f'enabled and /reload to add level and loot tracking. Active guess: {self.profile["active"]}.')
        else:
            st.status, st.note = 'missing', 'No character data yet; using your manual settings.'
        self.version += 1

    LOADERS = {
        'hotfix': ('_load_hotfix', lambda self: [self.paths.hotfix_cache() or '']),
        'tsm': ('_load_tsm', lambda self: [self.paths.tsm_appdata]),
        'questie': ('_load_questie', lambda self: [self.paths.questie_toc, self.paths.questie_drops]),
        'skillup': ('_load_skillup', lambda self: [self.paths.skillup_data, self.paths.foreverrecipes_data]),
        'angler': ('_load_angler', lambda self: [self._sv('ForeverAngler.lua') or '']),
        'gatherlite': ('_load_gatherlite', lambda self: [gatherlite_mod.data_file(self.paths.addons) or '',
                                                         gatherlite_mod.nodes_file(self.paths.addons) or '']),
        'classicdb': ('_load_classic', lambda self: [classicdb.CACHE]),
        'checks': ('_load_checks', lambda self: [WOWHEAD_FISHING, WOWHEAD_CONTAINERS, skinning_mod.SNAPSHOT,
                                                 wowhead_items.SNAPSHOT, datapack_mod.PACK, *everloot_mod.files()]),
        'inventory': ('_load_inventory', lambda self: [self._sv('Syndicator.lua') or '']),
        'profile': ('_load_profile', lambda self: [self._sv('ForeverMoneyBridge.lua') or '',
                                                   self._sv('TradeSkillMaster.lua') or '']),
    }

    def fill_missing_items(self):
        """Items TSM prices (or you carry) that the client's ItemSparse table lacks."""
        if not self.gamedata:
            return
        wanted = set(self.prices) | {i for inv in self.inventory.values() for i in inv}
        missing = [i for i in wanted if i not in self.gamedata.items or self.gamedata.items[i].partial]
        need_fetch = []
        for iid in missing:
            info = self.tooltips.get(iid)
            qname = (self.questie.items.get(iid) or {}).get('name') if self.questie else None
            existing = self.gamedata.items.get(iid)
            if (existing and existing.partial and existing.source != 'in-game' and info
                    and existing.sell_price == 0 and info.get('sell_price')):
                del self.gamedata.items[iid]       # upgrade a name-only item with tooltip info
            gamedata.add_partial_item(self.gamedata, iid, info, qname)
            if not info:
                need_fetch.append(iid)
        st = self.status.setdefault('items', SourceStatus('items', 'Extra item info (Wowhead tooltips)'))
        partial = [i for i in wanted if i in self.gamedata.items and self.gamedata.items[i].partial]
        filled = sum(1 for i in partial if self.tooltips.get(i))
        st.status = 'ok' if not need_fetch else 'warn'
        st.note = (f'{len(missing)} priced or owned items are missing from the game tables: {filled} filled from Wowhead tooltips, {len(need_fetch)} waiting '
                   f'(name from Questie, vendor price unknown until fetched; ~{len(need_fetch) * 1.5 / 60:.0f} min left).')
        st.loaded_at = int(time.time())
        if need_fetch and self.fetch_tooltips:
            self.tooltips.want(sorted(need_fetch))
        # what your own game client reported (ForeverMoneyBridge item checks) overrides every other source
        gamedata.apply_ingame(self.gamedata, (self.profile or {}).get('item_info'))
        # TSM's vendor sell prices, read in game: they beat the game files for unchecked items (2026-11-19)
        self.tsm_vendor_report = gamedata.apply_tsm_vendor(self.gamedata, (self.profile or {}).get('tsm_vendor'))
        # stop trusting a source's field for unchecked items once the game shows it is often wrong
        self.source_grades = gamedata.grade_sources(self.gamedata)
        self.untrusted_items = gamedata.mark_untrusted(self.gamedata, self.source_grades)

    def source_disagreements(self) -> list[int]:
        """Items whose server data (hotfix cache) and Wowhead Forever tooltip disagree on the sell price."""
        gd = self.gamedata
        out = []
        for iid, it in (gd.items.items() if gd else ()):
            if it.source in ('server', 'server-new'):
                t = self.tooltips.get(iid)
                if t and t.get('sell_price') is not None and t['sell_price'] != it.sell_price:
                    out.append(iid)
        return out

    def item_checks_wanted(self, important: set[int], limit: int = 800) -> list[int]:
        """Items for the addon to look up in game, most useful first: where sources disagree, items behind the
        current recommendations, items known only from Wowhead/Questie, then a sample that rotates daily. Items
        verified in the last week are skipped."""
        gd = self.gamedata
        if not gd:
            return []
        import random
        now = time.time()
        info = (self.profile or {}).get('item_info') or {}
        fresh = set()
        for k, v in info.items():
            try:
                if isinstance(v, dict) and now - float(v.get('t') or 0) < 7 * 86400:
                    fresh.add(int(k))
            except (TypeError, ValueError):
                continue
        out, seen = [], set(fresh)

        def add(ids):
            for i in ids:
                if len(out) >= limit:
                    return
                if i not in seen and i in gd.items:
                    seen.add(i)
                    out.append(i)

        add(sorted(self.source_disagreements()))
        add(sorted(important))
        # items whose source is unreliable for a field, the ones with prices first
        add(sorted(i for i, it in gd.items.items() if it.untrusted and i in self.prices))
        add(sorted(i for i, it in gd.items.items() if it.source in ('wowhead', 'questie') and i in self.prices))
        rnd = random.Random(int(now // 86400))
        ids = sorted(gd.items)
        add(rnd.sample(ids, min(100, len(ids))))
        return out

    def load_all(self):
        with self.lock:
            self._safe('gamedata', lambda: self._load_gamedata(force_check=True))
            for name, (fn, files) in self.LOADERS.items():
                self._mtimes[name] = _mtime(files(self))
                self._safe(name, getattr(self, fn))
            self._safe('items', self.fill_missing_items)
            self.refresh_freshness()

    def poll(self) -> list[str]:
        """Reload anything whose files changed. Returns the names of reloaded sources."""
        changed = []
        with self.lock:
            build = self.paths.client_build()
            if build != self.client_build or time.time() - self.wago_checked > 24 * 3600:
                before = self.gamedata.build if self.gamedata else None
                self._safe('gamedata', self._load_gamedata)
                if (self.gamedata.build if self.gamedata else None) != before:
                    changed.append('gamedata')
                    self._safe('hotfix', self._load_hotfix)      # fresh tables: overlay the server data again
            for name, (fn, files) in self.LOADERS.items():
                m = _mtime(files(self))
                if m != self._mtimes.get(name):
                    self._mtimes[name] = m
                    self._safe(name, getattr(self, fn))
                    changed.append(name)
            try:
                if self._check_classic_remote():
                    changed.append('classicdb')
            except Exception as e:
                self.log(f'classic-db check failed: {e}')
            if self._tooltips_dirty.is_set():
                self._tooltips_dirty.clear()
                changed.append('items')
            if changed:
                self._safe('items', self.fill_missing_items)
                self.version += 1
            self.refresh_freshness()
        return changed

    def _safe(self, name, fn):
        try:
            fn()
        except Exception as e:
            st = self.status.setdefault(name, SourceStatus(name, name))
            st.status, st.note = 'error', f'{type(e).__name__}: {e}'
            self.log(f'Failed to load {name}:\n{traceback.format_exc()}')

    # ---------- freshness ----------
    def refresh_freshness(self):
        now = time.time()
        s = self.settings.snapshot()
        stale = s.get('stale_hours', {})
        pd = self.price_data
        if not pd:
            return
        realm = s.get('realm')
        realm_times = [d.download_time for d in pd.datasets if d.scope == realm and d.kind == 'AUCTIONDB_NON_COMMODITY_DATA']
        region_times = [d.download_time for d in pd.datasets if d.kind.startswith('AUCTIONDB_REGION')]
        rows = []
        for label, times, limit in (('realm', realm_times, stale.get('realm', 3)), ('region', region_times, stale.get('region', 36))):
            if not times:
                rows.append(f'no {label} data')
                continue
            age = now - max(times)
            flag = '' if age < limit * 3600 else (' (stale)' if age > limit * 4 * 3600 else ' (old)')
            rows.append(f'{label} scan {_hours(age)} ago{flag}')
        st = self.status['tsm']
        st.data_time = max(realm_times) if realm_times else None
        realm_age = now - max(realm_times) if realm_times else 1e12
        sync_age = now - pd.app_info.get('lastSync', 0) if pd.app_info.get('lastSync') else None
        if realm not in pd.realms():
            st.status = 'warn'
            rows.insert(0, f'realm "{realm}" not in TSM data (has: {", ".join(pd.realms()) or "none"})')
        elif realm_age > stale.get('realm', 3) * 4 * 3600:
            st.status = 'stale'
        elif realm_age > stale.get('realm', 3) * 3600:
            st.status = 'warn'
        else:
            st.status = 'ok'
        if sync_age is not None:
            rows.append(f'TSM app last synced {_hours(sync_age)} ago')
            if sync_age > 3 * 3600 and st.status == 'ok':
                st.status = 'warn'
                rows.append('is the TSM desktop app running?')
        st.note = '; '.join(rows)

    def freshness(self) -> list[dict]:
        return [s.to_dict() for s in self.status.values()]




def _same_realm(a: str, b: str) -> bool:
    """The addon can record the server's internal realm name ("CAMWOW EU5 Realm 4 PvP") where Syndicator and TSM say "PvP"."""
    a, b = a.strip(), b.strip()
    return not a or not b or a == b or a.endswith(' ' + b) or b.endswith(' ' + a)

def _item_counts(x, out: dict | None = None) -> dict[int, int]:
    """Item counts from any nesting of Syndicator lists/tables with itemID/itemCount (mail, bags)."""
    out = {} if out is None else out
    if isinstance(x, dict):
        if x.get('itemID'):
            out[int(x['itemID'])] = out.get(int(x['itemID']), 0) + int(x.get('itemCount') or 1)
        else:
            for v in x.values():
                _item_counts(v, out)
    elif isinstance(x, list):
        for v in x:
            _item_counts(v, out)
    return out

def _as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return [v[k] for k in sorted(v, key=lambda k: (not isinstance(k, int), k))]
    return []
