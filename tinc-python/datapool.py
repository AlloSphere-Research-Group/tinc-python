# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 15:47:46 2020

@author: Andres
"""

import netCDF4

class DataPool(object):
    def __init__(self, tinc_client, dp_id = "_", parameter_space_id = '', slice_cache_dir = ''):
        self.id = dp_id
        self.parameter_space_id = parameter_space_id
        self.slice_cache_dir = slice_cache_dir
        self.tinc_client = tinc_client
        
    def get_slice(self, field, sliceDimensions):
        slice_file = self.tinc_client.request_datapool_slice_file(self.id, field, sliceDimensions)
        nc = netCDF4.Dataset(self.slice_cache_dir + slice_file)
        print(nc.variables.keys())
        return nc.variables['data'][:]
    
    def get_slice_file(self, field, sliceDimensions):
        return self.tinc_client.request_datapool_slice_file(self.id, field, sliceDimensions)
        
    def print(self):
        print(f" ** DataPool: {self.id}")
        print(f"      ParameterSpace id: {self.parameter_space_id}")