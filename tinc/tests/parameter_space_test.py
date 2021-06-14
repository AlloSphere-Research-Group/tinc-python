# -*- coding: utf-8 -*-
"""
Created on Mon Jun 14 11:49:43 2021

@author: Andres
"""

import sys,time
import unittest

from tinc import *


class ParameterSpaceTest(unittest.TestCase):

    def test_parameter(self):
        p1 = Parameter("param1")
        p2 = Parameter("param2")

        ps = ParameterSpace("ps")
        ps.register_parameters([p1, p2])
        
    def test_process(self):
        p1 = Parameter("param1")
        p1.values = [0, 1,2,3,4]
        p2 = Parameter("param2")
        p2.values = [-0.3,-0.2, -0.1, 0]

        ps = ParameterSpace("ps")
        ps.register_parameters([p1, p2])
        
        def func(param1, param2):
            return param1 * param2
        
        result = ps.run_process(func)
        
        self.assertAlmostEqual(result, p1.value * p2.value)
        
        p1.value = 3
        p2.value = -0.1
        
        result = ps.run_process(func)
        
        self.assertAlmostEqual(result, p1.value * p2.value)
        
        p1.value = 3
        p2.value = -0.1
        
        
    def test_sweep_cache(self):
        p1 = Parameter("param1")
        p1.values = [0, 1,2,3,4]
        p2 = Parameter("param2")
        p2.values = [-0.3,-0.2, -0.1, 0]

        ps = ParameterSpace("ps")
        ps.register_parameters([p1, p2])
        ps.enable_cache("ps_test")
        def func(param1, param2):
            return param1 * param2
        
        ps.sweep(func)
        
        
if __name__ == '__main__': 
    unittest.main()
