# -*- coding: utf-8 -*-
"""
Created on Mon Nov 23 11:13:52 2020

@author: Andres
"""

# Not needed if tinc-python is installed
import sys
from tinc import *

import unittest
import glob, os

class PresetTest(unittest.TestCase):
    
    def test_preset_writing(self):
        p1 = Parameter("p")
        presets = PresetHandler("preset_writing")
        presets.register_parameter(p1)
        p1.value = 5
        presets.store_preset("test1")
        p1.value = 6
        presets.store_preset("test2")
        p1.value = 7
        presets.store_preset("test3")

        self.assertEqual(len(glob.glob("preset_writing/default.presetMap")), 1)
        self.assertEqual(len(glob.glob("preset_writing/*.preset")), 3)
        
        self.assertTrue(os.path.exists("preset_writing/test1.preset"))
        self.assertTrue(os.path.exists("preset_writing/test2.preset"))
        self.assertTrue(os.path.exists("preset_writing/test3.preset"))

    def test_preset_writing_multiple(self):
        pass

    def test_preset_writing_string(self):
        pass
    
    def test_preset_writing_other_types(self):
        pass

    def test_preset_reading(self):
        p1 = Parameter("pr")
        presets = PresetHandler("preset_reading")
        presets.register_parameter(p1)
        p1.value = 5
        presets.store_preset("testread1")
        p1.value = 6
        presets.store_preset("testread2")
        p1.value = 7
        presets.store_preset("testread3")

        self.assertEqual(p1.value, 7)
        ret = presets.recall_preset("testread1")
        self.assertTrue(ret)
        self.assertEqual(p1.value, 5)
        ret = presets.recall_preset("testread2")
        self.assertTrue(ret)
        self.assertEqual(p1.value, 6)
        ret = presets.recall_preset("testread3")
        self.assertTrue(ret)
        self.assertEqual(p1.value, 7)
        ret = presets.recall_preset("testread2")
        self.assertTrue(ret)
        self.assertEqual(p1.value, 6)
        ret = presets.recall_preset("invalid")
        self.assertFalse(ret)
        self.assertEqual(p1.value, 6)

    def test_preset_reading_index(self):
        p1 = Parameter("pr")
        presets = PresetHandler("preset_reading_index")
        presets.register_parameter(p1)
        p1.value = 5
        presets.store_preset_index(3, "testread1")
        p1.value = 6
        presets.store_preset_index(4, "testread2")
        p1.value = 7
        presets.store_preset_index(6, "testread3")

        self.assertEqual(p1.value, 7)
        ret = presets.recall_preset("testread1")
        self.assertTrue(ret)
        self.assertEqual(p1.value, 5)
        ret = presets.recall_preset("testread2")
        self.assertTrue(ret)
        self.assertEqual(p1.value, 6)
        ret = presets.recall_preset("testread3")
        self.assertTrue(ret)
        self.assertEqual(p1.value, 7)
        ret = presets.recall_preset("testread2")
        self.assertTrue(ret)
        self.assertEqual(p1.value, 6)
        ret = presets.recall_preset("invalid")
        self.assertFalse(ret)
        self.assertEqual(p1.value, 6)

        ret = presets.recall_preset_index(3)
        self.assertTrue(ret)
        self.assertEqual(p1.value, 5)
        ret = presets.recall_preset_index(4)
        self.assertTrue(ret)
        self.assertEqual(p1.value, 6)
        ret = presets.recall_preset_index(6)
        self.assertTrue(ret)
        self.assertEqual(p1.value, 7)
        ret = presets.recall_preset_index(0)
        self.assertFalse(ret)
        self.assertEqual(p1.value, 7)

    def test_preset_reading_types(self):
        pass

if __name__ == '__main__': 
    unittest.main()
