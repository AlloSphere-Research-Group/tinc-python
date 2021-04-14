# -*- coding: utf-8 -*-
"""
Created on Wed Sep  2 10:41:37 2020

@author: Andres
"""


import struct

data_types = { 'DATA_DOUBLE' : 0x01, 'DATA_INT64' : 0x02, 'DATA_STRING' : 0x03 }

class Message(object):
    def __init__(self, data = None):
        if data is None:
            self.data = bytearray(0)
        else:
            self.data = data
        self.read_counter = 0
    
    def empty(self):
        return len(self.data) == 0 or self.read_counter == len(self.data)
    
    def remaining_bytes(self):
        return self.data[self.read_counter:]
    
    # Read functions -----------------------------------
    
    def get_byte(self):
        b = self.data[self.read_counter]
        self.read_counter += 1
        return b
    
    def get_uint16(self):
        b = struct.unpack('H', self.data[self.read_counter: self.read_counter + 2])
        self.read_counter += 2
        return b[0]
    
    def get_uint32(self):
        b = struct.unpack('L', self.data[self.read_counter: self.read_counter + 4])
        self.read_counter += 4
        return b[0]
    
    def get_int32(self):
        b = struct.unpack('i', self.data[self.read_counter: self.read_counter + 4])
        self.read_counter += 4
        return b[0]
    
    def get_uint64(self):
        b = struct.unpack('Q', self.data[self.read_counter: self.read_counter + 8])
        self.read_counter += 8
        return b[0]
    
    def get_float(self):
        b = struct.unpack('f', self.data[self.read_counter: self.read_counter + 4])
        self.read_counter += 4
        return b[0]
    
    def get_string(self):
        start_counter = self.read_counter
        s = ''
        while len(self.data) > self.read_counter and not self.data[self.read_counter] == ord('\x00'):
            self.read_counter += 1
        if self.read_counter > start_counter:
            s = self.data[start_counter:self.read_counter].decode("utf-8")
        self.read_counter += 1
        return s
    
    def get_variant(self):
        data_type = self.data[self.read_counter]
        self.read_counter += 1
        value = None
        if data_type == data_types['DATA_DOUBLE']:
            value = struct.unpack('d', self.data[self.read_counter: self.read_counter +8])
            self.read_counter += 8
        elif data_type == data_types['DATA_INT64']:
            value = struct.unpack('q', self.data[self.read_counter: self.read_counter +8])
            self.read_counter += 8
        elif data_type == data_types['DATA_STRING']:
            start = self.read_counter
            while len(self.data) > self.read_counter and not self.data[self.read_counter] == b'\x00':
                self.read_counter += 1;
            
            value = str(self.data[start: self.read_counter])
            self.read_counter += 1 # Skip null

        return value
    
    
    def get_vector_string(self):
        count = self.data[self.read_counter]
        self.read_counter += 1
        members = []
        for i in range(count):
            new_member = self.get_string()
            members.append(new_member)
        
        return members

    def consume(self, num_bytes = -1):
        if num_bytes < 0:
            self.data = []
        else:
            self.data = self.data[num_bytes:]
    
    # Write functions ----------------------------------------------
    
    def append(self, data):
        if type(data) == bytes:
            self.data + data
        elif type(data) == int:
            self.data.append(data)
        else:
            self.data += data
    
    def insert_string(self, string):
        self.data += bytes(string, "utf8")
        self.data += b'\x00'
        
    def insert_as_uint16(self, int_value):
        self.data += struct.pack('H', int_value)
        
    def insert_as_uint32(self, int_value):
        self.data += struct.pack('L', int_value)
        
    def insert_vector_string(self, stringlist):
        if len(stringlist) > 254:
            raise ValueError("too many strings in vector")
        self.data += chr(len(stringlist))
        for s in stringlist:
            self.insert_string(s)