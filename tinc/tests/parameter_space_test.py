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

    def test_data_directories(self):
        dim1 = Parameter("dim1")
        dim1.values = [0.1,0.2,0.3,0.4, 0.5]
        dim2 = Parameter("dim2")
        dim2.set_space_representation_type(parameter_space_representation_types.INDEX)
        dim2.values = [0.1,0.2,0.3,0.4, 0.5]
        dim3 = Parameter("dim3")
        dim3.set_space_representation_type(parameter_space_representation_types.ID)
        dim2.values = [0.1,0.2,0.3,0.4, 0.5]

        ps = ParameterSpace("ps")
        ps.register_parameters([dim1, dim2, dim3])
        ps.set_current_path_template("file_%%dim1%%_%%dim2:INDEX%%")

        dim1.value=0.2
        dim2.value=0.2
        self.assertEqual(ps.get_current_relative_path(), 'file_0.2_1')

        # TODO ML complete tests see C++ tests for parameter space

        
    def test_common_id(self):
        dim1 = Parameter("dim1")
        dim1.values = [0.1, 0.1, 0.2, 0.2, 0.3, 0.3]
        dim1.ids = ["0.1_1" ,"0.1_2","0.2_1" ,"0.2_2", "0.3_1" ,"0.3_2"]

        dim2 = Parameter("dim2")
        dim2.set_space_representation_type(parameter_space_representation_types.INDEX)
        dim2.values = [1,1,1,2,2,2]
        dim2.ids = ["0.1_1", "0.2_1", "0.3_1", "0.1_2", "0.2_2", "0.3_2"]

        ps = ParameterSpace("ps")
        ps.register_parameters([dim1, dim2])
        dim1.value = 0.1
        dim2.value = 1
        self.assertEqual(ps.get_common_id([dim1, dim2]), "0.1_1")
        dim1.value = 0.2
        dim2.value = 1
        self.assertEqual(ps.get_common_id([dim1, dim2]), "0.2_1")
        dim1.value = 0.1
        dim2.value = 2
        self.assertEqual(ps.get_common_id([dim1, dim2]), "0.1_2")
        dim1.value = 0.2
        dim2.value = 2
        self.assertEqual(ps.get_common_id([dim1, dim2]), "0.2_2")
        dim1.value = 0.3
        dim2.value = 2
        self.assertEqual(ps.get_common_id([dim1, dim2]), "0.3_2")
        
        
if __name__ == '__main__': 
    unittest.main()
