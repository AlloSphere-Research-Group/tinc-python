# -*- coding: utf-8 -*-
"""
Created on Mon Oct  4 17:13:15 2021

@author: Andres
"""

import os
import numpy as np
import glob
import itertools

from .parameter import *
from .parameter_space import *
from .datapool import *

def extract_parameter_space_data(data_dir, config_file, 
            parameter_start_key, parameter_end_key,
            parameter_increment_key, debug = False):

    sub_dirs = []
    for it in os.scandir(data_dir):
        if it.is_dir():
            if os.path.exists(it.path + '/' + config_file):
                sub_dirs.append(it.path)

    all_spaces = []
    for sub_dir in sub_dirs:
        all_spaces.append(
            _tinc_extract_parameters(sub_dir + '/' + config_file, parameter_start_key, parameter_end_key, parameter_increment_key, debug = debug))
    return _tinc_merge_spaces(all_spaces)

'''
Use output files in subdirectories to create ParameterSpace and DataPool


'''
def create_datapool_from_output(data_root, output_file, read_file_func = None, \
                    ignore_params = [], depth = 3, dp_name = "dp", ps_name = "ps", debug = False):
    if read_file_func is None:
        read_file_func = _tinc_default_read_function_for_create_datapool
    ps = extract_parameter_space_from_output(data_root, output_file, read_file_func, \
            ignore_params, depth, ps_name, debug)
    ps.set_root_path('') # Full path is currently used as id. 
    # TODO determine file type
    if output_file[-5:] == '.json':
        dp = DataPoolJson(dp_name, ps, "slices")
    else:
        raise ValueError("Unsupported type for output file")

    fs_param = None
    for dim in ps.get_dimensions():
        if not ps.is_filesystem_dimension(dim.id):
            fs_param = dim.id

    if fs_param is None:
        # raise ValueError("Can't identify a parameter in output files.")
        print("Can't identify a parameter in output files.")
        return None
    else:
        dp.register_data_file(output_file, fs_param)
    return dp,ps

# read_file_func shoud return a dictionary in this form:
# {"param_name": [val1, val2, val3 .... valn]}
def extract_parameter_space_from_output(data_root, output_file, read_file_func, ignore_params = [], \
        depth = 3, ps_name = "ps", debug = False):
    all_params = _tinc_get_params_in_files(data_root, output_file, read_file_func, depth, debug)
    consistent_params_data = _tinc_extract_consistent_params(all_params, ignore_params)
    ps = make_parameter_space_from_dict(consistent_params_data, data_root, ps_name)
    template = ''
    for param_name in consistent_params_data:
        if len(ps.get_dimension(param_name).ids):
            template += f"{param_name},"
    if len(template) > 0:
        if template.count(',') == 1:  
            template = "%%" + template[:-1] + ":ID%%"
        else:
            template = "%%" + template[:-1] + "%%"
    if debug:
        print(f"Set parameter space path template to {template}")
    ps.set_current_path_template(template)
    return ps

def make_parameter_space(data_dir, config_file, parameter_start_key, parameter_end_key, parameter_increment_key, ps_name = None, debug = False):
    if ps_name is None:
        ps_name = config_file
    merged_space = extract_parameter_space_data(data_dir, config_file, parameter_start_key, parameter_end_key, parameter_increment_key)

    ps = make_parameter_space_from_dict(merged_space, data_dir, ps_name, debug)
    return ps

# Each dictionary entry can be in this form:
# {"param_name": [val1, val2, val3 .... valn]}
# or:
# {"param_name": {"space" : [val1, val2, val3 .... valn], "ids": ["id1", "id2" ... "idn"]} }
def make_parameter_space_from_dict(merged_space, data_dir = None, ps_name = None, debug = False):

    ps = ParameterSpace(ps_name)
    if not data_dir is None:
        ps.set_root_path(data_dir)

    for name, data in merged_space.items():
        new_param = Parameter(name)
        if type(data) == dict:
            if len(data['space']) != len(data['ids']):
                raise ValueError(f"Size mismatch between values and ids for {name}")
            # TODO validate space and ids
            new_param.values = data['space']
            new_param.ids = data['ids']
        else:
            new_param.values = data
        new_param.sort()
        if debug:
            print(f"Added parameter {new_param.id}")
        ps.register_parameter(new_param)
    return ps

#######################################################
# internal functions
def _tinc_default_read_function_for_create_datapool(path):
    import json
    with open(path) as f:
        j = json.load(f)
    return j

def _tinc_get_params_in_files(data_root, output_file, read_file_func, depth = 3, debug = False):
    glob_expr = data_root + '/'
    all_files = []
    for i in range(depth):
        all_files.extend(glob.glob(glob_expr + output_file, recursive=True))
        glob_expr += "*/"
    all_params = {}
    for f in all_files:
        new_params = read_file_func(f)
        # Validate output from function
        if type(new_params) != dict:
            raise ValueError(f"read_file_func return value not a dictionary for {f}")
        for name, space in new_params.items():
            try:
                list(space)
            except:
                raise ValueError(f"read_file_func parameter space not a list for {name} in {f}")

        if debug:
            print(f"Explored file: {f}")
            if len(new_params) == 0:
                print(f'Warning no params found in file {f}')
        all_params[f] = new_params
    return all_params

