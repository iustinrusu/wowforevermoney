import json
import unittest
from types import SimpleNamespace as NS

from wfm import market

NOW = 1_800_000_000
H = 3600


def snap(ts, mb, listed=10, market_v=1000, sale=1000, spd=20.0):
    return {'ts': ts, 'min_buyout': mb, 'num_auctions': listed, 'market': market_v, 'region_market': market_v,
            'region_sale': sale, 'sold_per_day': spd}


def prices(mb=1000, listed=10, mv=1000, sale=1000, spd=20.0, rate=0.6):
    return {'minBuyout': mb, 'numAuctions': listed, 'marketValue': mv, 'regionSale': sale,
            'regionSoldPerDay': spd, 'regionSalePercent': rate}


def by_name(sigs):
    return {s['name']: s for s in sigs}


class Signals(unittest.TestCase):
    def test_rising_price_and_shrinking_supply_is_bullish(self):
        series = [snap(NOW - 24 * H, 800, listed=40), snap(NOW - 12 * H, 900, listed=30), snap(NOW, 1000, listed=10)]
        sigs = market.signals(prices(mb=1000, listed=10, mv=800, sale=1100), series, NOW)
        s = by_name(sigs)
        self.assertEqual(s['Price momentum']['score'], 1)          # +25% over the day
        self.assertEqual(s['Price vs 14-day average']['score'], 1)  # +25% vs average
        self.assertEqual(s['Supply']['score'], 1)                  # 10 listed vs 40 a day ago
        self.assertEqual(s['Demand']['score'], 1)                  # 20/day, 60% sell
        self.assertEqual(market.sentiment(sigs)['label'], 'Bullish')

    def test_falling_price_flooded_supply_is_bearish(self):
        series = [snap(NOW - 24 * H, 1000, listed=10), snap(NOW, 700, listed=40)]
        sigs = market.signals(prices(mb=700, listed=40, mv=1000, sale=400, spd=0.5, rate=0.05), series, NOW)
        s = by_name(sigs)
        self.assertEqual(s['Price momentum']['score'], -1)
        self.assertEqual(s['Price vs 14-day average']['score'], -1)
        self.assertEqual(s['Supply']['score'], -1)
        self.assertEqual(s['Demand']['score'], -1)                 # barely sells
        self.assertEqual(s['Realm vs region']['score'], -1)        # 175% of the region's sale price
        self.assertEqual(market.sentiment(sigs)['label'], 'Bearish')

    def test_small_moves_are_neutral(self):
        series = [snap(NOW - 24 * H, 1000), snap(NOW, 1030)]
        s = by_name(market.signals(prices(mb=1030, mv=1000), series, NOW))
        self.assertEqual(s['Price momentum']['score'], 0)
        self.assertEqual(s['Price vs 14-day average']['score'], 0)

    def test_no_history_or_listing_means_no_data_not_a_guess(self):
        sigs = market.signals({'marketValue': 1000, 'numAuctions': 0}, [], NOW)
        s = by_name(sigs)
        self.assertIsNone(s['Price momentum']['score'])
        self.assertIsNone(s['Price vs 14-day average']['score'])
        self.assertIsNone(s['Supply']['score'])
        self.assertIsNone(s['Demand']['score'])
        self.assertIsNone(s['Realm vs region']['score'])
        self.assertEqual(market.sentiment(sigs), {'label': 'Neutral', 'score': 0, 'signals_with_data': 0, 'signals': 5})

    def test_supply_compares_with_a_day_ago_only(self):
        series = [snap(NOW - 2 * H, 1000, listed=5), snap(NOW, 1000, listed=40)]   # nothing 20-28 h back
        self.assertIsNone(by_name(market.signals(prices(listed=40), series, NOW))['Supply']['score'])


class Build(unittest.TestCase):
    def test_build_is_json_and_has_trends(self):
        series = [snap(NOW - 8 * 24 * H, 1000), snap(NOW - 24 * H, 1100), snap(NOW, 1200)]
        d = market.build(5, NS(name='Thing', quality=2, sell_price=50), prices(mb=1200), series, NOW)
        json.dumps(d)
        self.assertAlmostEqual(d['trend_all']['change'], 0.2)
        self.assertAlmostEqual(d['trend_24h']['change'], 1200 / 1100 - 1)
        self.assertEqual(d['name'], 'Thing')


if __name__ == '__main__':
    unittest.main()
