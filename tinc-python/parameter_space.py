# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 17:13:15 2020

@author: Andres
"""

from cachemanager import CacheManager

class ParameterSpace(object):
    def __init__(self, name = '', tinc_client = None):
        self.id = name
        self._parameters = []
        self.tinc_client = tinc_client
        self._cache_manager = None
        # self._local_current_path
        # self._local_root_path
        # self._local_path_template
        
    def register_parameters(self, params):
        for param in params:
            self.register_parameter(param)
        
    def register_parameter(self, param):
        param_registered = False
        for p in self._parameters:
            if p.id == param.id and p.group == param.group:
                if not p is param:
                    print("ERROR: Registering the same parameter with a different object")
                param_registered = True
        if not param_registered:
            self._parameters.append(param)
            
    def configure_caching(self, directory):
        self._cache_manager = CacheManager(self, directory)
            
    def get_parameters(self):
        return self._parameters
    
    def get_current_path(self):
        if self.tinc_client:
            return self.tinc_client.command_parameter_space_get_current_path(self)
        
    def get_root_path(self):
        if self.tinc_client:
            return self.tinc_client.command_parameter_space_get_root_path(self)
        
    def sweep(self, function):
        function()
 
    def print(self):
        print(f" ** ParameterSpace {self.id}")