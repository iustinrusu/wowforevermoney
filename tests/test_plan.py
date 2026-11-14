"""Plan for today (wfm/plan.py): checked against hand-worked numbers. All money in copper. Names are made up."""
import unittest
from types import SimpleNamespace

from wfm import plan
from wfm.engine import Engine, Opportunity
from wfm.gamedata import Item
from tests.test_engine import SETTINGS, make_world

SHARE, CUT, TV = 0.2, 0.05, 50000        # time value 5g an hour


def holding(iid, name, count, value, channel='AH', cls=7, sub=0, quality=1, spd=100.0, rate=0.8, flags=(),
            liq=(), reagent=False, stack=20, contents=(), locked=False, in_mail=0):
    return {'item_id': iid, 'name': name, 'quality': quality, 'class_id': cls, 'subclass_id': sub, 'stack': stack,
            'count': count, 'in_mail': in_mail, 'value': value, 'channel': channel, 'flags': list(flags),
            'confidence': 1.0, 'sold_per_day': spd, 'sale_rate': rate, 'liquidity_flags': list(liq),
            'locked': locked, 'reagent': reagent, 'contents': list(contents)}


def opp(kind, key, title, profit, cost=0, units=1.0, daily=None, gph=None, flags=(), doable=True, **detail):
    d = {'confidence': 1.0}
    d.update(detail)
    return Opportunity(kind=kind, key=key, item_id=1, title=title, profit_unit=profit, cost_unit=cost,
                       units_day=units, daily=int(profit * units) if daily is None else daily, gph=gph,
                       doable=doable, flags=list(flags), detail=d)


class CashInTests(unittest.TestCase):
    def test_ah_vendor_and_open_piles(self):
        hs = [holding(1, 'Thick Hide', 30, 500, spd=50),            # 50 a day x 20% x 2 days = 20 to list, keep 10
              holding(2, 'Cracked Tusk', 4, 120, channel='vendor', quality=0),
              holding(3, 'Sturdy Trunk', 2, 30000, channel='open', flags=['open_it'], contents=['Silk Cloth']),
              holding(4, 'Old Boots', 1, 900, channel='vendor', cls=4)]   # gear: maybe yours, not junk
        acts = {a['type']: a for a in plan.cash_in(hs, SHARE, CUT)}
        ah = acts['cash_ah']
        self.assertEqual(ah['gain'], 20 * 500)
        self.assertEqual((ah['items'][0]['count'], ah['items'][0]['have']), (20, 30))
        self.assertEqual(ah['items'][0]['list_at'], round(500 / 0.95))      # leaves 500 after the cut
        self.assertIn('keep the rest', ah['why'])
        # 20 stackable units = 4 posts x 1.25 listings per sale (sale rate 0.8) x 10 s, plus 1 minute at the AH
        self.assertAlmostEqual(ah['minutes'], round(1 + 4 * 1.25 * 10 / 60, 1))
        self.assertEqual(acts['cash_vendor']['gain'], 4 * 120)
        self.assertEqual(acts['cash_open']['gain'], 60000)
        self.assertEqual(acts['cash_open']['title'], 'Open your 2 Sturdy Trunk')

    def test_items_that_barely_sell_are_not_listed(self):
        hs = [holding(1, 'Odd Gem', 3, 5000, liq=['hard_to_sell']), holding(2, 'Thing', 1, 100, liq=['no_sales_data'])]
        self.assertEqual(plan.cash_in(hs, SHARE, CUT), [])

    def test_things_you_use_are_named_but_not_counted(self):
        hs = [holding(1, 'Instant Poison', 29, 300, cls=0, sub=8),
              holding(2, 'Healing Potion', 2, 700, cls=0, sub=1),
              holding(3, 'Flash Powder', 15, 60, cls=15, sub=1),
              holding(4, 'Skinning Knife', 1, 95, cls=2, sub=14),
              holding(5, 'Raw Winter Squid', 40, 250, cls=0, sub=5, reagent=True),   # food in the data, but a material
              holding(6, 'Jungle Stew', 11, 355, cls=0, sub=5)]                      # food nothing is made from
        ah = plan.cash_in(hs, SHARE, CUT)[0]
        self.assertEqual([i['name'] for i in ah['items']], ['Raw Winter Squid'])
        self.assertEqual(ah['gain'], 40 * 250)
        self.assertIn('29 Instant Poison', ah['why'])
        self.assertIn('Not counted', ah['why'])

    def test_ended_auctions_mean_collect_the_mail(self):
        ah = plan.cash_in([holding(1, 'Black Pearl', 2, 1615, in_mail=2)], SHARE, CUT, ended_auctions=7)[0]
        self.assertIn('7 of your auctions have ended', ah['why'])

    def test_character_key_matches_on_name(self):
        syn = {'Bob-Realm': {'name': 'Bob'}, 'Ann-Realm': {'name': 'Ann'}}
        self.assertEqual(plan.character_key(syn, 'Ann'), 'Ann-Realm')
        self.assertIsNone(plan.character_key(syn, ''))


