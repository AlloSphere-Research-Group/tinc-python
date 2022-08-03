# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 17:13:15 2020

@author: Andres
"""

from .tinc_object import TincObject
from .cachemanager import CacheEntry, CacheManager, DistributedPath, FileDependency, SourceArgument, SourceInfo, UserInfo, VariantValue, VariantType
from .parameter import *

import traceback
import os
import pickle
import threading
from threading import Lock

import inspect, dis

class ParameterSpace(TincObject):
    '''The ParameterSpace class contains a set of :class:`tinc.parameter.Parameter` objects and organizes access to them

 Parameter spaces can be linked to specific directories in the file system.
 This can be useful to locate data according to paramter values. For example
 when the data is a result of a parameter sweep that generated multiple
 directories. See set_current_path_template() and generate_relative_run_path() for
 more information.
    '''
    def __init__(self, tinc_id = '', tinc_client = None):
        '''Constructor methos
        '''
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
    
    def __str__(self):
        details = f" ** ParameterSpace '{self.id}'\n"
        for p in self._parameters:
            if type(p) == Parameter or type(p) == ParameterInt:
                details += f"   -- Parameter {p.id}{':' + p.group if p.group else ''} {p.minimum} ... {p.maximum}\n"
            else:
                details += f"   -- Parameter {p.id}{':' + p.group if p.group else ''}\n"
        details += "\n"
        return details
        
    def get_dimension(self, param_id, group = None):
        '''Returns parameter that matches param_id name and group. If group is None, the first match is returned.
        
        :param param_id: Parameter name to match
        :param group: group to match
        :returns: The matched parameter or None if no match
        '''
        for p in self._parameters:
            if p.id == param_id:
                if group is None or group == p.group:
                    return p
        return None

    def register_dimensions(self, params):
        '''Register a list of parameters as dimensions for the parameter space'''
        for param in params:
            self.register_parameter(param)
        
    def register_dimension(self, param):
        '''Register a parameter as a dimension for the parameter space'''
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
        if self.tinc_client:
            pass
            #FIXME notify TINC server 
        return param

    def create_dimension(self, name, values = None):
        '''Create a parameter/dimension in the parameter space of type :class:`tinc.parameter.Parameter`.
        
        :param name: Name of the parameter to create
        :param values: (optional) values the parameter can take
        :returns: the created parameter
        '''
        p = Parameter(name)
        p.values = values
        self.register_dimension(p)

    def remove_dimension(self, param):
        for p in self._parameters:
            if p.id == param.id and p.group == param.group:
                self._parameters.remove(p)
                break
            
    def enable_cache(self, directory = "python_cache"):
        '''Enable caching for processes run through run_process()'''
        if self.tinc_client:
            if directory != "":
                print("Connected to client. enable_cache() ignoring directory")
        self._cache_manager = CacheManager(directory)
        
    def disable_cache(self):
        self._cache_manager = None
        
    def clear_cache(self):
        if self._cache_manager:
            self._cache_manager.clear_cache()

    def get_dimensions(self):
        return self._parameters

    # Aliases using 'parameter' instead of 'dimension'
    def get_parameter(self, param_id, group = None):
        return self.get_dimension(param_id, group)
    
    def get_parameters(self):
        return self.get_dimensions()
        
    def register_parameters(self, params):
        self.register_dimensions(params)
        
    def register_parameter(self, param):
        return self.register_dimension(param)
            
    def remove_parameter(self, param):
        return self.remove_dimension(param)
   
    def set_current_path_template(self, path_template):
        '''
        Set the current path template for the paramter space to map current values
        to a location in the filesystem.
        You can use %% to delimit dimension names, e.g. "value_%%ParameterValue%%"
        where %%ParameterValue%% will be replaced by the current value (in the
        correct representation as ID, VALUE or INDEX) of the dimension whose id is
        "ParameterValue". You can specify a different representation than the one
        set for the ParameterSpaceDimension by adding it following a ':'. For
        example:
        "value_%%ParameterValue:INDEX%%" will replace "%%ParameterValue:INDEX%%"
        with the current index for ParameterValue.
        For parameters that have mutiple ids for the same value, you can specify
        any muber of parameters separated by commas. the function get_common_id()
        will be called. For example, for %%param1,param2%% the common id for the
        their current values will be inserted. Any representation type (ID, VALUE,
        INDEX) is ignored, as only ids are used. Using this method can be useful as
        it can avoid having to define a custom generateRelativeRunPath() function
        '''
        if type(path_template) != str:
            raise ValueError('Path template must be a string')
        if self.tinc_client:
            print("Setting local path template, but it can be overriden by the TINC server.") 
        self._path_template = path_template
        
    def resolve_template(self, path_template, index_map = None):
        '''Resolve a path template according to the current parameter values.'''
        resolved_template = ''
        if path_template.count("%%") == 0:
            return path_template
        end = 0
        if index_map is None:
            index_map = {}
        for p in self._parameters:
            if not p.id in index_map:
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
            if self.debug:
                print(f'Found param {token} in template: {start, end}')

            if token.count(',') > 0:
                tokens = token.split(',')
                dims = []
                for t in tokens:
                    dims.append(self.get_parameter(t))
                resolved_template += self.get_common_id(dims, index_map)
            else:
                if token.count(':') > 0:
                    sep_index = token. index(':')
                    representation = token[sep_index+1:]
                    token = token[:sep_index]
                param = self.get_parameter(token)
                index = index_map[token]
                if param:
                    if representation == 'VALUE':
                        resolved_template += str(param.values[index])
                    elif representation == 'ID':
                        if index > len(param.ids):
                            raise ValueError(f"Insufficient ids in parameter '{param.id}' for substitution")
                        resolved_template += str(param.ids[index])
                    elif representation == 'INDEX':
                        resolved_template += str(index)
                else:
                    print(f"Warning: could not resolve token {token} in template")

        if end < len(path_template):
            resolved_template += path_template[end:]
        return resolved_template

    def get_common_id(self, dimensions, indeces = None):
        # validate dims size > 1
        if indeces is None:
            indeces = {}
            for dim in dimensions:
                indeces[dim.id] = dim.get_current_index()

        ids = dimensions[0].get_ids_for_value(dimensions[0].values[indeces[dimensions[0].id]])
        for dim in dimensions[1:]:
            next_ids = dim.get_ids_for_value(dim.values[indeces[dim.id]])
            ids_to_remove =[]
            for id in ids:
                if not id in next_ids:
                    ids_to_remove.append(id)
            for id_to_remove in ids_to_remove:
                while id_to_remove in ids:
                    ids.remove(id_to_remove)
        
        if len(ids) == 1:
            return ids[0]
        else:
            print("No common id")
            return ""

    def _substitute_values(self, path_template, replacement_map):
        resolved_template = ''
        while path_template.count("%%", end)> 0:
            start = path_template.index("%%", end)
            resolved_template += path_template[end: start]
            end = path_template.index("%%", start + 2)
            token = path_template[start + 2: end]
            end += 2
            # TODO support different representations
            if token.count(':') > 0:
                sep_index = token. index(':')
                token = token[:sep_index]
            resolved_template += replacement_map(token)


    def get_current_relative_path(self):
        if self.tinc_client:
            return self.tinc_client._command_parameter_space_get_current_relative_path(self, self.server_timeout)
        else:
            return self.resolve_template(self._path_template)
        
    def is_filesystem_dimension(self, dimension_name):
        if isinstance(dimension_name, Parameter):
            dimension_name = dimension_name.id
        dim = self.get_parameter(dimension_name)
        if dim is not None and len(dim.values) > 1:
            index_map = {}
            for p in self._parameters:
                if len(p.values) > 0:
                    index_map[p.id] = p.get_current_index()
                else:
                    index_map[p.id] = -1
            index_map[dimension_name] = 0
            path0 = self.resolve_template(self._path_template, index_map)
            index_map[dimension_name] = len(dim.values) - 1
            path1 = self.resolve_template(self._path_template, index_map)
            if path0 != path1:
                return True
        return False

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
 
    def running_paths(self, fixed_dimensions = []):
        paths = []
        params = []
        fixed_params = {}
        for dim in self._parameters:
            if dim.id != fixed_dimensions:
                params.append(dim)
            else:
                # TODO support other paramter representations. This hard codes VALUE
                fixed_params[dim.id] = str(dim.value)

        indeces = [0]*len(params)
        index_max = [len(p.values) for p in params]

        done = False 
        while not done and self.sweep_running:
            sweep_values = {p.id:str(p.values[indeces[i]]) for i, p in enumerate(params)}
            sweep_values.update(fixed_params)

            paths.append(self._substitute_values(self._path_template, sweep_values))

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

        return paths
    
    def sweep(self, function, params=None, dependencies = [], force_recompute = False, force_values = False):
        '''Sweep the parameter space running the function for all value combinations
        
        :param function: Function to run for each parameter space sample
        :param params: If set, only the parameters provided will be sweept. The rest of the parameters in the ParameterSpace will be kept constant at their current value
        :param dependencies: 
        :param force_recompute: Always recompute function even if there is cache available
        :param force_values: Set all parameters' value every sample. This will trigger parameter callbacks. This is required when you query the parameter values within the function rather than taking the parameter values as function parameters
        '''

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
                elif issubclass(type(p),ParameterString):
                    if p.id in named_args:
                        calling_args[p.id] = p.value
                else:
                    print("ERROR argument element to _process() is not a Parameter type. Ignoring")
            
            unused_args = [p for p in calling_args.keys() if not p in named_args]
        else:
            raise ValueError("args argument can take a list of parameter or a dict of values")
        
        if len(unused_args) > 0:
            print(f'Ignoring parameters: {unused_args}. Not used in function')
        
        out = None
        if self._cache_manager:
            # TODO store metadata about function to know if we need to reprocess cache
            # TODO set working path and hash in src_info
            
            args = []
            for id,value in calling_args.items():
                nctype = VariantType.VARIANT_DOUBLE
                if type(value) == int:
                    nctype = VariantType.VARIANT_INT64
                elif type(value) == float:
                    nctype = VariantType.VARIANT_DOUBLE
                elif type(value) == np.int32:
                    nctype = VariantType.VARIANT_INT32
                    value = int(value) # json can't handle int32
                elif type(value) == np.float64:
                    nctype = VariantType.VARIANT_DOUBLE
                    # value = value
                else:
                    print(f"Unsupported type for arg: {id} - {type(value)}")

                args.append(SourceArgument(id = id, 
                                            value = VariantValue(nctype = nctype,
                                                                value = value)))

            deps = []
            for dep in dependencies:
                if type(dep) == Parameter:
                    nctype = VariantType.VARIANT_FLOAT
                elif type(dep) == ParameterInt:
                    nctype = VariantType.VARIANT_INT32
                elif type(dep) == ParameterString:
                    nctype = VariantType.VARIANT_STRING
                else:
                    # TODO ML add support for all types
                    print("Warning unsupported type")

                deps.append(SourceArgument(id = dep.id, 
                                           value = VariantValue(nctype = nctype,
                                                                value = dep.value)))

            fdeps = []
            if self.debug:
                print(dis.dis(function))
                print(inspect.getsource(function))
            # TODO set filename and root path
            dist_path =  DistributedPath()
            dist_path.filename = ""
            dist_path.relative_path = os.getcwd()
            dist_path.root_path = ""
            dist_path.protocol_id = "python"
            fdeps.append(FileDependency(file = dist_path,
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
                    dependencies = deps,
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
                    dist_path = DistributedPath()
                    dist_path.filename = filename
                    entry = CacheEntry(timestamp_start='a',
                                    timestamp_end='b',
                                    files=[FileDependency(file = dist_path)],
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
