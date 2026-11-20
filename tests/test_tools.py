"""Item uses (the Salt Shaker, essences, Darkmoon cards) and the tools recipes need. Money in copper.

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


GREATER, BALL, ACE, TWO, HAMMER, KNIFE = 10939, 23135, 31882, 31889, 5956, 9060


class ItemUseTableTests(unittest.TestCase):
    """ItemEffect (on use) spells that create items, read from tiny CSVs shaped like wago.tools' exports."""

    def load(self):
        gd = GameData(build='test')
        gd.professions = {LW: 'Leatherworking'}
        for it in (item(SHAKER, 'Salt Shaker', 7500, cls=0, req_skill=LW, rank=250), item(SALT, 'Deeprock Salt'),
                   item(REFINED, 'Refined Deeprock Salt'), item(ESSENCE, 'Lesser Magic Essence'),
                   item(GREATER, 'Greater Magic Essence'), item(BRILLIANCE, 'Brilliance', req_skill=LW, rank=280),
                   item(1, 'Quest Thing'), item(BALL, 'Heavy Leather Ball'), item(ACE, 'Ace of Beasts'),
                   item(TWO, 'Two of Beasts')):
            gd.items[it.id] = it
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            # TriggerType 0 = on use (1 = on equip: ignored); Charges -1 = used up, 0 = kept, 20 = twenty uses
            (folder / 'ItemEffect.csv').write_text(
                'ID,LegacySlotIndex,TriggerType,Charges,CoolDownMSec,CategoryCoolDownMSec,SpellCategoryID,SpellID\n'
                f'100917,0,0,0,0,{HOURS_71},791,19566\n'
                '2,0,0,-1,-1,-1,0,13361\n'
                '3,0,0,-1,-1,-1,0,13362\n'
                '4,0,0,-1,-1,-1,0,1232054\n'
                '5,0,0,0,0,0,0,999\n'
                '6,0,0,-1,-1,-1,0,23135\n'
                '7,0,0,0,0,0,0,23677\n'
                '8,0,1,0,0,0,0,555\n', encoding='utf-8')
            (folder / 'ItemXItemEffect.csv').write_text(
                f'ID,ItemEffectID,ItemID\n1,100917,{SHAKER}\n2,2,{ESSENCE}\n3,3,{GREATER}\n4,4,{BRILLIANCE}\n5,5,1\n'
                f'6,6,{BALL}\n7,7,{TWO}\n8,8,{SHAKER}\n', encoding='utf-8')
            creates = {19566: (REFINED, 1.0), 13361: (GREATER, 1.0), 13362: (ESSENCE, 3.0), 1232054: (3, 1.0),
                       999: (4, 1.0), 23135: (BALL, 1.0), 23677: (77, 1.0), 555: (5, 1.0)}
            reagents = {19566: [(SALT, 1)], 13361: [(ESSENCE, 2)], 1232054: [(SALT, 15)], 23677: [(ACE, 1), (TWO, 1)]}
            out = gamedata.item_use_recipes(folder, gd, creates, reagents, {19566: 'Salt Shaker'}, set())
        return {r.spell_id: r for r in out}

    def test_a_tool_you_keep(self):
        r = self.load()[19566]
        self.assertEqual((r.tool_id, r.use_item, r.product_id, r.reagents, r.profession, r.min_rank),
                         (SHAKER, 0, REFINED, [(SALT, 1)], 'Leatherworking', 250))
        self.assertEqual(r.cooldown_ms, 255_600_000)        # 71 hours, the Forever tooltip's "2 Days, 23 Hrs"

    def test_items_used_up_count_as_one_more_reagent(self):
        rs = self.load()
        up = rs[13361]                 # "Turn three lesser magic essences into a greater one": 1 used + 2 reagents
        self.assertEqual((up.use_item, up.tool_id, up.reagents, up.profession), (ESSENCE, 0, [(ESSENCE, 3)],
                                                                                   gamedata.NO_PROFESSION))
        down = rs[13362]               # "Turn a greater magic essence into three lesser ones"
        self.assertEqual((down.reagents, down.product_id, down.product_count), ([(GREATER, 1)], ESSENCE, 3.0))
        self.assertEqual(rs[1232054].reagents, [(SALT, 15), (BRILLIANCE, 1)])     # a single-use item
        self.assertEqual(rs[1232054].profession, 'Leatherworking')

    def test_combined_items_and_what_is_left_out(self):
        rs = self.load()
        deck = rs[23677]               # Darkmoon cards: the used card is one of the reagents, nothing extra
        self.assertEqual((deck.use_item, deck.tool_id, deck.reagents), (TWO, 0, [(ACE, 1), (TWO, 1)]))
        self.assertNotIn(999, rs)      # something from nothing, any time: not real
        self.assertNotIn(23135, rs)    # an item turned into itself
        self.assertNotIn(555, rs)      # on equip, not on use

    def test_older_caches_without_the_tables_load_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gamedata.item_use_recipes(Path(tmp), GameData(build='t'), {}, {}, {}, set()), [])

    def test_tools_a_recipe_needs(self):
        gd = GameData(build='test')
        gd.recipes = [Recipe(spell_id=17187, name='Transmute: Arcanite', profession='Alchemy', skill_line=171,
                             product_id=12360, product_count=1, reagents=[], trivial_low=0, trivial_high=0, min_rank=1)]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'SpellTotems.csv').write_text('ID,SpellID,RequiredTotemCategoryID_0,RequiredTotemCategoryID_1,'
                                                    'Totem_0,Totem_1\n1,17187,12,0,0,0\n', encoding='utf-8')
            (folder / 'TotemCategory.csv').write_text(
                'ID,Name_lang,TotemCategoryType,TotemCategoryMask\n12,"Philosopher\'s Stone",22,1\n'
                '161,"Gnomish Army Knife",24,127\n162,"Blacksmith Hammer",24,4\n165,"Mining Pick",24,8\n'
                '375,"Runed Golden Rod",3,7\n377,"Runed Arcanite Rod",3,31\n', encoding='utf-8')
            gamedata.add_tools_needed(folder, gd)
        self.assertEqual(gd.recipes[0].tools_needed, (12,))
        self.assertTrue(gamedata.tool_fits(gd, 161, 162))      # a Gnomish Army Knife is a Blacksmith Hammer
        self.assertTrue(gamedata.tool_fits(gd, 377, 375))      # an Arcanite rod does what a Golden rod does
        self.assertFalse(gamedata.tool_fits(gd, 375, 377))
        self.assertFalse(gamedata.tool_fits(gd, 162, 165))     # a hammer is not a pick


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


