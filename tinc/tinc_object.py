# -*- coding: utf-8 -*-
"""
Created on Tue Dec  8 11:08:40 2020

@author: Andres
"""

tinc_version_major = 0
tinc_version_minor = 9

def TincVersion():
    print(str(tinc_version_major) + "." + str(tinc_version_minor))

class TincObject(object):
    def __init__(self, tinc_id = ''):
        self.id = tinc_id
        self.documentation = '' # TODO add protections to avoid overwriting documentation
        self.remote = False
        self.remote_stale = False
        self.server_timeout = 30