class FinishTests(unittest.TestCase):
    def test_time_cost_drops_tiny_actions(self):
        tiny = plan._action('cash_vendor', 'Sell junk', '', gain=1000, minutes=2)        # 10s vs 1s 66c of time
        good = plan._action('routine', 'Flip', '', gain=30000, minutes=5, key='a')
        kept = plan.finish([tiny, good], TV)
        self.assertEqual([a['title'] for a in kept], ['Flip'])
        self.assertEqual(kept[0]['value'], 30000 - int(5 / 60 * TV))
        self.assertEqual(kept[0]['per_hour'], 30000 * 12)

    def test_each_type_is_capped_and_keys_are_not_repeated(self):
        acts = [plan._action('farm', f'Farm {i}', '', gain=100000 - i, minutes=60, key=f'f{i}') for i in range(3)]
        acts += [plan._action('routine', f'R{i}', '', gain=50000 - i, minutes=5, key=f'r{i}') for i in range(5)]
        acts.append(plan._action('big_flip', 'Same row again', '', gain=40000, minutes=3, key='r0'))
        kept = plan.finish(acts, TV)
        types = [a['type'] for a in kept]
        self.assertEqual(types.count('farm'), 1)
        self.assertEqual(types.count('routine'), 3)
        self.assertNotIn('Same row again', [a['title'] for a in kept])

    def test_selected_by_value_and_shown_by_gold_per_hour(self):
        acts = [plan._action('farm', 'Farm', '', gain=100000, minutes=60, key='f'),            # value 5g, 10g/h
                plan._action('routine', 'Quick flip', '', gain=20000, minutes=4, key='r')]      # value ~1g 67s, 30g/h
        kept = plan.finish(acts, TV)
        self.assertEqual([a['title'] for a in kept], ['Quick flip', 'Farm'])
        self.assertEqual([a['rank'] for a in kept], [1, 2])

    def test_confidence_lowers_the_value(self):
        a = plan._action('snipe', 'Snipe', '', gain=80000, minutes=2, confidence=0.45, key='s')
        self.assertEqual(plan.finish([a], TV)[0]['value'], int(80000 * 0.45) - int(2 / 60 * TV))


