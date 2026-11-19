"""Locate the WoW: Forever install, its addons and this app's data folder."""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
WEB = ROOT / 'web'

_CANDIDATES = [
    Path(r'C:\Games\World of Warcraft'),
    Path(r'C:\Program Files (x86)\World of Warcraft'),
    Path(r'C:\Program Files\World of Warcraft'),
    Path(r'D:\World of Warcraft'),
    Path(r'D:\Games\World of Warcraft'),
]


def find_wow_dir(configured: str | None = None) -> Path | None:
    if configured and Path(configured).exists():
        return Path(configured)
    cfg = Path(os.environ.get('APPDATA', '')) / 'tradeskillmaster' / 'TSM.cfg'
    if cfg.exists():
        m = re.search(r'"wowPath"\s*:\s*"([^"]+)"', cfg.read_text(encoding='utf-8', errors='replace'))
        if m:
            p = Path(m.group(1).replace('\\\\', '\\'))
            if p.exists():
                return p
    return next((p for p in _CANDIDATES if (p / '_forever_').exists()), None)


class GamePaths:
    def __init__(self, wow_dir: Path):
        self.wow = wow_dir
        self.flavor = wow_dir / '_forever_'
        self.addons = self.flavor / 'Interface' / 'AddOns'
        self.wtf = self.flavor / 'WTF'

    @property
    def tsm_appdata(self) -> Path:
        return self.addons / 'TradeSkillMaster_AppHelper' / 'AppData.lua'

    @property
    def questie_toc(self) -> Path:
        return self.addons / 'QuestieDB' / 'QuestieDB_Forever.toc'

    @property
    def questie_drops(self) -> Path:
        return self.addons / 'QuestieDB' / 'support' / 'Forever' / 'DropTables' / 'classicItemDrops.lua'

    @property
    def skillup_data(self) -> Path:
        return self.addons / 'SkillUpForever' / 'Data'

    @property
    def foreverrecipes_data(self) -> Path:
        return self.addons / 'ForeverRecipes' / 'Data'

    def hotfix_cache(self) -> Path | None:
        """The client's cache of data sent by the server (Cache/ADB/<locale>/DBCache.bin)."""
        adb = self.flavor / 'Cache' / 'ADB'
        for loc in ('enUS', 'enGB'):
            p = adb / loc / 'DBCache.bin'
            if p.exists():
                return p
        found = sorted(adb.glob('*/DBCache.bin')) if adb.exists() else []
        return found[0] if found else None

    def client_build(self) -> str | None:
        """Version of the installed Forever client, e.g. 1.60.1.70938."""
        info = self.wow / '.build.info'
        if not info.exists():
            return None
        lines = info.read_text(encoding='utf-8', errors='replace').splitlines()
        if not lines:
            return None
        header = [h.split('!')[0] for h in lines[0].split('|')]
        for line in lines[1:]:
            row = dict(zip(header, line.split('|')))
            if row.get('Product') == 'wowf' and row.get('Active') == '1':
                return row.get('Version')
        return None

    def account_savedvariables(self) -> list[Path]:
        return sorted(p for p in (self.wtf / 'Account').glob('*/SavedVariables') if p.is_dir())

    def character_savedvariables(self) -> list[Path]:
        return sorted(p for p in (self.wtf / 'Account').glob('*/*/*/SavedVariables') if p.is_dir())

    def addon_version(self, addon: str) -> str | None:
        for toc in sorted((self.addons / addon).glob('*.toc')):
            m = re.search(r'^## Version:\s*(.+)$', toc.read_text(encoding='utf-8', errors='replace'), re.M)
            if m:
                return m.group(1).strip()
        return None
