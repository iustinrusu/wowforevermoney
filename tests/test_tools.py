"""Tools you keep and use (the Salt Shaker): read from ItemEffect, and their craft rows. Money in copper.

The user's question (2026-11-19): why isn't Cured Rugged Hide profitable with Leatherworking 255 and a Salt Shaker?
The Salt Shaker turns Deeprock Salt (3s 13c) into Refined Deeprock Salt (57g listed) once every 71 hours, but it is an
item you use, not a recipe, so the app never saw it and costed Refined Deeprock Salt at the AH price only.
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from wfm import gamedata
from wfm.engine import Engine
from wfm.gamedata import GameData, Item, Recipe
from wfm.questie import QuestieDB
from wfm.skillup import SkillUpData

SHAKER, SALT, REFINED, HIDE, CURED, ESSENCE, BRILLIANCE = 15846, 8150, 15409, 8171, 15407, 10938, 242269
LW = 165
HOURS_71 = 71 * 3600 * 1000


def item(iid, name, sell=0, cls=7, sub=0, req_skill=0, rank=0):
    return Item(id=iid, name=name, quality=1, item_level=50, req_level=0, sell_price=sell, buy_price=0, stack=20,
                class_id=cls, subclass_id=sub, bonding=0, req_skill=req_skill, req_skill_rank=rank)


class ToolTableTests(unittest.TestCase):
    def test_tools_from_item_effects(self):
        gd = GameData(build='test')
        gd.professions = {LW: 'Leatherworking'}
        for it in (item(SHAKER, 'Salt Shaker', 7500, cls=0, req_skill=LW, rank=250), item(SALT, 'Deeprock Salt'),
                   item(REFINED, 'Refined Deeprock Salt'), item(ESSENCE, 'Lesser Magic Essence', req_skill=LW),
                   item(BRILLIANCE, 'Brilliance', req_skill=LW, rank=280), item(1, 'Quest Thing')):
            gd.items[it.id] = it
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            # TriggerType 0 = on use; Charges -1 = used up (single use); the essence's use consumes the essence itself
            (folder / 'ItemEffect.csv').write_text(
                'ID,LegacySlotIndex,TriggerType,Charges,CoolDownMSec,CategoryCoolDownMSec,SpellCategoryID,SpellID\n'
                f'100917,0,0,0,0,{HOURS_71},791,19566\n'
                '2,0,0,0,0,0,0,13361\n'
                '3,0,0,-1,-1,-1,0,1232054\n'
                '4,0,0,0,0,0,0,999\n'
                '5,0,1,0,0,0,0,19566\n', encoding='utf-8')
            (folder / 'ItemXItemEffect.csv').write_text(
                f'ID,ItemEffectID,ItemID\n1,100917,{SHAKER}\n2,2,{ESSENCE}\n3,3,{BRILLIANCE}\n4,4,1\n', encoding='utf-8')
            creates = {19566: (REFINED, 1.0), 13361: (2, 1.0), 1232054: (3, 1.0), 999: (4, 1.0)}
            reagents = {19566: [(SALT, 1)], 13361: [(ESSENCE, 2)], 1232054: [(SALT, 15)], 999: [(SALT, 1)]}
            out = gamedata.tool_recipes(folder, gd, creates, reagents, {19566: 'Salt Shaker'}, set())
        self.assertEqual(len(out), 1)                       # essence (uses itself), single use, no profession: out
        r = out[0]
        self.assertEqual((r.tool_id, r.product_id, r.reagents, r.profession, r.min_rank), (SHAKER, REFINED, [(SALT, 1)],
                                                                                       'Leatherworking', 250))
        self.assertEqual(r.cooldown_ms, 255_600_000)        # 71 hours, the Forever tooltip's "2 Days, 23 Hrs"

    def test_older_caches_without_the_tables_load_no_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gamedata.tool_recipes(Path(tmp), GameData(build='t'), {}, {}, {}, set()), [])


def world(bags=None, lw=255):
    """Prices from the user's TSM data, 2026-11-19 (Refined Deeprock Salt 57g listed, Deeprock Salt 3s 13c)."""
    gd = GameData(build='test')
    for it in (item(SHAKER, 'Salt Shaker', 7500, cls=0, req_skill=LW, rank=250), item(SALT, 'Deeprock Salt', 250, sub=7),
               item(REFINED, 'Refined Deeprock Salt', 1000, sub=7), item(HIDE, 'Rugged Hide', 500, sub=6),
               item(CURED, 'Cured Rugged Hide', 500, sub=6)):
        gd.items[it.id] = it
    shaker = Recipe(spell_id=19566, name='Salt Shaker', profession='Leatherworking', skill_line=LW, product_id=REFINED,
                    product_count=1, reagents=[(SALT, 1)], trivial_low=0, trivial_high=0, min_rank=250,
                    cooldown_ms=HOURS_71, tool_id=SHAKER)
    cure = Recipe(spell_id=19047, name='Cured Rugged Hide', profession='Leatherworking', skill_line=LW,
                  product_id=CURED, product_count=2, reagents=[(HIDE, 1), (REFINED, 1)], trivial_low=225,
                  trivial_high=235, min_rank=1)
    gd.recipes = [shaker, cure]
    prices = {SALT: {'numAuctions': 339, 'minBuyout': 313, 'marketValue': 313, 'regionSale': 265,
                     'regionMarketValue': 368, 'regionSoldPerDay': 428.0, 'regionSalePercent': 0.649},
              REFINED: {'numAuctions': 12, 'minBuyout': 570089, 'marketValue': 487364, 'regionSale': 538598,
                        'regionMarketValue': 419787, 'regionSoldPerDay': 16.856, 'regionSalePercent': 0.602},
              HIDE: {'numAuctions': 117, 'minBuyout': 520, 'marketValue': 2153, 'regionSale': 528,
                     'regionMarketValue': 2261, 'regionSoldPerDay': 161.9, 'regionSalePercent': 0.291},
              CURED: {'numAuctions': 42, 'minBuyout': 309999, 'marketValue': 273758, 'regionSale': 293330,
                      'regionMarketValue': 241202, 'regionSoldPerDay': 10.584, 'regionSalePercent': 0.392},
              SHAKER: {'numAuctions': 53, 'minBuyout': 29000, 'marketValue': 37360, 'regionSale': 33060,
                       'regionMarketValue': 63631, 'regionSoldPerDay': 9.9, 'regionSalePercent': 0.45}}
    su = SkillUpData(thresholds={19047: [0, 225, 230, 235]})
    w = SimpleNamespace(gamedata=gd, prices=prices, questie=QuestieDB(items={SALT: {'npcDrops': [1]}}, npcs={}),
                        skillup=su, angler=None)
    if bags is not None:
        w.syndicator = {'k': {'name': 'Testchar', 'equipped': {}}}
        w.inventory = {'k': bags}
    settings = {'gold': 100, 'ah_cut': 0.05, 'market_share': 0.2, 'faction': 'H', 'min_sold_per_day': 0.5,
                'professions': {'Leatherworking': lw}, 'character': 'Testchar-PvP', 'sale_price_basis': 'realm'}
    return w, settings


