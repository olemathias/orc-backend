from unittest import TestCase
from orc.base.utils import get_tag_value


# Create your tests here.
class UtilsTestCase(TestCase):
    def test_get_tag_name(self):
        """Get tag from tags"""
        self.assertEqual(get_tag_value(
            [{"key": "name", "value": "name"}], "name"), "name")
        self.assertEqual(get_tag_value([{"key": "name", "value": "my name"}, {
                         "key": "owner", "value": "owner"}], "OwNer"), "owner")

    def test_get_tag_default(self):
        """Get default tag"""
        self.assertEqual(get_tag_value(
            [{"key": "name", "value": "name"}], "Name", "not name"), "name")
        self.assertEqual(get_tag_value(
            [{"key": "owner", "value": "owner"}], "name", "not name"), "not name")
