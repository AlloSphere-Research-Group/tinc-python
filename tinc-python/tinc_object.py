# -*- coding: utf-8 -*-
"""
Created on Tue Dec  8 11:08:40 2020

@author: Andres
"""

class TincObject(object):
    def __init__(self, tinc_id = ''):
        self.id = tinc_id
        self.remote = False
        self.remote_stale = False