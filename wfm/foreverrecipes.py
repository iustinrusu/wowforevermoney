"""Read the ForeverRecipes addon's data (the user installed it 2026-11-19): the main source of Forever recipe facts
since 2026-11-19 (the user: "make skillupforever optional so I can delete the addon"; see merged()).

Its tables are generated from the Forever client (build 1.60.1.70938 in version 1.17.1) plus the author's own
observations and frozen Classic reference data (CMaNGOS), GPL-3.0; read here from the user's install, never copied.
What the app uses:
- skill colours [orange, yellow, green, grey] with `requirementKnown`: SkillUpForever stores 0/1 as the orange
  threshold when it doesn't know it (Cured Rugged Hide: the app guessed 185; ForeverRecipes says 225), and has no
  rogue Poisons at all; ForeverRecipes has both. SkillUpForever stays first where it knows; the two are compared on
  Data health.
- the character level a recipe needs (`levelRequired`, Poisons: Instant Poison II at 30)
- trainer fees and the skill the trainer asks for (Poisons: Instant Poison II costs 1g at Poisons 130)
- what disenchanting an item gives (Data/Disenchant.lua; the user's yes, 2026-11-19, as a labelled fallback): its own
  words call these "independently reconstructed Classic baseline estimates ... not verified Forever yields", so the
  app labels them "Classic table" everywhere and never lets them into Top picks or the plan
- where each recipe is learned (2026-11-19, the user: the levelling path "should be with all recipes in game, and
  where to get them or learn them"): trainers, the recipe item and who sells it (price, limited stock), who drops it
  (the top 5 recorded chances, in %), chests, quests (Sources.lua, Npcs.lua). Its author marks some of it as Classic
  reference data (CMaNGOS): the page says "ForeverRecipes" on every source row.
Not used yet: Merchant's Favor items as a currency.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

from .lua import parse_assignments
from .skillup import SkillUpData


@dataclass
class ForeverRecipesData:
    recipes: dict[int, dict] = field(default_factory=dict)     # spell -> {skill_line, thresholds, reagents, product, count}
    meta: dict[int, dict] = field(default_factory=dict)        # spell -> {levelRequired, requirementKnown, ...}
    trainers: dict[int, list] = field(default_factory=dict)    # spell -> [(npc, copper, skill)]
    automatic: set[int] = field(default_factory=set)           # learned with the profession
    source_build: str | None = None
    # disenchanting (Classic reference): profile -> [(material, chance, min, max)] or None (unsupported)
    de_profiles: dict[int, list | None] = field(default_factory=dict)
    de_rules: list[tuple] = field(default_factory=list)        # (class, subclass or -1, quality, min ilvl, max ilvl, profile)
    de_items: dict[int, int | None] = field(default_factory=dict)   # item -> profile, None = can't be estimated
    de_eligible: set[int] = field(default_factory=set)
    de_excluded: set[int] = field(default_factory=set)
    # where recipes come from (Sources.lua, Npcs.lua)
    teach: dict[int, list] = field(default_factory=dict)          # spell -> recipe items that teach it
    sellers: dict[int, list] = field(default_factory=dict)        # recipe item -> [npc]
    vendor_costs: dict[int, dict] = field(default_factory=dict)   # recipe item -> {npc: "200 copper" / "40 Merchant's Favor"}
    drops: dict[int, list] = field(default_factory=dict)          # recipe item -> [(npc, chance in %)], top 5 recorded
    other_drops: dict[int, list] = field(default_factory=dict)    # recipe item -> [(chest or container, chance % or None)]
    quest_rewards: dict[int, list] = field(default_factory=dict)  # recipe item -> [quest]
    auto_quests: dict[int, list] = field(default_factory=dict)    # spell -> [quest that teaches it]
    source_meta: dict[int, dict] = field(default_factory=dict)    # spell -> {limitedStockVendors, trainerQuests}
    binding: dict[int, str] = field(default_factory=dict)         # recipe item -> 'none' (tradeable) / 'onPickup'
    npcs: dict[int, tuple] = field(default_factory=dict)          # npc -> (name, faction 'A' / 'H' / '', zone, x, y)
    quests: dict[int, dict] = field(default_factory=dict)         # quest -> {name, level, side, start, zone}


def _seq(t) -> list:
    """A Lua array as a list, whether the parser gave a list or a dict with 1..n keys (and named extras)."""
    if isinstance(t, list):
        return t
    if isinstance(t, dict):
        n = max((k for k in t if isinstance(k, int)), default=0)
        return [t.get(i) for i in range(1, n + 1)]
    return []


def load(data_dir: Path) -> ForeverRecipesData:
    out = ForeverRecipesData()
    rec_path, src_path = data_dir / 'Recipes.lua', data_dir / 'Sources.lua'
    if rec_path.exists():
        text = rec_path.read_text(encoding='utf-8', errors='replace')
        m = re.search(r'client build\s*([\d.]+)', text)
        out.source_build = m.group(1) if m else None
        d = parse_assignments(text)
        for spell, row in (d.get('Recipes') or {}).items():
            if not isinstance(row, list) or len(row) < 4:
                continue
            reag = row[2] or []
            product = row[3] or [0, 1]
            out.recipes[int(spell)] = {
                'skill_line': int(row[0]), 'thresholds': [int(x) for x in (row[1] or [])],
                'reagents': [(int(reag[i]), int(reag[i + 1])) for i in range(0, len(reag) - 1, 2)],
                'product': int(product[0]) if product else 0, 'count': float(product[1]) if len(product) > 1 else 1.0}
        out.meta = {int(k): v for k, v in (d.get('RecipeMeta') or {}).items() if isinstance(v, dict)}
        for spell, row in (d.get('Recipes') or {}).items():
            row = _seq(row)
            items = [int(i) for i in _seq((d.get('RecipeItems') or {}).get(spell)) if i]
            if len(row) > 4 and row[4]:
                items = [int(row[4])] + [i for i in items if i != int(row[4])]
            if items:
                out.teach[int(spell)] = items
    if src_path.exists():
        d = parse_assignments(src_path.read_text(encoding='utf-8', errors='replace'))
        for spell, rows in (d.get('Trainers') or {}).items():
            out.trainers[int(spell)] = [(int(r[0]), int(r[1]), int(r[2])) for r in rows or []
                                        if isinstance(r, list) and len(r) >= 3]
        out.automatic = {int(k) for k, v in (d.get('AutomaticRecipes') or {}).items() if v}
        ints = lambda v: [int(x) for x in _seq(v) if isinstance(x, (int, float))]
        out.sellers = {int(k): ints(v) for k, v in (d.get('Sellers') or {}).items()}
        out.vendor_costs = {int(k): {int(n): str(c) for n, c in v.items()} for k, v in
                            (d.get('RecipeVendorCosts') or {}).items() if isinstance(v, dict)}
        out.drops = {int(k): [(int(r[0]), float(r[1]) if isinstance(r[1], (int, float)) else None)
                              for r in map(_seq, _seq(v)) if len(r) >= 2 and r[0]]
                     for k, v in (d.get('Drops') or {}).items()}
        out.other_drops = {int(k): [(str(r.get('name')), r.get('chance') if isinstance(r.get('chance'), (int, float))
                                     else None) for r in _seq(v) if isinstance(r, dict) and r.get('name')]
                           for k, v in (d.get('OtherDrops') or {}).items()}
        out.quest_rewards = {int(k): ints(v) for k, v in (d.get('QuestRewards') or {}).items()}
        out.auto_quests = {int(k): ints(v) for k, v in (d.get('AutomaticQuests') or {}).items()}
        out.source_meta = {int(k): v for k, v in (d.get('SourceMeta') or {}).items() if isinstance(v, dict)}
        out.binding = {int(k): str(v) for k, v in (d.get('RecipeItemBinding') or {}).items()}
    npc_path = data_dir / 'Npcs.lua'
    if npc_path.exists():
        d = parse_assignments(npc_path.read_text(encoding='utf-8', errors='replace'))
        for nid, row in (d.get('Npcs') or {}).items():
            row = _seq(row)
            if not row:
                continue
            loc = _seq(row[2]) if len(row) > 2 else []
            out.npcs[int(nid)] = (str(row[0]), row[1] if len(row) > 1 and isinstance(row[1], str) else '',
                                  str(loc[0]) if loc else '', loc[2] if len(loc) > 3 else None,
                                  loc[3] if len(loc) > 3 else None)
        names, metas = d.get('Quests') or {}, d.get('QuestMeta') or {}
        for qid in set(names) | set(metas):
            m = metas.get(qid) or {}
            starts = _seq(m.get('starts')) or ([m['start']] if isinstance(m.get('start'), dict) else [])
            first = starts[0] if starts and isinstance(starts[0], dict) else {}
            out.quests[int(qid)] = {'name': m.get('name') or (_seq(names.get(qid)) or [f'Quest {qid}'])[0],
                                    'level': m.get('requiredLevel'), 'side': m.get('side'),
                                    'start': first.get('name'), 'zone': (first.get('location') or {}).get('zone')}
    de_path = data_dir / 'Disenchant.lua'
    if de_path.exists():
        d = parse_assignments(de_path.read_text(encoding='utf-8', errors='replace'))
        for pid, rows in (d.get('DisenchantProfiles') or {}).items():
            out.de_profiles[int(pid)] = None if rows is False else [
                (int(r[0]), float(r[1]), int(r[2]), int(r[3])) for r in rows or [] if isinstance(r, list) and len(r) >= 4]
        rules = d.get('DisenchantRules') or []
        if isinstance(rules, dict):
            rules = [rules[k] for k in sorted(rules)]
        out.de_rules = [tuple(int(x) for x in r[:6]) for r in rules if isinstance(r, list) and len(r) >= 6]
        for iid, v in (d.get('DisenchantItems') or {}).items():
            out.de_items[int(iid)] = int(v[0]) if isinstance(v, list) and v and v[0] else None
        out.de_eligible = {int(k) for k, v in (d.get('DisenchantEligible') or {}).items() if v}
        out.de_excluded = {int(k) for k, v in (d.get('DisenchantExcluded') or {}).items() if v}
    return out


def _copper(text) -> int | None:
    """'200 copper' -> 200; a cost in another currency (Merchant's Favor, tokens) -> None."""
    m = re.fullmatch(r'\s*([\d,]+) copper\s*', text or '')
    return int(m.group(1).replace(',', '')) if m else None


def sources(fr: ForeverRecipesData | None, spell: int, faction: str | None = None) -> dict | None:
    """Where a recipe is learned, from ForeverRecipes: trainers (fee, skill they ask for), the recipe items, who sells
    them (price, limited stock), who drops them (top 5 recorded chances, %), chests and containers, quests. faction
    'A' / 'H': the other faction's trainers, vendors and quests are left out."""
    if not fr:
        return None
    ok = lambda n: not faction or (fr.npcs.get(n) or ('', ''))[1] in ('', faction)

    def place(n):
        name, f, zone, x, y = fr.npcs.get(n) or (f'NPC {n}', '', '', None, None)
        return {'npc': n, 'name': name, 'zone': zone, 'x': x, 'y': y}
    meta = fr.source_meta.get(spell) or {}
    out = {'automatic': spell in fr.automatic, 'trainers': [], 'items': list(fr.teach.get(spell) or []),
           'sold_by': [], 'dropped_by': [], 'other_drops': [], 'quests': [], 'tradeable': None}
    for npc, cost, skill in fr.trainers.get(spell) or []:
        if ok(npc):
            q = (meta.get('trainerQuests') or {}).get(npc)
            out['trainers'].append(dict(place(npc), cost=cost, skill=skill,
                                        quest=(fr.quests.get(q) or {}).get('name') if q else None))
    limited = meta.get('limitedStockVendors') or {}
    quests = list(fr.auto_quests.get(spell) or [])
    for it in out['items']:
        costs = fr.vendor_costs.get(it) or {}
        for npc in fr.sellers.get(it) or []:
            if ok(npc):
                text = costs.get(npc)
                out['sold_by'].append(dict(place(npc), item=it, cost_text=text, copper=_copper(text),
                                           limited=bool((limited.get(it) or {}).get(npc))))
        out['dropped_by'] += [dict(place(n), item=it, chance=c) for n, c in fr.drops.get(it) or []]
        out['other_drops'] += [{'name': n, 'chance': c, 'item': it} for n, c in fr.other_drops.get(it) or []]
        quests += fr.quest_rewards.get(it) or []
        if it in fr.binding:
            out['tradeable'] = bool(out['tradeable']) or fr.binding[it] == 'none'
    for q in dict.fromkeys(quests):
        qm = fr.quests.get(q) or {}
        side = str(qm.get('side') or '')
        if faction and side in ('Alliance', 'Horde') and side[0] != faction:
            continue
        out['quests'].append({'id': q, 'name': qm.get('name') or f'Quest {q}', 'level': qm.get('level'),
                              'start': qm.get('start'), 'zone': qm.get('zone')})
    out['dropped_by'].sort(key=lambda r: -(r['chance'] or 0))
    out['sold_by'].sort(key=lambda r: (r['copper'] is None, r['copper'] or 0, r['zone'], r['name']))
    return out


def find_how(src: dict | None) -> str:
    """How you'd get a recipe that can't be bought with gold now: 'vendor' (another currency), 'quest', 'drop' or
    '' (no source known)."""
    if not src:
        return ''
    if src['sold_by']:
        return 'vendor'
    if src['quests']:
        return 'quest'
    return 'drop' if src['dropped_by'] or src['other_drops'] else ''


def disenchant_profile(fr: ForeverRecipesData | None, iid: int, class_id: int, subclass_id: int, quality: int,
                       item_level: int) -> tuple[int | None, str]:
    """Which disenchant profile an item has, as ForeverRecipes works it out (Crafting.lua ResolveDEProfile): its own
    per-item list first, else the rules by class, subclass, quality and item level (first match). Only weapons and
    armour of green quality or better can be disenchanted."""
    if not fr or not fr.de_profiles:
        return None, 'no data'
    if iid in fr.de_excluded:
        return None, 'excluded'
    if iid in fr.de_items:
        pid = fr.de_items[iid]
        return (pid, 'ok') if pid and fr.de_profiles.get(pid) else (None, 'unsupported')
    if class_id not in (2, 4) or quality < 2:
        return None, 'ineligible'
    if quality > 4 or iid not in fr.de_eligible:
        return None, 'unsupported'
    for cls, sub, q, lo, hi, pid in fr.de_rules:
        if cls == class_id and sub in (-1, subclass_id) and q == quality and lo <= item_level <= hi:
            return (pid, 'ok') if pid and fr.de_profiles.get(pid) else (None, 'unsupported')
    return None, 'unsupported'


def disenchant_materials(fr: ForeverRecipesData | None, profile: int | None) -> list[tuple]:
    """[(material, chance, min, max)] for a profile; empty if unknown. Chances are not normalised: a profile can
    include getting nothing."""
    if not fr or not profile:
        return []
    return list(fr.de_profiles.get(profile) or [])


# Enchanting skill needed to disenchant, by item level: the WoW Classic rule (not in ForeverRecipes' data, not checked
# for Forever), labelled "estimated" wherever it is shown. Green and blue items:
DE_SKILL = [(20, 1), (25, 25), (30, 50), (35, 75), (40, 100), (45, 125), (50, 150), (55, 175), (60, 200), (65, 225)]


def disenchant_skill(quality: int, item_level: int) -> int:
    if quality >= 4:                       # epics: 225 up to item level 60, 300 above (estimate)
        return 225 if item_level <= 60 else 300
    for top, skill in DE_SKILL:
        if item_level <= top:
            return skill
    return 275


def merged(su: SkillUpData | None, fr: ForeverRecipesData | None) -> SkillUpData:
    """The recipe facts the app uses (a new object; the inputs are not changed).

    ForeverRecipes first (the user, 2026-11-19: "make skillupforever optional so I can delete the addon"; ForeverRecipes
    will keep being updated, so a gap in it now is fine). Its validated list decides which recipes can be learned in
    Forever, with their colours, the skill and character level they need and the trainer fee (the cheapest trainer's).
    SkillUpForever, when installed, only fills gaps: the required skill where ForeverRecipes doesn't know it, a fee it
    lacks, limited stock at other vendors, its vendor price list, the profession ranks. A recipe only SkillUpForever
    lists is left out, so the app shows the same with or without it: its list is every recipe in the client's tables
    (307 of its 315 extra recipes on 2026-11-19 had products that never sell in Forever's region). Without
    ForeverRecipes, SkillUpForever alone is used as before.
    - required skill known with an orange of 0 or 1: Poisons need no skill to craft once learned, so it is raised to
      the skill the trainer asks for, the real gate (Instant Poison II: Poisons 130); a starting recipe keeps 1
    - required skill unknown to both: orange 0, and the engine estimates it (yellow - 40), flagged
    - limited stock: ForeverRecipes marks pattern vendors limited without a count: 1 a restock (SkillUpForever's count
      where it has one; it said 1 for 246 of the 254 it counts)
    Provenance: `requirement_known` (spells whose required skill is exact), `from_forever_recipes` (whose colours came
    from ForeverRecipes), `from_skillup` (whose required skill came from SkillUpForever)."""
    su = su or SkillUpData()
    out = copy.copy(su)
    out.thresholds = dict(su.thresholds)
    out.trainer_fees = dict(su.trainer_fees)
    out.limited_stock = {k: dict(v) for k, v in (su.limited_stock or {}).items()}
    out.requirement_known = {s for s, th in su.thresholds.items() if th and th[0] and th[0] > 1}
    out.level_required, out.from_forever_recipes, out.from_skillup = {}, set(), set()
    if not fr or not fr.recipes:
        return out
    out.thresholds, out.requirement_known, fees = {}, set(), {}
    for spell, r in fr.recipes.items():
        meta = fr.meta.get(spell) or {}
        th = r['thresholds']
        trainers = fr.trainers.get(spell) or []
        if trainers:
            cost, skill = min((c, s) for _, c, s in trainers)
            fees[spell] = [cost, skill]
        if meta.get('levelRequired'):
            out.level_required[spell] = int(meta['levelRequired'])
        theirs = su.thresholds.get(spell)
        theirs_known = bool(theirs and len(theirs) >= 4 and theirs[0] and theirs[0] > 1)
        if len(th) < 4 or meta.get('thresholdsKnown') is False:      # colours unknown to ForeverRecipes
            if theirs and len(theirs) >= 4:
                out.thresholds[spell] = [int(x) for x in theirs[:4]]
                if theirs_known:
                    out.requirement_known.add(spell)
                    out.from_skillup.add(spell)
            continue
        if meta.get('requirementKnown'):
            orange = th[0]
            if orange <= 1 and trainers:
                orange = min(s for _, _, s in trainers)              # learnable from this skill on
            orange = max(1, orange)
            out.requirement_known.add(spell)
        elif theirs_known:
            orange = int(theirs[0])
            out.requirement_known.add(spell)
            out.from_skillup.add(spell)
        else:
            orange = 0                                               # unknown: the engine estimates it
        out.thresholds[spell] = [orange, th[1], th[2], th[3]]
        out.from_forever_recipes.add(spell)
    out.trainer_fees.update(fees)                                    # ForeverRecipes' fee first
    for m in fr.source_meta.values():
        lim = m.get('limitedStockVendors') if isinstance(m, dict) else None
        for it, npcs in (lim.items() if isinstance(lim, dict) else []):
            for npc, on in ((npcs or {}).items() if isinstance(npcs, dict) else []):
                if on:
                    out.limited_stock.setdefault(int(it), {}).setdefault(int(npc), 1)
    return out


def compare(su: SkillUpData, fr: ForeverRecipesData | None) -> dict:
    """SkillUpForever vs ForeverRecipes on the recipes both have: how many agree on the colours, and the differences."""
    same, diff = 0, []
    for spell, th in su.thresholds.items():
        r = (fr.recipes.get(spell) if fr else None)
        if not r or len(r['thresholds']) < 4 or not th or len(th) < 4:
            continue
        a, b = [int(x) for x in th[1:4]], r['thresholds'][1:4]      # yellow, green, grey (orange is often unknown)
        if a == b:
            same += 1
        else:
            diff.append((spell, a, b))
    only_fr = sorted(set(fr.recipes) - set(su.thresholds)) if fr else []
    return {'both': same + len(diff), 'same': same, 'diff': diff, 'only_forever_recipes': only_fr}
