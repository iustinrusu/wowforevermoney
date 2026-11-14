"""Fishing spots in every zone: the Classic baseline (cMaNGOS classic-db) corrected by your own catches.

A zone has one or more open-water "spots": the zone's own loot table, plus subzones with a different table
(often the coast). Your logs (ForeverAngler, ForeverMoneyBridge) are per zone, so a zone's log is matched to
the spot that explains most of what you caught there, and blended in: each fish's share is
    w * your share + (1 - w) * Classic share,   w = n / (n + PRIOR_CATCHES),  n = catches you logged there.
Zones Classic doesn't know (new in Forever) come from your logs only.

Chance a cast lands a fish = (1 - your miss rate) * (1 - got-away rate). Got-away rate, best source first:
your own rate in that zone, your rate in zones with the same Classic zone skill, the Classic formula.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import gamedata
from .classicdb import CONDITION_EVENT, ClassicFishing, expected_items, success_chance

PRIOR_CATCHES = 30           # after this many logged catches your data weighs as much as Classic's
MIN_RATE_SAMPLE = 20         # catches + getaways needed before trusting a measured got-away rate
INCOMPLETE = 0.9             # a Classic table explaining less than 90% of catches is incomplete
NEW_FISH_MIN = 2             # logged this many times in a zone where Classic doesn't have it -> Forever change
NEW_FISH_SHARE = 0.005       # ... and at least 0.5% of catches (big Wowhead samples have one-off oddities)
WOWHEAD_CONFIRM = 30         # Wowhead Forever catches needed to count as confirmation
SNAPSHOT_MAX_DAYS = 30       # Wowhead Forever counts older than this are flagged for re-reading
MISSING_SHARE, MISSING_N = 0.15, 40   # Classic says >= 15% but none in your 40+ catches -> maybe removed
MATCH_MIN = 0.5              # a spot must explain half of a zone log's (non-pool) catches to be blended with it


@dataclass
class Spot:
    zone_id: int
    zone: str
    areas: list[int]
    names: list[str]                 # subzone names; [] = the zone's own waters
    skill: int | None                # Classic zone skill (minimum to catch anything in Classic)
    shares: dict[int, dict]          # item -> share per catch (+ quest/seasonal info)
    coverage: float                  # share of catches the table explains (1.0 = complete)
    dungeon: bool = False

    def label(self, others: bool) -> str:
        if not self.names:
            return f'{self.zone} (rest of the zone)' if others else self.zone
        more = f' +{len(self.names) - 1} more' if len(self.names) > 1 else ''
        return f'{self.zone}: {self.names[0]}{more}'


@dataclass
class Obs:
    zone: str
    casts: int = 0
    caught: int = 0
    escaped: int = 0
    items: dict[int, int] = field(default_factory=dict)
    seconds: float = 0.0
    timed_catches: int = 0
    sources: list[str] = field(default_factory=list)
    wh_fished: int = 0                    # Wowhead Forever: times the zone's waters were fished
    wh_items: dict[int, int] = field(default_factory=dict)
    wh_checked: str = ''
    wh_url: str = ''

    def total(self) -> int:
        """Forever catches known for this zone: yours plus Wowhead's."""
        return self.caught + self.wh_fished

    def all_items(self) -> dict[int, int]:
        out = dict(self.items)
        for i, c in self.wh_items.items():
            out[i] = out.get(i, 0) + c
        return out


def add_wowhead(obs: dict[str, 'Obs'], wowhead: dict | None) -> dict[str, 'Obs']:
    """Add Wowhead Forever zone counts (read by hand) to your own logs. Your casts and got-away counts stay
    yours alone: Wowhead has no cast data, so it only adds catches."""
    for zone, z in (wowhead or {}).items():
        if not z.get('fished'):
            continue
        o = obs.setdefault(zone, Obs(zone=zone))
        o.wh_fished, o.wh_items = int(z['fished']), {int(k): int(v) for k, v in (z.get('items') or {}).items()}
        o.wh_checked, o.wh_url = z.get('checked', ''), z.get('url', '')
        o.sources.append(f'Wowhead Forever ({o.wh_checked})')
    return obs


def _top_zone(gd, area: int) -> int:
    seen = set()
    while gd.zone_parent.get(area) and area not in seen:
        seen.add(area)
        area = gd.zone_parent[area]
    return area