def _tinc_extract_consistent_params(all_params, ignore_params = []):
    param_cache = {}
    param_consistent = []
    for path, params in all_params.items():
        for param_name, param_space in params.items():
            if not _tinc_check_list_all_equal(param_space):
                # Discard is all values equal
                if not param_name in param_cache:
                    param_cache[param_name] = param_space
                    param_consistent.append(param_name)
                else:
                    if not param_cache[param_name] == param_space and param_consistent.count(param_name) > 0:
                        param_consistent.remove(param_name)
    
    consistent_params_data = {}
    if len(param_consistent) > 0:
        print(f"Found more than one potential parameter in files:{param_consistent} ")
        for ignore in ignore_params:
            while ignore in param_consistent:
                param_consistent.remove(ignore)
        print(f"Using:{param_consistent[0]} ")
        consistent_params_data[param_consistent[0]] = param_cache[param_consistent[0]]
    else:
        consistent_params_data[param_consistent[0]] = param_cache[param_consistent[0]]
        
    fs_params = _tinc_extract_filesystem_params(all_params)
    fs_final_params ={}
    # It is guaranteeed that these parameters have only one value in their space
    # That is what defines them as filesystem parameters
    for path, params in fs_params.items():
        for param_name, data in params.items():
            if not param_name in ignore_params:
                if not param_name in fs_final_params:
                    fs_final_params[param_name] = {'space':[data], 'ids':[path]}
                else:
                    fs_final_params[param_name]['space'].append(data)
                    fs_final_params[param_name]['ids'].append(path)

    # Remove paramaters that have a single value 
    # (i.e. a single value maps to all filesystem paths)
    params = list(fs_final_params.keys())
    for name in params:
        if _tinc_check_list_all_equal(fs_final_params[name]['space']):
            fs_final_params.pop(name)
        
    consistent_params_data.update(fs_final_params)
    return consistent_params_data

def _tinc_extract_filesystem_params(all_params):
    param_filesystem = {}
    for full_path, params in all_params.items():
        if os.path.isdir(full_path):
            path = full_path
        else:
            path = os.path.dirname(full_path)
        param_filesystem[path] = {}
        for param_name, param_space in params.items():
            reduced_space = _tinc_reduce_list(param_space)
            if len(reduced_space) == 1:
                param_filesystem[path][param_name] = reduced_space[0]

    return param_filesystem

def _tinc_check_list_all_equal(iterator: iter):
    iterator = iter(iterator)
    try:
        first = next(iterator)
    except StopIteration:
        return True
    return all(first == rest for rest in iterator)
    
def _tinc_reduce_list(input_list):
    if _tinc_check_list_all_equal(input_list):
        return [input_list[0]]
    else:
        return input_list

def _tinc_get_param_condition(parameter_key, j):
    sub_entry = j
    param_condition = {}
    for key in parameter_key.split('/'):
        if key != '*':
            sub_entry = sub_entry[key]
        else:
            param_condition = sub_entry
            break
    if len(param_condition) == 0:
        param_condition = sub_entry
    return param_condition


def _tinc_generate_parameter_space_values(start_value, end_value, increment_value, end_point = True):
    try:
        start_value = float(start_value)
        end_value = float(end_value)
        increment_value = float(increment_value)
        if start_value == end_value:
            if increment_value == start_value:
                return None
            if increment_value != 0:
                increment_value = 0
                print("Forcing increment value to 0")
            return np.array([start_value])
        if end_point:
            end_value = end_value + increment_value
        return np.arange(start_value, end_value, increment_value)
    except ValueError as e:
        print("not a float")
    except TypeError as e:
        print("not a type")
    return None

def _tinc_extract_parameters(config_file, parameter_start_key, parameter_end_key, parameter_increment_key, debug = False):
    
    param_space = {}
    import json
    with open(config_file) as f:
        j = json.load(f)
    param_starts = _tinc_get_param_condition(parameter_start_key,j)
    param_ends = _tinc_get_param_condition(parameter_end_key,j)
    param_increments = _tinc_get_param_condition(parameter_increment_key,j)
    common_params = []

    for param in param_starts.keys():
        if param in param_ends and param in param_increments:
            if type(param_starts[param]) == list and type(param_ends[param]) == list \
                and type(param_increments[param]) == list:
                if len(param_starts[param]) == len(param_ends[param]) \
                    and len(param_starts[param]) == len(param_increments[param]):
                    # TODO we need to validate types (e.g. dict, list, but allowing some type conversions, e.g. float is a valid match to int)
                    # TODO we also need to validate sizes and types recursively.
                    common_params.append(param)
            else:
                common_params.append(param)
    
    for param in common_params:
        # TODO allow separate path for integers
        if type(param_starts[param]) == dict:
            for key, value in param_starts[param].items():
                space = _tinc_generate_parameter_space_values(param_starts[param][key], param_ends[param][key], param_increments[param][key])
                if space is not None:
                    param_space[param + f'({key})'] = space
        else:
            space = _tinc_generate_parameter_space_values(param_starts[param], param_ends[param], param_increments[param])
            if space is not None:
                param_space[param] = space
    return param_space

def _tinc_merge_spaces(all_spaces):
    merged_space = {}
    for space in all_spaces:
        for param_name, space in space.items():
            if not param_name in merged_space:
                merged_space[param_name] = space
            else:
                for value in space:
                    if not value in merged_space[param_name]:
                        merged_space[param_name] = np.append(merged_space[param_name],value)

    for param_name, data in merged_space.items():
        merged_space[param_name] = np.sort(merged_space[param_name])
        
    return merged_space