LESSER_ETERNAL, GREATER_ETERNAL, PHILO, PHILO_CAT, ARCANITE, THORIUM, CRYSTAL = 16202, 16203, 9149, 12, 12360, 12359, 12363


class MoreInteractionTests(unittest.TestCase):
    """Essence splits (no profession), recipe tools, and poisons' level requirement (2026-11-19 survey)."""

    def world(self, bags=None, level=50, poisons=230):
        gd = GameData(build='test')
        for it in (item(LESSER_ETERNAL, 'Lesser Eternal Essence', sub=12), item(GREATER_ETERNAL, 'Greater Eternal Essence', sub=12),
                   item(PHILO, "Philosopher's Stone", cls=0), item(ARCANITE, 'Arcanite Bar'), item(THORIUM, 'Thorium Bar'),
                   item(CRYSTAL, 'Arcane Crystal'), item(2892, 'Deadly Poison', cls=0), item(5173, 'Deathweed'),
                   item(3372, 'Leaded Vial')):
            gd.items[it.id] = it
        gd.items[PHILO].totem_category = PHILO_CAT
        gd.totem_categories = {PHILO_CAT: ("Philosopher's Stone", 22, 1)}
        gd.recipes = [
            Recipe(spell_id=20040, name='Lesser Eternal Essence', profession=gamedata.NO_PROFESSION, skill_line=0,
                   product_id=LESSER_ETERNAL, product_count=3, reagents=[(GREATER_ETERNAL, 1)], trivial_low=0,
                   trivial_high=0, min_rank=1, use_item=GREATER_ETERNAL),
            Recipe(spell_id=17187, name='Transmute: Arcanite', profession='Alchemy', skill_line=171, product_id=ARCANITE,
                   product_count=1, reagents=[(THORIUM, 1), (CRYSTAL, 1)], trivial_low=275, trivial_high=300,
                   min_rank=1, tools_needed=(PHILO_CAT,)),
            Recipe(spell_id=2835, name='Deadly Poison', profession='Poisons', skill_line=40, product_id=2892,
                   product_count=1, reagents=[(5173, 1), (3372, 1)], trivial_low=175, trivial_high=225, min_rank=1)]
        # the user's TSM data, 2026-11-19: a Greater Eternal Essence at 27g, Lesser ones at 10g 42s
        p = lambda mb, spd: {'numAuctions': 20, 'minBuyout': mb, 'marketValue': mb, 'regionSale': mb,
                             'regionMarketValue': mb, 'regionSoldPerDay': spd, 'regionSalePercent': 0.5}
        prices = {GREATER_ETERNAL: p(269990, 105.5), LESSER_ETERNAL: p(104230, 175.1), ARCANITE: p(442400, 36.8),
                  THORIUM: p(4000, 500), CRYSTAL: p(86500, 32), 2892: p(1000, 13.5), 5173: p(100, 100), 3372: p(50, 100)}
        su = SkillUpData(thresholds={17187: [275, 275, 282, 290], 2835: [130, 175, 200, 225]},
                         level_required={2835: 30}, requirement_known={17187, 2835})
        w = SimpleNamespace(gamedata=gd, prices=prices, questie=QuestieDB(), skillup=su, angler=None)
        if bags is not None:
            w.syndicator = {'k': {'name': 'Testchar', 'equipped': {}}}
            w.inventory = {'k': bags}
        s = {'gold': 1000, 'ah_cut': 0.05, 'market_share': 0.2, 'faction': 'H', 'min_sold_per_day': 0.5,
             'professions': {'Alchemy': 300, 'Poisons': poisons}, 'character': 'Testchar-PvP', 'level': level,
             'sale_price_basis': 'realm'}
        e = Engine(w, s)
        return e, {o.key: o for o in e.crafts()}

    def test_nothing_only_a_recipe_makes_gets_a_farm_row(self):
        # review 2026-11-20: "Farm Arcanite Bar" showed 341g a day as Mining (only a transmute makes it)
        e, _ = self.world(bags={})
        e.gd.items[ARCANITE].subclass_id = 7                 # Metal & Stone: the kind "Farm" rows look at
        farm = {o.item_id: o for o in e.gathering(e.best_uses())}
        self.assertNotIn(ARCANITE, farm)
        self.assertIn(GREATER_ETERNAL, farm)            # essences: disenchanting gives them, splitting only converts
        self.assertIn(LESSER_ETERNAL, farm)
        # a source of its own brings it back: a mob that drops it (QuestieDB)
        e.q.items[ARCANITE] = {'npcDrops': [1234]}
        self.assertIn(ARCANITE, {o.item_id for o in e.gathering(e.best_uses())})

    def test_node_spots_use_gatherlite_counts_and_your_level(self):
        # review 2026-11-20: Winterspring mining showed as doable for a level 42; GatherLite often knows more nodes
        from unittest import mock
        from wfm import nodes as nodes_mod
        HERB, NODE, ZONE = 2447, 1618, 618
        gd = GameData(build='test')
        gd.items[HERB] = item(HERB, 'Peacebloom', sub=9, sell=10)
        gd.zones = {ZONE: 'Winterspring'}
        mobs = {100 + i: {'name': f'Mob {i}', 'minLevel': 55, 'maxLevel': 56, 'spawns': {ZONE: [[1, 1]]}} for i in range(12)}
        q = QuestieDB(items={HERB: {'objectDrops': [NODE]}},
                      objects={NODE: {'name': 'Peacebloom', 'spawns': {ZONE: [[1, 1], [2, 2], [3, 3]]}}}, npcs=mobs)
        prices = {HERB: {'numAuctions': 5, 'minBuyout': 500, 'marketValue': 500, 'regionSoldPerDay': 50,
                         'regionSalePercent': 0.5, 'regionSale': 500}}
        w = SimpleNamespace(gamedata=gd, prices=prices, questie=q, skillup=SkillUpData(), angler=None,
                            gatherlite={'nodes': {NODE: {ZONE: 20}}})
        s = {'gold': 1000, 'ah_cut': 0.05, 'market_share': 0.2, 'faction': 'H', 'professions': {'Herbalism': 300},
             'level': 50}
        with mock.patch.object(nodes_mod, 'load_or_build', lambda ids, log=print: {}):
            e = Engine(w, s)
            self.assertEqual(e.zone_level(ZONE), 55.5)
            spot = next(o for o in e.node_spots({}) if o.kind == 'herb_spot')
            self.assertEqual(spot.detail['node_count'], 20)               # GatherLite's 20, not QuestieDB's 3
            self.assertFalse(spot.doable)                                 # mobs 55+, you are 50
            self.assertIn('zone_above_you', spot.flags)
            self.assertEqual(spot.needs, 'Level 52+ (most mobs here are level 55+; you are 50)')
            spot = next(o for o in Engine(w, {**s, 'level': 53}).node_spots({}) if o.kind == 'herb_spot')
            self.assertTrue(spot.doable)                                  # 55 is within 3 levels of 53

    def test_splitting_a_greater_essence_is_a_flip_anyone_can_do(self):
        e, rows = self.world(bags={})
        o = rows['craft:20040']
        self.assertEqual(o.title, 'Turn 1 Greater Eternal Essence into 3 Lesser Eternal Essence')
        self.assertTrue(o.doable)
        self.assertEqual(o.profit_unit, 3 * int(104230 * 0.95) - 269990)    # 297,054 - 269,990 = 27,064 (2g 70s)
        self.assertEqual(o.detail['learn']['how'], 'item use')
        # and a Greater Eternal Essence is worth what its three Lesser ones sell for
        self.assertEqual(e.best_uses()[GREATER_ETERNAL]['doable_value'], 3 * int(104230 * 0.95))

    def test_a_recipe_tool_you_lack(self):
        _, rows = self.world(bags={})
        o = rows['craft:17187']
        self.assertFalse(o.doable)
        self.assertIn('needs_tool', o.flags)
        self.assertEqual(o.needs, "Get a Philosopher's Stone (once: you keep it)")
        self.assertEqual(o.detail['tools'][0]['have'], False)
        _, rows = self.world(bags={PHILO: 1})
        self.assertTrue(rows['craft:17187'].doable)
        self.assertNotIn('needs_tool', rows['craft:17187'].flags)
        _, rows = self.world()                                       # bags not read: shown, with a doubt
        self.assertIn('tool_unchecked', rows['craft:17187'].flags)

    def test_poisons_are_crafts_with_a_level_to_learn_them(self):
        _, rows = self.world(bags={})
        o = rows['craft:2835']
        self.assertTrue(o.doable)
        self.assertEqual((o.detail['skill_required'], o.detail['skill_exact']), (130, True))
        _, rows = self.world(bags={}, level=25)
        self.assertFalse(rows['craft:2835'].doable)
        self.assertIn('Level 30', rows['craft:2835'].needs)
        _, rows = self.world(bags={}, poisons=100)
        self.assertIn('Poisons 130', rows['craft:2835'].needs)


