# -*- coding: utf-8 -*-
"""
Created on Mon Oct  4 17:13:15 2021

@author: Andres
"""

import os
import numpy as np

from .parameter import *
from .parameter_space import *

def extract_parameter_space_data(data_dir, config_file, 
            parameter_start_key, parameter_end_key,
            parameter_increment_key):

    sub_dirs = []
    for it in os.scandir(data_dir):
        if it.is_dir():
            if os.path.exists(it.path + '/' + config_file):
                sub_dirs.append(it.path)

    all_spaces = []
    for sub_dir in sub_dirs:
        all_spaces.append(
            _tinc_extract_parameters(sub_dir + '/' + config_file, parameter_start_key, parameter_end_key, parameter_increment_key))
    return _tinc_merge_spaces(all_spaces)

def make_parameter_space(data_dir, config_file, parameter_start_key, parameter_end_key, parameter_increment_key, ps_name = None):

    if ps_name is None:
        ps_name = config_file
    merged_space = extract_parameter_space_data(data_dir, config_file, parameter_start_key, parameter_end_key, parameter_increment_key)

    ps = ParameterSpace(ps_name)
    ps.set_root_path(data_dir)

    for name, data in merged_space.items():
        new_param = Parameter(name)
        new_param.values = data['space']
        ps.register_parameter(new_param)
    return ps

#######################################################
# internal functions
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

def _tinc_extract_parameters(config_file, parameter_start_key, parameter_end_key, parameter_increment_key):
    
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
                    param_space[param + f'({key})'] = {"space": space}
        else:
            space = _tinc_generate_parameter_space_values(param_starts[param], param_ends[param], param_increments[param])
            if space is not None:
                param_space[param] = {"space": space}
    return param_space

def _tinc_merge_spaces(all_spaces):
    merged_space = {}
    for space in all_spaces:
        for param_name, space in space.items():
            if not param_name in merged_space:
                merged_space[param_name] = space
            else:
                for value in space['space']:
                    if not value in merged_space[param_name]['space']:
                        merged_space[param_name]['space'] = np.append(merged_space[param_name]['space'],value)

    for param_name, data in merged_space.items():
        merged_space[param_name]['space'] = np.sort(merged_space[param_name]['space'])
        
    return merged_space
