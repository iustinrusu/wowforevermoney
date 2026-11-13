"""Ranking (user, 2026-11-14): profit x how sure we are x risk x can-do-now x problems x preference."""
import unittest

from tests.test_engine import PRODUCT, SETTINGS, make_world
from wfm.engine import Engine, Opportunity


def opp(**kw):
    base = dict(kind='vendor_flip', key='k', item_id=PRODUCT, title='t', profit_unit=300, cost_unit=20, units_day=10,
                daily=3000, doable=True)
    base.update(kw)
    return Opportunity(**base)


class Ranking(unittest.TestCase):
    def setUp(self):
        self.e = Engine(make_world({}), dict(SETTINGS))

    def score(self, **kw):
        return self.e.rank(opp(**kw))[0]

    def test_same_profit_less_at_risk_ranks_higher(self):
        cheap = self.score(cost_unit=20)                 # risk 20c to make 3s
        dear = self.score(cost_unit=6000)                # risk 60s to make 3s
        self.assertGreater(cheap, dear)
        _, parts = self.e.rank(opp(cost_unit=6000))
        self.assertEqual(parts['downside'], 6000 - 20)  # Tasty Dish sells to a vendor for 20c
        self.assertAlmostEqual(parts['risk'], 1 / (1 + 0.05 * 5980 / 300), places=3)

    def test_doubts_and_problems_lower_the_rank(self):
        clean = self.score()
        self.assertLess(self.score(flags=['sells_lower']), clean)
        self.assertLess(self.score(flags=['hard_to_sell']), self.score(flags=['sells_lower', 'crowded']))

    def test_can_do_now_beats_skill_gap_beats_other_profession(self):
        now = self.score(kind='craft')
        gap = self.score(kind='craft', doable=False)
        other = self.score(kind='craft', doable=False, flags=['other_profession'])
        self.assertGreater(now, gap)
        self.assertGreater(gap, other)
        self.assertEqual(self.e.rank(opp(kind='craft', doable=False), later=True)[1]['doable'], 1.0)

    def test_affordable_now_counts_fully_more_gold_counts_10_percent(self):
        _, parts = self.e.rank(opp(daily=1000, detail={'daily_if_affordable': 11000}))
        self.assertEqual(parts['base'], 1000 + 1000)
        self.assertEqual(self.e.rank(opp(daily=1000, detail={'daily_if_affordable': 11000}), later=True)[1]['base'], 11000)

    def test_activities_rank_by_gold_per_hour_snipes_by_profit(self):
        self.assertEqual(self.e.rank(opp(kind='fishing_spot', gph=50000, daily=0, cost_unit=0))[1]['base'], 50000)
        self.assertEqual(self.e.rank(opp(kind='realm_dip', profit_unit=700, daily=700))[1]['base'], 700)

    def test_preferred_profession_bonus(self):
        self.assertAlmostEqual(self.score(preferred=True), self.score() * 1.1)

    def test_run_scores_every_row_and_orders_top_picks_by_score(self):
        r = Engine(make_world({}), dict(SETTINGS)).run()
        by = {o.key: o for o in r['opportunities']}
        for o in r['opportunities']:
            self.assertIn('rank', o.detail)
        now = [by[k].score for k in r['top']['now']]
        self.assertEqual(now, sorted(now, reverse=True))


if __name__ == '__main__':
    unittest.main()
