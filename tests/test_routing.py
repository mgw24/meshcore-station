import unittest
from station.routing import validate_catalog, normalize_scope, normalize_channel_scopes
class RoutingTests(unittest.TestCase):
    def test_scope(self):
        self.assertEqual(normalize_scope('*'), '')
        self.assertEqual(normalize_scope('#Spokane'), '#Spokane')
        with self.assertRaises(ValueError): normalize_scope('Spokane')
        with self.assertRaises(ValueError): normalize_scope('#X;region denyf *')
    def test_catalog(self):
        self.assertEqual(validate_catalog(['#USA','#Local']), ['#USA','#Local'])
        with self.assertRaises(ValueError): validate_catalog(['#A','#A'])
        with self.assertRaises(ValueError): validate_catalog(['#X']*33)
    def test_channels(self):
        self.assertEqual(normalize_channel_scopes({'0':'inherit','1':'','7':'#Local'}), {'1':'','7':'#Local'})
        with self.assertRaises(ValueError): normalize_channel_scopes({'8':'#Bad'})
if __name__ == '__main__': unittest.main()
