# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 15:47:46 2020

@author: Andres
"""

from tinc_object import TincObject

import netCDF4

class DataPool(TincObject):
    def __init__(self, tinc_id = "_", parameter_space_id = '', slice_cache_dir = '', tinc_client = None):
        super().__init__(tinc_id)
        self.parameter_space_id = parameter_space_id
        self.slice_cache_dir = slice_cache_dir
        self.tinc_client = tinc_client
        
    def get_slice(self, field, sliceDimensions):
        if not self.tinc_client:
            # TODO implement slicing for local data
            
            print("Datapool get_slice not implemented without connection")
            return None
        slice_file = self.tinc_client._command_datapool_slice_file(self.id, field, sliceDimensions, self.server_timeout)
        nc = netCDF4.Dataset(self.slice_cache_dir + slice_file)
        # print(nc.variables.keys())
        return nc.variables['data'][:]
    
    def get_slice_file(self, field, sliceDimensions):
        if not self.tinc_client:
            # TODO implement slicing for local data
            print("Datapool get_slice_file not implemented without connection")
            return None
        return self.tinc_client._command_datapool_slice_file(self.id, field, sliceDimensions, self.server_timeout)
        
    def get_current_files(self):
        if not self.tinc_client:
            # TODO implement for local data
            print("Datapool get_current_files not implemented without connection")
            return None
        return self.tinc_client._command_datapool_get_files(self.id, self.server_timeout)
        
    
    def print(self):
        print(f" ** DataPool: {self.id}")
        print(f"      ParameterSpace id: {self.parameter_space_id}")