class TsmVendorPriceTests(unittest.TestCase):
    """TSM is the king for prices (the user, 2026-11-19): its VendorSell and VendorBuy, read in game, beat the files."""

    def test_vendor_sell_from_tsm_beats_the_game_files(self):
        gd = GameData(build='test')
        gd.items = {1: item(1, 'New Forever Item', sell=999), 2: item(2, 'Checked Item', sell=50), 3: item(3, 'Other', sell=7)}
        gd.items[1].source, gd.items[1].untrusted = 'server-new', ('sell_price',)
        gd.items[2].source = 'in-game'
        rep = gamedata.apply_tsm_vendor(gd, {'sell': {1: 120, 2: 50, '3': 7}, 'buy': {5: 10}, 'at': 1795000000})
        self.assertEqual(gd.items[1].sell_price, 120)                    # the hotfix cache said 999
        self.assertNotIn('sell_price', gd.items[1].untrusted)
        self.assertTrue(gd.items[1].sell_from_tsm)
        self.assertEqual((rep['sell'], rep['buy']), (3, 1))
        self.assertEqual(rep['differ'], [(1, 'New Forever Item', 999, 120, 'server-new')])

    def test_tsm_against_your_clients_checks(self):
        # A4 (2026-11-19): TSM matched the client on 2,966 of 2,969; 3 were 5% low after a server change
        gd = GameData(build='test')
        gd.items = {1: item(1, 'Grovekeeper Leggings', sell=35696), 2: item(2, 'Checked Same', sell=50),
                    3: item(3, 'Old Hide', sell=7)}
        for i in (1, 2):
            gd.items[i].source = 'in-game'
        gd.items[1].checked = {'against': 'server-new', 'differs': [], 'at': 1795000000}
        rep = gamedata.apply_tsm_vendor(gd, {'sell': {1: 33997, 2: 50, 3: 9}, 'at': 1795200000})
        self.assertEqual(gd.items[1].sell_price, 35696)                  # your client's check wins over TSM
        self.assertEqual(gd.items[3].sell_price, 9)                      # TSM wins over the game files
        self.assertEqual(rep['client_same'], 1)
        self.assertEqual(rep['client_differ'], [(1, 'Grovekeeper Leggings', 35696, 33997, 1795000000)])
        self.assertEqual(rep['differ'], [(3, 'Old Hide', 7, 9, 'client')])

    def test_checks_go_where_tsm_and_the_files_disagree(self):
        import time
        from wfm.world import World
        w = World.__new__(World)
        gd = GameData(build='test')
        gd.items = {i: item(i, f'Item {i}', sell=10) for i in range(1, 9)}
        w.gamedata, w.tooltips = gd, {}
        w.prices = {4: {'minBuyout': 100}, 5: {'minBuyout': 100}}
        now = time.time()
        w.profile = {'item_info': {'1': {'n': 'Item 1', 't': now - 5 * 86400}, '2': {'n': 'Item 2', 't': now - 86400},
                                   '8': {'n': 'Item 8', 't': now - 86400}}}
        # 1 and 2: checked, TSM now differs (5 days ago: check again; yesterday: not yet); 3-6: TSM vs the files
        w.tsm_vendor_report = {'client_differ': [(1, 'Item 1', 10, 9, now - 5 * 86400), (2, 'Item 2', 10, 9, now - 86400)],
                               'differ': [(3, 'Item 3', 10, 500, 'client'), (4, 'Item 4', 10, 12, 'server-new'),
                                          (5, 'Item 5', 10, 900, 'server-new'), (6, 'Item 6', 10, 11, 'client')]}
        self.assertEqual(w.recheck_ids(), [1])
        # the AH-priced ones first, the biggest difference first
        self.assertEqual(w.source_disagreements(), [1, 5, 4, 3, 6])
        got = w.item_checks_wanted(set(), limit=5)
        self.assertEqual(got, [1, 5, 4, 3, 6])                          # 1 again though checked this week; 2 and 8 not

    def test_the_data_health_check_reads_plainly(self):
        from types import SimpleNamespace
        from wfm.audit import vendor_price_check
        gd = GameData(build='test')
        gd.items = {1: item(1, 'Checked', sell=35696), 2: item(2, 'From TSM', sell=9), 3: item(3, 'Files Only', sell=3)}
        gd.items[1].source, gd.items[2].sell_from_tsm = 'in-game', True
        w = SimpleNamespace(gamedata=gd, RECHECK_DAYS=3, profile={'tsm_vendor': {'buy': {5: 9}}},
                            tsm_vendor_report={'sell': 2, 'buy': 1, 'client_same': 2966,
                                               'client_differ': [(1, 'Checked', 35696, 33997, 0)],
                                               'differ': [(2, 'From TSM', 7, 9, 'client')]},
                            source_grades={('client', 'sell_price'): {'checked': 1173, 'wrong': 51},
                                           ('server-new', 'sell_price'): {'checked': 2011, 'wrong': 340},
                                           ('client', 'quality'): {'checked': 1173, 'wrong': 0}})
        gd.items[5] = item(5, 'Coal')
        gd.items[5].buy_price = 500
        c = vendor_price_check(w)
        self.assertEqual(c['status'], 'info')
        self.assertIn('On the 2,967 items your client checked, TSM agreed on 2,966; the game files were wrong on 391 of '
                      '3,184 (the client tables 51 of 1,173, the hotfix cache (new items) 340 of 2,011)', c['detail'])
        self.assertIn('1 items have a vendor price from them alone', c['detail'])
        self.assertIn('1 are below', c['detail'])
        self.assertEqual(c['examples'][:3], ['Checked (1): your client 35696c, TSM 33997c',
                                             'Files Only (3): only the game files (the client tables), 3c',
                                             'From TSM (2): game file 7c (the client tables), TSM 9c'])
        self.assertEqual(vendor_price_check(SimpleNamespace(gamedata=gd, tsm_vendor_report={}))['status'], 'warn')

    def test_vendor_buy_order(self):
        e = MoreInteractionTests().world()[0]
        q = QuestieDB(items={THORIUM: {'vendors': [100]}}, npcs={100: {'name': 'Trader', 'friendlyToFaction': 'AH', 'zoneID': 1}})
        e.q = e.w.questie = q
        e._vendor_cache.clear(); e._vendor_flags.clear()                  # built before the vendor existed
        e.gd.items[THORIUM].buy_price = 5000                              # the game file
        self.assertEqual(e.vendor_price(THORIUM)[0], 5000)
        self.assertIn('vendor_price_unconfirmed', e.vendor_flags(THORIUM))
        e._vendor_cache.clear(); e._vendor_flags.clear()
        e.w.profile = {'tsm_vendor': {'buy': {THORIUM: 4800}}}           # TSM's merchant record wins
        self.assertEqual(e.vendor_price(THORIUM)[0], 4800)
        self.assertIn('vendor_price_tsm', e.vendor_flags(THORIUM))