SEASON_EVIDENCE_DAYS = 14     # a seasonal fish caught in Forever this recently means its season is on


def seasonal_items(cf: ClassicFishing) -> dict[int, set[int]]:
    """Game event id -> items only caught while it's active (Winter Squid, Summer Bass...)."""
    out: dict[int, set[int]] = {}
    for rows in list(cf.loot.values()) + list(cf.refs.values()):
        for e in rows:
            c = cf.conditions.get(e['condition']) or {}
            if c.get('type') == CONDITION_EVENT and e['minref'] > 0:
                out.setdefault(c['value1'], set()).add(e['item'])
    return out


def forever_seasons(cf: ClassicFishing, wowhead: dict | None, now: float | None = None) -> dict[int, bool]:
    """Which seasons are on in Forever right now, from Forever catches (Wowhead Forever counts read in the last
    two weeks): a seasonal fish being caught means its season is on, and then a season with none of its fish
    caught is off. No recent evidence: {} (the Classic calendar is used, labelled as such)."""
    import time as _t
    now = _t.time() if now is None else now
    seen = set()
    for z in (wowhead or {}).values():
        try:
            age = (now - _t.mktime(_t.strptime(str(z.get('checked', '')), '%Y-%m-%d'))) / 86400
        except ValueError:
            continue
        if age <= SEASON_EVIDENCE_DAYS:
            seen |= {int(i) for i, c in (z.get('items') or {}).items() if int(c) > 0}
    gated = seasonal_items(cf)
    on = {eid for eid, items in gated.items() if items & seen}
    return {eid: eid in on for eid in gated} if on else {}


def item_shares(cf: ClassicFishing, entries: list[dict], now: float | None = None,
                seasons: dict[int, bool] | None = None) -> tuple[dict[int, dict], float]:
    """Per-catch share of each item from a loot table, with seasons applied. Returns (shares, coverage).
    seasons: what Forever catches say is in season (forever_seasons); otherwise the Classic calendar."""
    out, coverage = {}, 0.0
    for item, o in expected_items(entries, cf.refs).items():
        seasonal, in_season, factor = None, None, 1.0
        for cid in o['conditions']:
            c = cf.conditions.get(cid) or {}
            if c.get('type') == CONDITION_EVENT:
                seasonal = cf.events.get(c['value1'], {}).get('name') or f'event {c["value1"]}'
                if seasons and c['value1'] in seasons:
                    in_season = seasons[c['value1']]
                    seasonal += ' (Forever catches)'
                    factor *= 1.0 if in_season else 0.0
                else:
                    in_season, part = cf.event_status(c['value1'], now)
                    seasonal += ' (Classic calendar)'
                    factor *= part if in_season is None else (1.0 if in_season else 0.0)
        share = o['count'] * factor
        out[item] = {'share': share, 'quest': o['quest'], 'seasonal': seasonal, 'in_season': in_season,
                     'raw': o['count']}
        if not o['quest']:
            coverage += share
    return out, coverage


def build_spots(cf: ClassicFishing, gd, now: float | None = None,
                seasons: dict[int, bool] | None = None) -> dict[int, list[Spot]]:
    groups: dict[tuple, list[int]] = {}
    for area, entries in cf.loot.items():
        zid = _top_zone(gd, area)
        sig = tuple(sorted((e['item'], e['chance'], e['group'], e['minref'], e['maxcount'], e['condition'])
                           for e in entries))
        skill = cf.skill.get(area, cf.skill.get(zid))
        groups.setdefault((zid, sig, skill), []).append(area)
    spots: dict[int, list[Spot]] = {}
    for (zid, _sig, skill), areas in groups.items():
        shares, coverage = item_shares(cf, cf.loot[areas[0]], now, seasons)
        names = sorted(gd.zones.get(a) or f'Area {a}' for a in areas if a != zid)
        spots.setdefault(zid, []).append(Spot(
            zone_id=zid, zone=gd.zones.get(zid) or f'Area {zid}', areas=sorted(areas), names=names, skill=skill,
            shares=shares, coverage=coverage, dungeon=gamedata.is_instance(gd, zid)))
    for rows in spots.values():
        rows.sort(key=lambda s: (bool(s.names), s.names))
    return spots