class BuildTests(unittest.TestCase):
    def test_classic_yield_rows_never_appear(self):
        herb = opp('herb_spot', 'herb:1', 'Herbs in Zone A', 50, gph=200000, flags=['classic_yields'])
        skin = opp('skin_spot', 'skin:1', 'Skin in Zone B', 50, gph=90000, flags=['wowhead_forever'])
        p = plan.build([herb, skin], {'hourly': ['herb:1', 'skin:1']}, {}, TV, SHARE, CUT, 0)
        self.assertEqual([a['key'] for a in p['actions']], ['skin:1'])
        self.assertFalse(p['holdings_found'])

    def test_cooldown_action_only_with_the_profession(self):
        mine = opp('craft', 'craft:1', 'Craft Arcane Bar', 300000, cost=100000, units=0.5, recipe='Transmute: Bar',
                   cooldown_hours=47, cooldown_group='Transmute', mats=[], sell_channel='AH', sell_price=420000)
        theirs = opp('craft', 'craft:2', 'Craft Moon Cloth', 200000, units=0.25, doable=False, flags=['other_profession'],
                     recipe='Moon Cloth', cooldown_hours=95, mats=[])
        quick = opp('craft', 'craft:3', 'Craft Gold Bar', 5000, units=24, cooldown_hours=1, mats=[])
        acts = plan.cooldowns([mine, theirs, quick])
        self.assertEqual([a['key'] for a in acts], ['craft:1'])
        self.assertEqual(acts[0]['gain'], 300000)
        self.assertIn('every 47 hours', acts[0]['why'])

    def test_one_per_shared_cooldown(self):
        a = opp('craft', 'craft:1', 'Craft A', 300000, cooldown_hours=47, cooldown_group='Transmute', mats=[])
        b = opp('craft', 'craft:2', 'Craft B', 200000, cooldown_hours=23, cooldown_group='Transmute', mats=[])
        self.assertEqual([x['key'] for x in plan.cooldowns([a, b])], ['craft:1'])

    def test_routine_instruction_names_vendor_and_price(self):
        o = opp('vendor_flip', 'vflip:9', 'Buy Jungle Wine from vendor, sell on AH', 1410, cost=300, units=11.37,
                vendors=[{'name': 'Trader Bo', 'zone': 'Stranglethorn Vale', 'coords': [27.1, 77.4], 'event': False,
                          'located': True}], ah_sell=1800, sold_per_day=57, effort={'minutes': 3.6, 'cost': 3000})
        a = plan.routine(o, TV)
        self.assertEqual(a['title'], 'Buy 11 Jungle Wine from Trader Bo (Stranglethorn Vale 27, 77) at 3s 0c each; '
                                     'list at 18s 0c each')
        self.assertEqual((a['gain'], a['minutes'], a['gold_needed']), (o.daily, 3.6, int(300 * 11.37)))

    def test_big_flip_counts_the_lower_profit_and_needs_a_gold(self):
        o = opp('vendor_flip', 'vflip:7', 'Buy Pattern: Big Gloves from vendor, sell on AH', 690000, cost=60000,
                units=0.26, profit_at_avg_sale=320000, vendors=[])
        a = plan.big_flip(o)
        self.assertEqual(a['gain'], 320000)
        self.assertIn('one every 3.8 days', a['why'])
        small = opp('vendor_flip', 'vflip:8', 'Buy Cheap Pattern from vendor, sell on AH', 9000, units=0.5, vendors=[])
        self.assertIsNone(plan.big_flip(small))

    def test_engine_run_includes_the_plan(self):
        r = Engine(make_world({}), dict(SETTINGS)).run()
        self.assertIn('actions', r['plan'])
        self.assertFalse(r['plan']['holdings_found'])

    def test_engine_values_your_bags_for_the_plan(self):
        w = make_world({1: {'numAuctions': 4, 'minBuyout': 1000, 'marketValue': 1000, 'regionSale': 1000,
                            'regionSoldPerDay': 50, 'regionSalePercent': 0.8}})
        w.gamedata.items[1] = Item(id=1, name='Thick Hide', quality=1, item_level=30, req_level=0, sell_price=10,
                                   buy_price=0, stack=20, class_id=7, subclass_id=6, bonding=0)
        w.syndicator = {'Kel-Realm': {'name': 'Kel', 'mail': {}, 'auctions': [{'item': 1, 'count': 2, 'expires': 5}]}}
        w.inventory = {'Kel-Realm': {1: 3}}
        w.profile = {'active': 'Kel'}
        e = Engine(w, dict(SETTINGS))
        h = e.my_holdings(e.valuer({}), now=10)
        self.assertTrue(h['found'])
        self.assertEqual(h['ended_auctions'], 1)
        row = h['items'][0]
        self.assertEqual((row['count'], row['in_mail'], row['channel'], row['value']), (5, 2, 'AH', 950))


