"""Your characters, detected from saved addon data, so settings fill themselves in.

Sources, best first:
  1. ForeverMoneyBridge (our addon): level, gold, faction, professions, last played character,
     and loot by zone/activity with active time.
  2. TradeSkillMaster's SavedVariables: gold and professions per character (no level).
Manual settings are used for anything not detected.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .lua import parse_assignments

ADDON_NAME = 'ForeverMoneyBridge'
_TSM_KEY = re.compile(r'^s@(.+?) - (Horde|Alliance) - (.+?)@internalData@(money|playerProfessions)$')


def read_tsm_characters(path: Path | None) -> dict[str, dict]:
    if not path or not path.exists():
        return {}
    data = parse_assignments(path.read_text(encoding='utf-8', errors='replace')).get('TradeSkillMasterDB') or {}
    chars: dict[str, dict] = {}
    for key, value in data.items():
        m = _TSM_KEY.match(str(key))
        if not m:
            continue
        name_realm, faction, realm, field = m.groups()
        c = chars.setdefault(name_realm, {'name': name_realm, 'faction': faction, 'realm': realm, 'source': 'TSM'})
        if field == 'money':
            c['money'] = int(value or 0)
        elif isinstance(value, dict):
            c['professions'] = {p: {'rank': int(v.get('level') or 0), 'max': int(v.get('maxLevel') or 0)}
                                for p, v in value.items() if isinstance(v, dict) and 'level' in v}
    return chars


def read_bridge(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    return parse_assignments(path.read_text(encoding='utf-8', errors='replace')).get('ForeverMoneyBridgeDB') or {}


def build_profile(bridge: dict, tsm_chars: dict, char_mtimes: dict[str, float]) -> dict:
    """Merge sources into {characters: {...}, active: key, activity: {...}}."""
    chars: dict[str, dict] = {}
    for key, c in tsm_chars.items():
        chars[c['name']] = dict(c)
    def match(bridge_name: str) -> str:
        if bridge_name in chars:
            return bridge_name
        first = bridge_name.split(' ')[0]
        return next((n for n in chars if n.split(' ')[0] == first), bridge_name)

    for key, c in (bridge.get('characters') or {}).items():
        name = match(c.get('name') or key.split(' - ')[0])
        merged = chars.get(name, {})
        merged.update({k: v for k, v in c.items() if v is not None})
        merged['source'] = 'ForeverMoneyBridge'
        chars[name] = merged
    active = None
    last = bridge.get('lastCharacter')
    if last:
        active = match(last.split(' - ')[0])
    if not active and chars:
        # No addon data yet: guess your main = the character with the most profession skill. (The most recent
        # logout is a poor guess: it picked a level-1 alt in testing.) Last logout only breaks ties.
        def skill(n):
            return sum(int(p.get('rank') or 0) for p in (chars[n].get('professions') or {}).values())
        active = max(chars, key=lambda n: (skill(n), char_mtimes.get(n, 0)))
    return {'characters': chars, 'active': active, 'activity': bridge.get('activity') or {},
            'vendors': bridge.get('vendors') or {}, 'containers': bridge.get('containers') or {},
            'has_bridge': bool(bridge), 'active_guessed': not last}


def apply(settings: dict, profile: dict) -> tuple[dict, dict]:
    """Return (effective settings, what was detected). Manual values are the fallback."""
    eff = dict(settings)
    detected: dict = {}
    auto = settings.get('auto_detect', True)
    chars = profile.get('characters') or {}
    name = settings.get('character') or profile.get('active')
    c = chars.get(name) if name else None
    if not auto or not c:
        return eff, detected
    detected['character'] = name
    detected['source'] = c.get('source')
    if c.get('level'):
        eff['level'] = detected['level'] = int(c['level'])
    if c.get('faction'):
        eff['faction'] = detected['faction'] = 'H' if c['faction'] == 'Horde' else 'A'
    if c.get('professions'):
        profs = {p: int(v.get('rank') or 0) for p, v in c['professions'].items()}
        detected['professions'] = profs
        if c.get('source') == 'ForeverMoneyBridge':
            eff['professions'] = profs          # the addon reads every skill line: a complete list
        else:
            # TSM only records crafting professions (no Fishing/Skinning), so add to your manual list.
            eff['professions'] = {**(settings.get('professions') or {}), **profs}
    detected['guessed'] = not settings.get('character') and profile.get('active_guessed', False)
    if 'money' in c:
        if settings.get('gold_scope', 'faction') == 'faction':
            total = sum(int(o.get('money') or 0) for o in chars.values() if o.get('faction') == c.get('faction'))
        else:
            total = int(c['money'])
        eff['gold'] = detected['gold'] = round(total / 10000, 4)
    return eff, detected


def install_addon(src: Path, addons_dir: Path, log=print) -> bool:
    """Copy our addon into WoW's AddOns folder if missing or older. Returns True if copied."""
    dest = addons_dir / ADDON_NAME
    src_toc, dest_toc = src / f'{ADDON_NAME}.toc', dest / f'{ADDON_NAME}.toc'
    ver = lambda p: (re.search(r'## Version:\s*(\S+)', p.read_text(encoding='utf-8')) or [None, ''])[1] if p.exists() else ''
    if dest_toc.exists() and ver(dest_toc) == ver(src_toc) and \
            all((dest / f.name).exists() and (dest / f.name).read_bytes() == f.read_bytes() for f in src.iterdir()):
        return False
    dest.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        shutil.copy2(f, dest / f.name)
    log(f'Installed {ADDON_NAME} {ver(src_toc)} into {dest}')
    return True
