# -*- coding: utf-8 -*-
"""
Created on Mon Aug  9 15:47:18 2021

@author: Andres
"""

import os

class DistributedPath(object):

    def __init__(self, filename = '', relative_path ='', root_path ='', protocol_id = ''):
        self.filename = filename
        self.relative_path = relative_path
        self.root_path = root_path
        self.protocol_id = protocol_id

    def __eq__(self, other):
        if isinstance(other, DistributedPath):
            return self.filename == other.filename and \
                self.relative_path == other.relative_path and \
                self.root_path == other.root_path and \
                self.protocol_id == other.protocol_id
        return False
    
    def get_full_path(self):
        return self.root_path + self.relative_path
    
    def set_paths(self, rel_path, root_path):
        if rel_path != '':
            if rel_path[-1] != '/' and rel_path[-1] != '\\':
                rel_path += '/'
            self.relative_path = rel_path
            #TODO create path if not present
            if root_path != '':
                if root_path[-1] != '/' and root_path[-1] != '\\':
                    root_path += '/'
                self.root_path = root_path
            else:
                if os.path.isabs(self.relative_path):
                    self.root_path = ''
                else:
                    self.root_path = os.getcwd() + '/'
            if not os.path.exists(self.get_full_path()):
                os.makedirs(self.get_full_path())
        else:
            self.relative_path = ''
            if root_path != '':
                if root_path[-1] != '/' and root_path[-1] != '\\':
                    root_path += '/'
                self.root_path = root_path
            else:
                self.root_path = os.getcwd() + '/'
            
            if not os.path.exists(self.get_full_path()):
                os.makedirs(self.get_full_path())