if __name__ == '__main__':
    unittest.main()


class YourTimeIsNeverARate(unittest.TestCase):
    """User's rule (2026-11-14): time logged in a zone includes questing, travel and breaks, so your own logs never
    set a gold/hour or a pace; rates come from reported counts at the paces in Settings."""

    def world(self, activity):
        w = make_world({})
        w.profile = {'activity': activity}
        return w

    def test_loot_log_has_no_gold_per_hour(self):
        act = {'Marsh': {'mobs': {'loots': 40, 'seconds': 3600, 'items': {}}}}
        o = Engine(self.world(act), dict(SETTINGS)).activity_zones({})[0]
        self.assertIsNone(o.gph)
        self.assertEqual(o.flags[0], 'your_log')

    def test_logged_skinning_time_does_not_set_the_pace(self):
        from tests.test_skinning import SNAP
        act = {'Marsh': {'skinning': {'loots': 400, 'seconds': 3600, 'items': {}}}}    # 400 an hour logged
        w = self.world(act)
        w.forever_skinning = SNAP
        for iid, name, sell in ((2318, 'Light Leather', 600), (2319, 'Medium Leather', 1000)):
            w.gamedata.items[iid] = Item(id=iid, name=name, quality=1, item_level=20, req_level=0, sell_price=sell,
                                         buy_price=0, stack=20, class_id=7, subclass_id=6, bonding=0)
        s = dict(SETTINGS, kills_per_hour=60, level=40, professions={'Skinning': 300})
        rows = Engine(w, s).skinning_spots({})
        self.assertTrue(rows)
        for o in rows:
            self.assertEqual(o.detail['skins_per_hour'], 60)
            self.assertIn('assumed_kill_rate', o.flags)
            self.assertNotIn('measured_pace', o.flags)

    def test_time_value_comes_from_forever_farming_spots_not_your_log(self):
        act = {'Marsh': {'mobs': {'loots': 400, 'seconds': 600, 'items': {}}}}
        e = Engine(self.world(act), dict(SETTINGS))
        e.run()
        self.assertEqual((e.time_value, e.time_value_source), (20000, 'default'))


