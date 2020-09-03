# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 17:13:15 2020

@author: Andres
"""

class ParameterSpace(object):
    def __init__(self, name = ''):
        self.id = name
        
        
    def print(self):
        print(f" ** ParameterSpace {self.id}")