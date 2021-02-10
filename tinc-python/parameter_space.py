# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 17:13:15 2020

@author: Andres
"""

from tinc_object import TincObject
from cachemanager import CacheManager

import inspect, dis

class ParameterSpace(TincObject):
    def __init__(self, tinc_id = '', tinc_client = None):
        super().__init__(tinc_id)
        self._parameters = []
        self.tinc_client = tinc_client
        self._cache_manager = None
        self._path_template = ""
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
                    print("ERROR: Attempting to register the same parameter id with a different object")
                else:
                    # print("Parameter already registered")
                    p._value_callbacks = param._value_callbacks
                    param = p
                param_registered = True
                break
        if not param_registered:
            # print(f'register {param.id} for {self}')
            self._parameters.append(param)
        return param
            
    def unregister_parameter(self, param):
        for p in self._parameters:
            if p.id == param.id and p.group == param.group:
                self._parameters.remove(p)
                break
            
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
            args = {p.id:p.values[indeces[i]] if len(p.values) > 0 else p.value for i,p in enumerate(self._parameters)}
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
    
    def get_parameter(self, param_id, group = None):
        for p in self._parameters:
            if p.id == param_id:
                if group is None or group == p.group:
                    return p
        return None
    
    def get_parameters(self):
        return self._parameters
    
    def set_current_path_template(self, path_template):
        if type(path_template) != str:
            raise ValueError('Path template must be a string')
        self._path_template = path_template
        
    def resolve_path(self, path_template, index_map = None):
        resolved_template = ''
        end = 0
        if index_map is None:
            index_map = {}
            for p in self._parameters:
                if len(p.values) > 0:
                    index_map[p.id] = p.get_current_index()
                else:
                    index_map[p.id] = -1
        while path_template.count("%%", end)> 0:
            start = path_template.index("%%", end)
            resolved_template += path_template[end: start]
            end = path_template.index("%%", start + 2)
            token = path_template[start + 2: end]
            end += 2
            representation = 'VALUE'
            if token.count(':') > 0:
                sep_index = token. index(':')
                representation = token[sep_index+1:]
                token = token[:sep_index]
            param = self.get_parameter(token)
            index = index_map[token]
            if param:
                if representation == 'VALUE':
                    resolved_template += str(param.value)
                elif representation == 'ID':
                    resolved_template += str(param.ids[index])
                elif representation == 'INDEX':
                    resolved_template += str(index)
            else:
                print(f"Warning: could not resolve token {token} in template")
        return resolved_template
            

    def get_current_relative_path(self):
        if self.tinc_client:
            return self.tinc_client._command_parameter_space_get_current_relative_path(self, self.server_timeout)
        else:
            return self.resolve_path(self._path_template)
        
    def get_root_path(self):
        if self.tinc_client:
            return self.tinc_client._command_parameter_space_get_root_path(self, self.server_timeout)
        
    def sweep(self, function, params=None, force_values = False, dependencies = []):
        if params is None or len(params) == 0:
            params = self._parameters
        else:
            to_remove = []
            for p in params:
                registered = False
                for existing_param in self._parameters:    
                    if p.get_osc_address() == existing_param.get_osc_address():
                        registered = True
                        break
                if not registered:
                    print(f"Warning: Parameter p.get_osc_address() not registered with ParameterSpace")

        # TODO store metadata about function to know if we need to reprocess cache
        if True:
            print(dis.dis(function))
            print(inspect.getsource(function))
        
        indeces = [0]*len(params)
        index_max = [len(p.values) for p in params]
        
        original_values = {p:p.value for p in params}
    
        done = False 
        while not done:
            if force_values:
                for i,p in enumerate(params):
                    p.set_at(indeces[i])
                
            args = {p.id:p.values[indeces[i]] for i,p in enumerate(params)}
            self.run_process(function, args, dependencies)
            indeces[0] += 1
            current_p = 0
            while indeces[current_p] == index_max[current_p]:
                indeces[current_p] = 0
                if current_p == len(indeces) - 1:
                    if indeces == [0]*len(params):
                        done = True
                    break
                indeces[current_p + 1] += 1
                current_p += 1
                
        if force_values:
            for p, orig_val in original_values.items():
                p.value = orig_val
                
    
    def run_process(self, function, args = None, dependencies = []):
        if args is None:
            args = {p.id:p.value for p in self._parameters}
        for p in self._parameters:
            if(p.id not in args):
                args[p.id] = p.value
        return self._process(function, args, dependencies)
            
    def _process(self,function, args, dependencies = []):
        
        named_args = inspect.getfullargspec(function)[0]
        
        unused_args = [a for a in args.keys() if not a in named_args]
        if len(unused_args) > 0:
            print(f'Ignoring parameters: {unused_args}. Not used in function')
        # Only use arguments that can be passed to the function
        calling_args = {key:value for key, value in args.items() if key in named_args}
        
        cache_args = calling_args.copy()
        for dep in dependencies:
            cache_args[dep.id] = dep.value
        
        if self._cache_manager:
            out = self._cache_manager.load_cache(cache_args)
            if out:
                print("Using cache")
                return out
            
        out = function(**calling_args)
        if self._cache_manager:
            self._cache_manager.store_cache(out, cache_args)
        return out
        
 
    def print(self):
        print(f" ** ParameterSpace {self.id}: {self}")
        for p in self._parameters:
            print(f"   -- Parameter {p.id}{':' + p.group if p.group else ''} {p.get_osc_address()}")