class ToolRowTests(unittest.TestCase):
    def rows(self, **kw):
        w, s = world(**kw)
        e = Engine(w, s)
        return e, {o.key: o for o in e.crafts()}

    def test_the_salt_shaker_row_when_you_have_one(self):
        e, rows = self.rows(bags={SHAKER: 1})
        o = rows['craft:19566']
        self.assertEqual(o.title, 'Salt Shaker: make Refined Deeprock Salt')
        # 57g 0s 89c listed, after the 5% cut: 541,584; minus one Deeprock Salt at 313 -> 541,271 a use
        self.assertEqual(o.profit_unit, int(570089 * 0.95) - 313)
        self.assertAlmostEqual(o.units_day, round(24 / 71, 2))          # once every 71 hours
        self.assertEqual(o.daily, int(o.profit_unit * 24 / 71))           # 18g 29s 64c a day
        self.assertTrue(o.doable)
        self.assertEqual((o.detail['skill_required'], o.detail['skill_exact']), (250, True))
        self.assertNotIn('unverified_recipe', o.flags)                  # game data, not SkillUpForever
        self.assertEqual(o.detail['learn']['how'], 'tool')
        self.assertTrue(o.detail['learn']['owned'])
        self.assertIn('use your Salt Shaker', o.detail['recipe'])

    def test_without_the_tool_or_the_skill(self):
        _, rows = self.rows(bags={})
        o = rows['craft:19566']
        self.assertFalse(o.doable)
        self.assertIn('needs_tool', o.flags)
        self.assertIn('Get a Salt Shaker', o.needs)
        self.assertEqual(o.detail['learn']['cost'], 29000)               # 2g 90s on the AH, once
        _, rows = self.rows(bags={SHAKER: 1}, lw=240)
        self.assertFalse(rows['craft:19566'].doable)
        self.assertIn('Leatherworking 250', rows['craft:19566'].needs)
        _, rows = self.rows()                                             # no Syndicator: can't tell
        self.assertIn('tool_unchecked', rows['craft:19566'].flags)
        self.assertTrue(rows['craft:19566'].doable)

    def test_cured_rugged_hide_points_at_the_shaker(self):
        _, rows = self.rows(bags={SHAKER: 1})
        o = rows['craft:19047']
        salt = next(m for m in o.detail['mats'] if m['item_id'] == REFINED)
        self.assertEqual(salt['unit'], 570089)               # what selling it gives up is still its price
        self.assertEqual(salt['made_with']['key'], 'craft:19566')
        self.assertEqual(salt['made_with']['cooldown_hours'], 71.0)

    def test_the_shaker_does_not_make_deeprock_salt_valuable(self):
        e, _ = self.rows(bags={SHAKER: 1})
        self.assertNotIn(SALT, e.best_uses())                 # 3s 13c on the AH: the profit is the tool's row
        farm = {o.item_id for o in e.gathering(e.best_uses())}
        self.assertNotIn(REFINED, farm)                       # only the Salt Shaker makes it: nothing to farm
        self.assertIn(SALT, farm)


if __name__ == '__main__':
    unittest.main()