class DisenchantTests(unittest.TestCase):
    """Disenchanting from ForeverRecipes' Classic table (the user's yes to a labelled fallback, 2026-11-19)."""
    GREEN, DUST, ESSENCE_, CLOTH = 4240, 10940, 10938, 2996

    def world(self, enchanting=None):
        from wfm.foreverrecipes import ForeverRecipesData
        gd = GameData(build='test')
        green = Item(id=self.GREEN, name='Woolen Bag Thing', quality=2, item_level=12, req_level=7, sell_price=100,
                     buy_price=0, stack=1, class_id=4, subclass_id=1, bonding=2)
        for it in (green, item(self.DUST, 'Strange Dust', sub=12), item(self.ESSENCE_, 'Lesser Magic Essence', sub=12),
                   item(self.CLOTH, 'Bolt of Linen Cloth', sub=5)):
            gd.items[it.id] = it
        gd.recipes = [Recipe(spell_id=2385, name='Brown Linen Vest', profession='Tailoring', skill_line=197,
                             product_id=self.GREEN, product_count=1, reagents=[(self.CLOTH, 1)], trivial_low=40,
                             trivial_high=80, min_rank=1)]
        fr = ForeverRecipesData(de_profiles={1: [(self.ESSENCE_, 0.2, 1, 2), (self.DUST, 0.8, 1, 2)]},
                                de_items={self.GREEN: 1})
        p = lambda mb, spd: {'numAuctions': 20, 'minBuyout': mb, 'marketValue': mb, 'regionSale': mb,
                             'regionMarketValue': mb, 'regionSoldPerDay': spd, 'regionSalePercent': 0.5}
        prices = {self.DUST: p(1000, 300), self.ESSENCE_: p(2000, 200), self.CLOTH: p(300, 500), self.GREEN: p(400, 5)}
        chars = {'Enchy-PvP': {'professions': {'Enchanting': {'rank': enchanting}}}} if enchanting else {}
        w = SimpleNamespace(gamedata=gd, prices=prices, questie=QuestieDB(), angler=None, forever_recipes=fr,
                            skillup=SkillUpData(thresholds={2385: [1, 40, 60, 80]}), profile={'characters': chars})
        s = {'gold': 1000, 'ah_cut': 0.05, 'market_share': 0.2, 'faction': 'H', 'min_sold_per_day': 0.5,
             'professions': {'Tailoring': 100}, 'sale_price_basis': 'realm'}
        return Engine(w, s)

    def test_value_and_who_can_do_it(self):
        e = self.world(enchanting=3)
        d = e.disenchant(self.GREEN)
        # 0.2 x 1.5 Lesser Magic Essence at 1,900 + 0.8 x 1.5 Strange Dust at 950 (after the cut) = 570 + 1,140
        self.assertEqual(d['value'], 1710)
        self.assertEqual((d['skill'], d['can'], d['enchanter'], d['enchanter_skill']), (1, True, 'Enchy', 3))
        self.assertIsNone(self.world().disenchant(self.GREEN)['enchanter'])
        v = e.valuer().value(self.GREEN)
        self.assertEqual(v.channel, 'AH')                 # a Classic table never decides the best way
        self.assertIn('disenchant_more', v.flags)
        self.assertEqual(v.disenchant['value'], 1710)

    def test_craft_to_disenchant_row_is_labelled_and_never_a_top_pick(self):
        e = self.world(enchanting=3)
        rows = {o.key: o for o in e.crafts()}
        o = rows['craft_de:2385']
        self.assertEqual(o.title, 'Craft Woolen Bag Thing and disenchant it')
        self.assertEqual(o.profit_unit, 1710 - 300)
        self.assertIn('classic_disenchant', o.flags)
        self.assertTrue(o.doable)
        self.assertEqual(rows['craft:2385'].profit_unit, 380 - 300)      # selling it: 400 - 5%
        top = e.top_picks(list(rows.values()))
        self.assertNotIn('craft_de:2385', top['now'] + top['slow'] + top['level_up'])
        o = {x.key: x for x in self.world().crafts()}['craft_de:2385']     # nobody can disenchant
        self.assertFalse(o.doable)
        self.assertIn('Enchanting 1~', o.needs)


if __name__ == '__main__':
    unittest.main()
