# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 17:13:15 2020

@author: Andres
"""

from cachemanager import CacheManager

import inspect, dis

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
            
    def enable_caching(self, directory = "python_cache"):
        self._cache_manager = CacheManager(directory)
        
    def disable_caching(self):
        self._cache_manager = None
        
    def clear_cache(self):
        #FIXME this function needs to be moved to the cache manager
        indeces = [0]*len(self._parameters)
        index_max = [len(p.values) for p in self._parameters]
            
        done = False 
        while not done:
            args = {p.id:p.values[indeces[i]] for i,p in enumerate(self._parameters)}
            self._cache_manager.remove_cache_file(args)
            indeces[0] += 1
            current_p = 0
            while indeces[current_p] == index_max[current_p]:
                indeces[current_p] = 0
                if current_p == len(indeces) - 1:
                    if indeces == [0]*len(self._parameters):
                        done = True
                    break
                indeces[current_p + 1] += 1
                current_p += 1
            
    def get_parameters(self):
        return self._parameters
    
    def get_current_path(self):
        if self.tinc_client:
            return self.tinc_client.command_parameter_space_get_current_path(self)
        
    def get_root_path(self):
        if self.tinc_client:
            return self.tinc_client.command_parameter_space_get_root_path(self)
        
    def sweep(self, function):
        # TODO store metadata about function to know if we need to reprocess cache
        if True:
            print(dis.dis(function))
            print(inspect.getsource(function))
        
        indeces = [0]*len(self._parameters)
        index_max = [len(p.values) for p in self._parameters]
    
        done = False 
        while not done:
            args = {p.id:p.values[indeces[i]] for i,p in enumerate(self._parameters)}
            self._process(function, args)
            indeces[0] += 1
            current_p = 0
            while indeces[current_p] == index_max[current_p]:
                indeces[current_p] = 0
                if current_p == len(indeces) - 1:
                    if indeces == [0]*len(self._parameters):
                        done = True
                    break
                indeces[current_p + 1] += 1
                current_p += 1
                
    
    def process(self, function, args = None):
        if args is None:
            args = {p.id:p.value for p in self._parameters}
        return self._process(function, args)
            
    def _process(self,function, args):
        
        if self._cache_manager:
            out = self._cache_manager.load_cache(args)
            if out:
                print("Using cache")
                return out
            
        out = function(**args)
        if self._cache_manager:
            self._cache_manager.store_cache(out, args)
        return out
        
 
    def print(self):
        print(f" ** ParameterSpace {self.id}")