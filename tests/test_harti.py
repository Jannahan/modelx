import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from harti_parser import parse_price_range, resolve_commodity, resolve_market

class TestHartiParser(unittest.TestCase):

    def test_parse_price_range_valid(self):
        lo, hi, mid, traded = parse_price_range("500 - 600")
        self.assertTrue(traded)
        self.assertEqual(lo, 500.0)
        self.assertEqual(hi, 600.0)
        self.assertEqual(mid, 550.0)

    def test_parse_price_range_decimal(self):
        lo, hi, mid, traded = parse_price_range("225.50 - 275.50")
        self.assertTrue(traded)
        self.assertEqual(lo, 225.50)
        self.assertEqual(hi, 275.50)
        self.assertEqual(mid, 250.50)

    def test_parse_price_range_dash_no_trade(self):
        lo, hi, mid, traded = parse_price_range("-")
        self.assertFalse(traded)
        self.assertIsNone(lo)
        self.assertIsNone(hi)
        self.assertIsNone(mid)

    def test_resolve_commodity(self):
        self.assertEqual(resolve_commodity("Beans (Green)"), "BEANS")
        self.assertEqual(resolve_commodity("Bochi"), "BEANS")
        self.assertEqual(resolve_commodity("Carrot Nuwara Eliya"), "CARROT")
        self.assertEqual(resolve_commodity("Country Tomato"), "TOMATO")
        self.assertEqual(resolve_commodity("Leeks"), "LEEKS")
        self.assertEqual(resolve_commodity("White Cabbage"), "CABBAGE")
        self.assertEqual(resolve_commodity("Green Chilli"), "GREEN_CHILLI")

    def test_resolve_market(self):
        self.assertEqual(resolve_market("Peliyagoda Market"), "PELIYAGODA")
        self.assertEqual(resolve_market("Manning Market"), "PELIYAGODA")
        self.assertEqual(resolve_market("Dambulla DEC"), "DAMBULLA")
        self.assertEqual(resolve_market("Meegoda"), "MEEGODA")
        self.assertEqual(resolve_market("Keppetipola Market"), "KEPPETIPOLA")

if __name__ == "__main__":
    unittest.main()