class FishingBonusFromYourThings(unittest.TestCase):
    """User's request (2026-11-14): the Fishing skill bonus is worked out from what you have in bags and bank."""

    def items(self, *ids):
        from wfm.fishing import FISHING_GEAR
        return {i: Item(id=i, name=FISHING_GEAR[i][0], quality=1, item_level=1, req_level=0, sell_price=1, buy_price=0,
                        stack=20, class_id=0, subclass_id=8, bonding=0) for i in ids}

    def test_best_pole_best_lure_and_gear(self):
        from wfm.fishing import skill_bonus
        items = self.items(6529, 6532, 6365, 6367, 19972)
        bonus, parts = skill_bonus({6529, 6532, 6365, 6367, 19972}, items)
        self.assertEqual(bonus, 75 + 20 + 5)       # Bright Baubles beats Shiny Bauble; Big Iron beats Strong
        self.assertEqual(parts, ['Bright Baubles +75', 'Big Iron Fishing Pole +20', 'Lucky Fishing Hat +5'])

    def test_best_lure_and_when_it_pays(self):
        from wfm.fishing import best_lure, lure_pays
        self.assertEqual(best_lure({6529, 6532, 6365}, self.items(6529, 6532, 6365)), (6532, 75))   # not the pole
        self.assertIsNone(best_lure({6365}, self.items(6365)))
        # 1s 50c a catch; the lure lifts catches from 120 to 200 an hour: +80 x 150c = 120s, vs 6 lures at 25s = 150s
        self.assertFalse(lure_pays(150, 120, 200, 15000))
        self.assertTrue(lure_pays(150, 120, 200, 6 * 1500))      # 6 lures at 15s = 90s < 120s: worth it
        self.assertFalse(lure_pays(150, 200, 200, 0))            # nothing gets away already: no lure, even free

    def test_engine_lure_cost_per_hour(self):
        w = make_world({6532: {'numAuctions': 4, 'minBuyout': 2400, 'marketValue': 2500}})
        w.gamedata.items.update(self.items(6532, 6366))
        w.syndicator = {'Kel-Realm': {'name': 'Kel', 'mail': {}, 'auctions': [], 'equipped': {6366: 1}}}
        w.inventory = {'Kel-Realm': {6532: 3}}
        w.profile = {'active': 'Kel'}
        lure = Engine(w, dict(SETTINGS)).fishing_lure()
        # Bright Baubles: 10 minutes each -> 6 an hour at the 24s lowest listing = 1g 44s an hour
        self.assertEqual((lure['name'], lure['bonus'], lure['cost_per_hour']), ('Bright Baubles', 75, 6 * 2400))
        self.assertIsNone(Engine(w, dict(SETTINGS, fishing_skill_bonus=40)).fishing_lure())   # typed bonus: unknown

    def test_a_value_not_confirmed_in_forever_says_so(self):
        from wfm.fishing import skill_bonus
        bonus, parts = skill_bonus({6366, 6530}, self.items(6366, 6530))
        self.assertEqual(bonus, 15 + 50)
        self.assertEqual(parts, ['Nightcrawlers +50', 'Darkwood Fishing Pole +15 (WoW Classic value)'])

    def test_an_id_with_another_name_in_forever_does_not_count(self):
        from wfm.fishing import skill_bonus
        items = self.items(6532)
        items[6532] = Item(id=6532, name='Something Else', quality=1, item_level=1, req_level=0, sell_price=1,
                           buy_price=0, stack=20, class_id=0, subclass_id=8, bonding=0)
        self.assertEqual(skill_bonus({6532}, items), (0, []))

    def test_engine_reads_bags_bank_and_equipped_unless_set(self):
        w = make_world({})
        w.gamedata.items.update(self.items(6530, 6366))
        w.syndicator = {'Kel-Realm': {'name': 'Kel', 'mail': {}, 'auctions': [], 'equipped': {6366: 1}}}
        w.inventory = {'Kel-Realm': {6530: 14}}
        w.profile = {'active': 'Kel'}
        bonus, source = Engine(w, dict(SETTINGS)).fishing_bonus()
        self.assertEqual(bonus, 50 + 15)          # Nightcrawlers in the bags + Darkwood pole in hand
        self.assertIn('Nightcrawlers +50', source)
        self.assertEqual(Engine(w, dict(SETTINGS, fishing_skill_bonus=10)).fishing_bonus(), (10, 'your setting'))


class PlanStepLinks(unittest.TestCase):
    """Plan steps carry their item's name and quality so the page links the name in the title to Wowhead."""

    def test_plan_steps_carry_the_item_name(self):
        from types import SimpleNamespace
        from wfm.app import App
        from tests.test_engine import item
        app = App.__new__(App)
        app.world = SimpleNamespace(gamedata=SimpleNamespace(items={7: item(7, 'Dark Rune', quality=2)}))
        plan = {'actions': [{'title': 'If it is still listed: buy Dark Rune at 2g 25s', 'item_id': 7},
                            {'title': 'Spend an hour: Kill Marsh Owl', 'item_id': None}], 'goal': None}
        v = app.plan_view(plan)
        self.assertEqual((v['actions'][0]['item_name'], v['actions'][0]['quality']), ('Dark Rune', 2))
        self.assertNotIn('item_name', v['actions'][1])
        self.assertNotIn('item_name', plan['actions'][0])        # the engine's plan is left alone
        self.assertIsNone(app.plan_view(None))
