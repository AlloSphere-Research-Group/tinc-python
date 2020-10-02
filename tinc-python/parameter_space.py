# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 17:13:15 2020

@author: Andres
"""

class ParameterSpace(object):
    def __init__(self, name = '', tinc_client = None):
        self.id = name
        self.tinc_client = tinc_client
        
    def get_current_path(self):
        if self.tinc_client:
            return self.tinc_client.command_parameter_space_get_current_path(self)
        
    def get_root_path(self):
        if self.tinc_client:
            return self.tinc_client.command_parameter_space_get_root_path(self)
 
    def print(self):
        print(f" ** ParameterSpace {self.id}")