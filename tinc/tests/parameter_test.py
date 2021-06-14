# -*- coding: utf-8 -*-
"""
Created on Mon Jun 14 11:49:43 2021

@author: Andres
"""

import sys,time
import unittest

from tinc import *

external_value = 0
def callback(value):
    #print("enter callback")
    time.sleep(0.2)
    global external_value
    external_value = value
    #print("exit callback")


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

        p.clear_callbacks()
        
        # External value shoudl not change because callback is removed
        p.value = 0.7
        self.assertEqual(external_value, 0.4)
        
    def test_parameter_cb_async(self):
        global external_value
        p = Parameter("name", "group", -1, 1, 0.5)
        
        external_value = 0.5
        p.register_callback(callback, False)
        p.value = 0.4

        self.assertNotEqual(external_value, 0.4)
        time.sleep(0.3)
        
        self.assertEqual(external_value, 0.4)

    def test_parameter_space(self):
        global external_value
        p = Parameter("name", "group", -1, 1, 0.5)
        p.values = [1,2,3,4,5,6, 7]

        p.value = 1.8
        self.assertEqual(p.value, 2)

        p.value = 1.1
        self.assertEqual(p.value, 1)

        p.value = -0.1
        self.assertEqual(p.value, 1)

        p.value = 7.1
        self.assertEqual(p.value, 7)

        p.ids = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        
        self.assertEqual(p.get_current_id(), 'G')
        self.assertEqual(p.get_current_index(), 6)

        p.value = 5
        self.assertEqual(p.get_current_id(), 'E')
        self.assertEqual(p.get_current_index(), 4)

        p.set_at(3)
        self.assertEqual(p.get_current_id(), 'D')

        
    def test_parameter_int(self):
        global external_value
        p = ParameterInt("name", "group", -10, 10, 1)

        self.assertEqual(p.id, "name")
        self.assertEqual(p.group, "group")
        self.assertEqual(p.minimum, -10)
        self.assertEqual(p.maximum, 10)
        self.assertEqual(p.value, 1)

        p.value = 4
        self.assertEqual(p.value, 4)

        p.register_callback(callback)
        p.value = 6

        self.assertEqual(external_value, 6)

        p.clear_callbacks()
        
        # External value shoudl not change because callback is removed
        p.value = 5
        self.assertEqual(external_value, 6)

    def test_parameter_int_space(self):
        global external_value
        p = ParameterInt("name", "group", -10, 10, 1)
        p.values = [2,4,6,8,10]

        p.value = 3
        self.assertEqual(p.value, 4)

        p.value = 1
        self.assertEqual(p.value, 2)

        p.value = -2
        self.assertEqual(p.value, 2)

        p.value = 11
        self.assertEqual(p.value, 10)

        p.ids = ['A', 'B', 'C', 'D', 'E']
        
        self.assertEqual(p.get_current_id(), 'E')
        self.assertEqual(p.get_current_index(), 4)

        p.value = 4
        self.assertEqual(p.get_current_id(), 'B')
        self.assertEqual(p.get_current_index(), 1)

        p.set_at(2)
        self.assertEqual(p.get_current_id(), 'C')

    def test_parameter_vec_space(self):
        global external_value
        p = ParameterVec("name", "group", 3)
        p.value = [2,4,6]

        self.assertEqual(p.value, [2,4,6])
        
        # TODO test wrong sizes
        
if __name__ == '__main__': 
    unittest.main()
