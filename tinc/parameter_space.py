# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 17:13:15 2020

@author: Andres
"""

import threading
from .tinc_object import TincObject
from .cachemanager import CacheEntry, CacheManager, DistributedPath, FileDependency, SourceArgument, SourceInfo, UserInfo, VariantValue, VariantType
from .parameter import Parameter
from threading import Lock

import traceback
import os
import pickle

import inspect, dis

class ParameterSpace(TincObject):
    def __init__(self, tinc_id = '', tinc_client = None):
        super().__init__(tinc_id)
        self._parameters = []
        self.tinc_client = tinc_client
        self._cache_manager = None
        self._path_template = ""
        self._process_lock = Lock()
        # self._local_current_path
        self._local_root_path = ''
        self.debug = False
        self.sweep_running = False
        self.sweep_threads = []
        
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
            
    def enable_cache(self, directory = "python_cache"):
        self._cache_manager = CacheManager(directory)
        
    def disable_cache(self):
        self._cache_manager = None
        
    def clear_cache(self):
        if self._cache_manager:
            self._cache_manager.clear_cache()
    
    def get_parameter(self, param_id, group = None):
        for p in self._parameters:
            if p.id == param_id:
                if group is None or group == p.group:
                    return p
        return None
    
    def get_parameters(self):
        return self._parameters

        # TODO ML add register and remove parameter
    
    def set_current_path_template(self, path_template):
        if type(path_template) != str:
            raise ValueError('Path template must be a string')
        if self.tinc_client:
            print("Setting local path template, but it can be overriden by the TINC server.") 
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
        
    def set_root_path(self, root_path):
        if type(root_path) != str:
            raise ValueError('Root path must be a string')
        if self.tinc_client:
            print("Setting local root path, but it can be overriden by the TINC server.") 
        self._local_root_path = root_path

    def get_root_path(self):
        if self.tinc_client:
            return self.tinc_client._command_parameter_space_get_root_path(self, self.server_timeout)
        else:
            return self._local_root_path
 
    def sweep(self, function, params=None, dependencies = [], force_recompute = False, force_values = False):
        if self.sweep_running:
            print("Sweep is already running")
            return
        self.sweep_running = True
        if params is None or len(params) == 0:
            params = self._parameters
        else:
            for p in params:
                registered = False
                for existing_param in self._parameters:    
                    if p.get_osc_address() == existing_param.get_osc_address():
                        registered = True
                        break
                if not registered:
                    print(f"Warning: Parameter p.get_osc_address() not registered with ParameterSpace")

        # TODO store metadata about function to know if we need to reprocess cache
        if self.debug:
            print(dis.dis(function))
            print(inspect.getsource(function))
        
        indeces = [0]*len(params)
        index_max = [len(p.values) for p in params]
        
        # original_values used to restore values if self.force_values
        original_values = {p:p.value for p in params}
    
        done = False 
        while not done and self.sweep_running:
            if force_values:
                for i,p in enumerate(params):
                    p.set_at(indeces[i])
                self.run_process(function, params, dependencies, force_recompute)
            else:
                sweep_values = {p.id:p.values[indeces[i]] for i, p in enumerate(params)}
                self.run_process(function, sweep_values, dependencies, force_recompute)
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
        self.sweep_running = False
                
    
    def sweep_async(self, function, args=None, dependencies = [], force_recompute = False, force_values = False,num_threads = 1):
        self.sweep_threads.clear()
        # FIXME self.sweep_running is set at the end of sweep(), so num_threads > 1 will not work correctly
        # FIXME support num_threads > 1 by slicing parameter space 
        for i in range(num_threads):
            self.sweep_threads.append(threading.Thread(target=self.sweep, 
                args=(function, args, dependencies, force_recompute, force_values)))
            self.sweep_threads[-1].start()

    def stop_sweep(self):
        self.sweep_running = False
        for th in self.sweep_threads:
            th.join()
        # TODO wait for sweep threads to end.
    
    def run_process(self, function, args = None, dependencies = [], force_recompute = False):
        # TODO add asynchronous mode
        with self._process_lock:
            if args is None:
                args = self._parameters
            else:
                if type(args) == list:
                    for p in self._parameters:
                        if not p in args:
                            args.append(p)
                elif type(args) == dict:
                    for p in self._parameters:
                        if p.id not in args.keys():
                            args[p.id] = p.value
            # print("running _process()")
            return self._process(function, args, dependencies, force_recompute)
            
    def _process(self,function, args, dependencies = [], force_recompute = False):
        
        named_args = inspect.getfullargspec(function)[0]
        # Only use arguments that can be passed to the function
        calling_args = {}
        
        if type(args) == dict:
            for key, value in args.items():
                if key in named_args:
                    calling_args[key] = value
            unused_args = [a for a in calling_args.keys() if not a in named_args]
        elif type(args) == list:
            for p in args:
                if issubclass(type(p),Parameter):
                    if p.id in named_args:
                        calling_args[p.id] = p.value
                else:
                    print("ERROR argument element to _process() is not a Parameter type. Ignoring")
            
            unused_args = [p for p in calling_args.keys() if not p in named_args]
        else:
            raise ValueError("args argument can take a list of parameter or a dict of values")
        
        if len(unused_args) > 0:
            print(f'Ignoring parameters: {unused_args}. Not used in function')
        cache_args = calling_args.copy()
        for dep in dependencies:
            cache_args[dep.id] = dep.value
        
        out = None
        if self._cache_manager:
            # TODO store metadata about function to know if we need to reprocess cache
            # TODO set working path and hash in src_info
            
            args = []
            for id,value in calling_args.items():
                nctype = VariantType.VARIANT_DOUBLE
                if type(value) == int:
                    nctype = VariantType.VARIANT_INT64

                args.append(SourceArgument(id = id, 
                                            value = VariantValue(nctype = nctype,
                                                                value = value)))

            fdeps = []
            if self.debug:
                print(dis.dis(function))
                print(inspect.getsource(function))
            # TODO set filename and root path
            fdeps.append(FileDependency(file = DistributedPath(filename = "",
                                                                relative_path = os.getcwd(),
                                                                root_path = "",
                                                                protocol_id = "python"),
                                            modified = "",
                                            size = 0,
                                            hash = ""
                                            ))
            # TODO there needs to be a special character to avoid tinc id clashes for these auto generated
            # tinc ids. e.g. self.id + '@' + function.__name__. The disallow @ in all other tinc id names.
            # Perhaps use space? That is already disallowed because of OSC address limitations.
            src_info = SourceInfo(
                    type = "PythonInMemory",
                    tinc_id = self.id + "_" + function.__name__,
                    command_line_arguments = "", # This could be used to store function information
                    working_path_rel = "",
                    working_path_root = "",
                    arguments = args,
                    dependencies = [],
                    file_dependencies = fdeps)
            if not force_recompute:
                cache_filenames = self._cache_manager.find_cache(src_info, dependencies)
                # TODO mark as stale if needed
                try:
                    for fname in cache_filenames:
                        cache_file_path = self._cache_manager.cache_directory() +"/" + fname
                        if os.path.exists(cache_file_path):
                            with open(cache_file_path, 'rb') as f:
                                out = pickle.load(f)
                                if self.debug:
                                    print(f"loaded cache: {cache_file_path}")
                                return out
                                # TODO increase cache hits
                        else:
                            print(f"ERROR finding cache file: {self._cache_manager.cache_directory() + '/' +fname}")
                except:
                    print("Cache is empty. Trying to generate cache")
                    traceback.print_exc()
        try:
            #print("Calling function with: " + str(calling_args))
            out = function(**calling_args)
            if self._cache_manager:
                # FIXME write complete metadata 
                try:
                    args_text = '_'.join([str(v) for v in calling_args.values()])
                    filename = self.id + "_" + function.__name__ + "_" + args_text + "_cache.pkl"
                    fullpath = self._cache_manager.cache_directory() + "/" + filename
                    if self.debug:
                        print("storing cache: " + fullpath)
                    with open(fullpath, "wb") as f:
                        pickle.dump(out, f)
                    entry = CacheEntry(timestamp_start='a',
                                    timestamp_end='b',
                                    files=[FileDependency(DistributedPath(filename))],
                                    user_info=UserInfo(user_name='name',
                                                        user_hash='hash',
                                                        ip='ip',
                                                        port=9001,
                                                        server=False),
                                    source_info=src_info,
                                    cache_hits=0,
                                    stale=False)
                    self._cache_manager.append_entry(entry)
                    self._cache_manager.write_to_disk()
                except:
                    print("Error creating cache")
                    traceback.print_exc()
        except Exception as e:
            print("Function call exception")
            traceback.print_exc()
            
        # print("done _process()")
        return out
        
 
    def print(self):
        print(f" ** ParameterSpace {self.id}: {self}")
        for p in self._parameters:
            print(f"   -- Parameter {p.id}{':' + p.group if p.group else ''} {p.get_osc_address()}")
