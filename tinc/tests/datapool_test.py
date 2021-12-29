# -*- coding: utf-8 -*-
"""
Created on Fri Sep 11 16:30:13 2020

@author: Andres
"""

import sys
import time

from tinc import *

import unittest
import random

class DataPoolTest(unittest.TestCase):

    def test_basic(self):
        ps = ParameterSpace("ps_id")
        dp = DataPool("dp_id", ps, 'cache_dir')
        data_files = [f'file_{random.randint(0,3000)}' for i in range(5)]
        dim_in_files = [f'dim_{random.randint(0,3000)}' for i in range(5)]
        for file, dim_name in zip(data_files,dim_in_files):
            dp.register_data_file(file, dim_name)
        self.assertEqual(dp.get_parameter_space().id, ps.id)
        

        self.assertEqual(len(dp.get_registered_data_files()), len(data_files))

        for file, dim_name in dp.get_registered_data_files().items():
            self.assertTrue(file in data_files)
            self.assertTrue(dim_name in dim_in_files)

    def test_slices(self):
        ps = ParameterSpace("ps_id")
        ps.set_root_path('data')
        dp = DataPoolJson("dp_id", ps, 'cache_dir')
        dp.register_data_file("results.json", "internal")
        dp.debug = True

        internalDim = Parameter("internal")
        ps.register_dimension(internalDim)
        internalDim.values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        externalDim = Parameter("external")
        ps.register_dimension(externalDim)
        externalDim.set_space_representation_type(parameter_space_representation_types.ID)
        externalDim.values = [10.0, 10.1, 10.2]
        externalDim.ids = ["folder1", "folder2", "folder3"]
        ps.set_current_path_template("%%external:ID%%/")

        # Slice across files
        internalDim.value = 0.0
        externalDim.value = 10.0
        
        slice = dp.get_slice('field1', 'external')
        self.assertListEqual(list(slice), [0,1,5])
        slice = dp.get_slice('field2', 'external')
        self.assertListEqual(list(slice), [1,0,6])
        slice = dp.get_slice('field3', 'external')
        self.assertListEqual(list(slice), [4,5,1])
        
        internalDim.value = 0.4
        
        slice = dp.get_slice('field1', 'external')
        self.assertListEqual(list(slice), [4,5,0])
        slice = dp.get_slice('field2', 'external')
        self.assertListEqual(list(slice), [5,4,1])
        slice = dp.get_slice('field3', 'external')
        self.assertListEqual(list(slice), [8,0,9])

        # Test slices from a single file
        internalDim.value = 0.0
        externalDim.value = 10.0

        slice = dp.get_slice('field1', 'internal')
        self.assertListEqual(list(slice), [0,1,2,3,4,5,6,7])
        slice = dp.get_slice('field2', 'internal')
        self.assertListEqual(list(slice), [1,2,3,4,5,6,7, 8])
        slice = dp.get_slice('field3', 'internal')
        self.assertListEqual(list(slice), [4,5,6,7, 8,9, 0, 1])

        externalDim.value = 10.2
        
        slice = dp.get_slice('field1', 'internal')
        self.assertListEqual(list(slice), [5,7,8,9,0,1,6,4])
        slice = dp.get_slice('field2', 'internal')
        self.assertListEqual(list(slice), [6,7,8,0,1,3,5,7])
        slice = dp.get_slice('field3', 'internal')
        self.assertListEqual(list(slice), [1,3,5,7,9,0,2,4])

    def test_multidim_slices(self):
        ps = ParameterSpace("ps_id")
        ps.set_root_path('data')
        dp = DataPoolJson("dp_id", ps, 'cache_dir')
        dp.register_data_file("results.json", "internal")
        dp.debug = True

        internalDim = Parameter("internal")
        ps.register_dimension(internalDim)
        internalDim.values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        externalDim = Parameter("external")
        ps.register_dimension(externalDim)
        externalDim.set_space_representation_type(parameter_space_representation_types.ID)
        externalDim.values = [10.0, 10.1, 10.2]
        externalDim.ids = ["folder1", "folder2", "folder3"]
        ps.set_current_path_template("%%external:ID%%/")

        # Slice across files
        internalDim.value = 0.0
        externalDim.value = 10.0

if __name__ == '__main__':
    unittest.main()