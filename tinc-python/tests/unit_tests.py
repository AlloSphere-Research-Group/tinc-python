import unittest

import sys
sys.path.append('../')
sys.path.append('./tinc-python/tinc-python')
from parameter import *

external_value = 0
def callback(value):
    global external_value
    external_value = value


class ParameterTest(unittest.TestCase):

    def test_parameter(self):
        global external_value
        p = Parameter("name", "group", -1, 1, 0.5)

        self.assertEqual(p.id, "name")
        self.assertEqual(p.group, "group")
        self.assertEqual(p.minimum, -1)
        self.assertEqual(p.maximum, 1)
        self.assertEqual(p.value, 0.5)

        p.value = 0.8
        self.assertEqual(p.value, 0.8)

        p.register_callback(callback)
        p.value = 0.4

        self.assertEqual(external_value, 0.4)

if __name__ == '__main__': 
    unittest.main()