def pool_items(cf: ClassicFishing) -> dict[int, list[str]]:
    """item -> names of the fishing pools that can contain it."""
    out: dict[int, set] = {}
    for p in cf.pools.values():
        for item in expected_items(p['loot'], cf.refs):
            out.setdefault(item, set()).add(p['name'])
    return {k: sorted(v) for k, v in out.items()}


def observations(angler: dict | None, activity: dict | None) -> dict[str, Obs]:
    """Your fishing logs per zone name. The two addons can log the same catches, so the larger log is used for
    counts (never the sum); timing comes only from ForeverMoneyBridge, casts and getaways only from ForeverAngler."""
    out: dict[str, Obs] = {}
    for zone, z in ((angler or {}).get('zones') or {}).items():
        if not isinstance(z, dict) or not int(z.get('c') or 0):
            continue
        fish = z.get('fish') if isinstance(z.get('fish'), dict) else {}
        out[zone] = Obs(zone=zone, casts=int(z.get('c') or 0), caught=int(z.get('k') or 0), escaped=int(z.get('e') or 0),
                        items={int(k): int(v) for k, v in fish.items()}, sources=['ForeverAngler'])
    for zone, acts in (activity or {}).items():
        a = (acts or {}).get('fishing') if isinstance(acts, dict) else None
        if not a or not int(a.get('loots') or 0):
            continue
        o = out.setdefault(zone, Obs(zone=zone))
        loots = int(a['loots'])
        o.seconds, o.timed_catches = float(a.get('seconds') or 0), loots
        if loots > o.caught:
            o.caught = loots
            o.items = {int(k): int(v) for k, v in (a.get('items') or {}).items()}
        o.sources.append('ForeverMoneyBridge')
    return out


@dataclass
class CatchModel:
    landed_share: float | None       # (caught + got away) / casts over all your logs: 1 - miss rate
    keep_by_zone: dict[str, float]   # measured 1 - got-away rate per zone (enough data only)
    keep_by_skill: dict[int, float]  # measured, pooled by Classic zone skill
    casts_per_hour: float
    pace_source: str                 # always 'setting' (your own time is never used)

    def keep(self, zone: str, zone_skill: int | None, skill: int, use_zone: bool = True) -> tuple[float, str]:
        """Share of hooked fish you keep: always the game's rule, your effective fishing skill (skill + pole, gear and
        lure bonus) against the zone's skill. Never your own logs (user's rule, 2026-11-14): keep_by_zone/skill are
        shown for comparison only."""
        if zone_skill is None:
            return 1.0, 'zone skill unknown; assuming nothing gets away'
        return (success_chance(skill, zone_skill),
                f'game rule: your effective skill {skill} vs the zone\'s {zone_skill} (zone skill from WoW Classic)')

    def catches_per_hour(self, keep: float) -> float:
        # every cast is assumed to be clicked in time: your own miss rate (bites you didn't click, early recasts)
        # depends on how closely you watched, like your time, so it is shown but not used (user, 2026-11-14)
        return self.casts_per_hour * keep


def catch_model(obs: dict[str, Obs], zone_skill_of, setting_casts: float) -> CatchModel:
    casts = sum(o.casts for o in obs.values())
    landed = sum(o.caught + o.escaped for o in obs.values() if o.casts)
    landed_share = min(1.0, landed / casts) if casts >= 50 else None
    keep_by_zone, pooled = {}, {}
    for o in obs.values():
        if not o.casts:
            continue
        hooked = o.caught + o.escaped
        if hooked >= MIN_RATE_SAMPLE:
            keep_by_zone[o.zone] = o.caught / hooked
        zs = zone_skill_of(o.zone)
        if zs is not None:
            k, h = pooled.get(zs, (0, 0))
            pooled[zs] = (k + o.caught, h + hooked)
    keep_by_skill = {zs: k / h for zs, (k, h) in pooled.items() if h >= MIN_RATE_SAMPLE}
    # Pace is always the casts-per-hour setting. Your logged time is never used: time in a zone includes travel,
    # questing and breaks, so it is not a farming rate (user's rule, 2026-11-14).
    return CatchModel(landed_share, keep_by_zone, keep_by_skill, setting_casts, 'setting')
