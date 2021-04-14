# -*- coding: utf-8 -*-
"""
Created on Thu Oct 15 14:32:03 2020

@author: Andres
"""

import json
import os

# FIXME use more robust cache metadata defined in the metadata schema

class CacheManager(object):
    def __init__(self, directory = "python_cache"):
        if not os.path.exists(directory):
            os.makedirs(directory)
        self._cache_dir = directory
        
    def construct_filename(self, args):
        # TODO allow setting filename template.
        filename = self._cache_dir + '/cache_'
        # TODO more robust checks for arguments and source process
        for param_id, value in args.items():
            filename += f'{value}_'
        filename = filename[:-1]
        return filename
        
    def store_cache(self, data, args):
        with open(self.construct_filename(args), 'w') as fp:
            json.dump(data, fp)
            print(f"stored cache: {self.construct_filename(args)}")
    
    def load_cache(self, args):
        data = None
        filename = self.construct_filename(args)
        if os.path.exists(filename):
            with open(filename) as fp:
                data = json.load(fp)
                
                print(f"loaded cache: {filename}")
        return data
    
    def remove_cache_file(self, args):
        
        filename = self.construct_filename(args)
        if os.path.exists(filename):
            print(f"removing {filename}")
            os.remove(filename)