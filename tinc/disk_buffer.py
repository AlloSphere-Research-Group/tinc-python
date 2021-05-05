import json
import os
import re
import traceback
import numpy as np

from .tinc_object import TincObject

from filelock import FileLock

import netCDF4

DiskBufferType = {'BINARY':0, 'TEXT': 1, 'NETCDF': 2, 'JSON': 3, 'IMAGE': 4}

# This is a base class for disk buffers. All children class must implement the data setter function
class DiskBuffer(TincObject):
    def __init__(self, tinc_id, base_filename, path, tinc_client = None):
        super().__init__(tinc_id)
        
        self._data = None
        self._base_filename:str = base_filename
        self._path:str = path
        if not path == '' and not os.path.exists(path):
            os.makedirs(path)
        
        self._round_robin_size  = None
        self._round_robin_counter: int = 0
        
        self._file_lock:bool = False
        self._lock = None
        
        self._filename = ''
        
        self.tinc_client = tinc_client
        pass
    
    def get_current_filename(self):
        return self._filename
    
    def load_data(self, filename):
        self._data = self._parse_file(filename)
        self.done_writing_file(filename)
        # TODO implement update callbacks
    
    def get_base_filename(self):
        return self._base_filename
    
    def set_base_filename(self, filename):
        # TODO validate string
        self._base_filename = filename
        
    def get_path(self):
        return self._path
    
    def set_path(self, path):
        # TODO validate path
        self._path = path
                 
    def cleanup_round_robin_files(self):
        prefix, suffix = self._get_file_components()
        if os.path.exists(self._path):
            files = [f for f in os.listdir(self._path) if re.match(prefix + '(_[0-9]+)?' + suffix + '(.lock)?', f)]
            for f in files:
                    os.remove(self._path + f)
    
    def enable_round_robin(self, cache_size = 0, clear_locks: bool = True):
        # 0 is unlimited cache
        self._round_robin_size = cache_size
        if self._round_robin_counter >= cache_size:
            self._round_robin_counter = 0
        if self._file_lock:
            # To force clearing locks. Should this be optional?
            self.use_file_lock(self._file_lock, clear_locks)
    
    def use_file_lock(self, use:bool = True, clear_locks: bool = True):
        self._file_lock = use
        try:
            if self._round_robin_size == None:
                os.remove(self._path + self._base_filename)
            else:
                files = [f for f in os.listdir(self._path) if re.match(r'.*_[0-9]+.*\.lock', f)]
                for f in files:
                    os.remove(self._path + f)
        except:
            pass
        
    @property
    def data(self):
        return self._data
        
    @data.setter
    def data(self, data):
        raise RuntimeError("You must use a specialized DiskBuffer, not the DiskBuffer base class")
    
    def get_filename_for_writing(self, timeout_secs = 0):
        # TODO implement timeout when locked.
        outname = ''
        if self._file_lock:
            if self._lock:
                print("Error, file is locked")
                return ''
            
            outname = self._make_next_filename()
            self._lock = FileLock(self._path + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("File is locked " + outname)
            self._lock.acquire()
        else:
            outname = self._make_next_filename()
        self.outname = outname
        return self._path + outname
    
    def done_writing_file(self, filename: str =''):
        print(filename)
        if self._path == '' or filename.find(self._path) == 0:
            filename = filename[len(self._path):]

        self._filename = filename
        if self.tinc_client:
            self.tinc_client.send_disk_buffer_current_filename(self, filename)
            
        if self._file_lock:
            self._lock.release()
            self._lock = None
   
    def _parse_file(filename):
        # Reimplement in sub classes
        raise RuntimeError("load_data() not implemented. Don't use DiskBuffer directly")
        
    def _make_next_filename(self):
        outname = self._base_filename
        
        if self._round_robin_size is not None and self._round_robin_size >=0:
            if self._round_robin_size > 0 and self._round_robin_counter == self._round_robin_size:
                self._round_robin_counter = 0
            outname = self._make_filename(self._round_robin_counter)
            self._round_robin_counter += 1
        return outname
        
    def _make_filename(self, index):
        prefix, suffix = self._get_file_components()
        outname = prefix + '_' + str(index) + suffix
        return outname
    
    def _get_file_components(self):
        outname = self._base_filename
        try:
            index_dot = outname.index('.')
            prefix = outname[0: index_dot]
            suffix = outname[index_dot:]
        except:
            prefix = outname
            suffix = ''
        return [prefix, suffix]
    
    def print(self):
        print(f" ** DiskBuffer: '{self.id}' type {self.type}")
        print(f'      path: {self._path} basename: {self._base_filename}')
    
class JsonDiskBuffer(DiskBuffer):
    
    def __init__(self, tinc_id, base_filename, path = '', tinc_client = None):
        super().__init__(tinc_id, base_filename, path, tinc_client)
        self.type = DiskBufferType['JSON']

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
        
        # TODO implement file lock
        
        outname = self._make_next_filename()
        
        if self._file_lock:
            self._lock = FileLock(self._path + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()
        try:
            if type(data) == list:
                self._write_from_array(data, self._path + outname)
            if type(data) == np.ndarray:
                self._write_from_array(data, self._path + outname)
            if self.tinc_client:
                    self.tinc_client.send_disk_buffer_current_filename(self, outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()
        if self.tinc_client:
            self.tinc_client.send_disk_buffer_current_filename(self, outname)
    
        if self._file_lock:
            self._lock.release()
            
    def _parse_file(self, filename):
        with open(self.get_path() + filename) as fp:
            return json.load(fp)
        
    def _write_from_array(self, array, filename):
        with open(filename, 'w') as outfile:
            json.dump(array, outfile)

class DiskBufferBinary(DiskBuffer):
    def __init__(self, tinc_id, base_filename, path, tinc_client = None):
        super().__init__(tinc_id, base_filename, path, tinc_client)
        self.type = DiskBufferType['BINARY']

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        pass

class DiskBufferText(DiskBuffer):
    def __init__(self, tinc_id, base_filename, path, tinc_client = None):
        super().__init__(tinc_id, base_filename, path, tinc_client)
        self.type = DiskBufferType['TEXT']

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        pass

class DiskBufferImage(DiskBuffer):
    def __init__(self, tinc_id, base_filename, path, tinc_client = None):
        super().__init__(tinc_id, base_filename, path, tinc_client)
        self.type = DiskBufferType['IMAGE']

    def set_image():
        pass

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        pass

class DiskBufferNetCDFData(DiskBuffer):

    def __init__(self, tinc_id, base_filename, path, tinc_client = None):
        super().__init__(tinc_id, base_filename, path, tinc_client)
        self.type = DiskBufferType['NETCDF']

    def write_from_array(array, filename):
        with open(filename, 'w') as outfile:
            json.dump(data, outfile)

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
        
        # TODO implement file lock
        
        outname = self._make_next_filename()
        
        if self._file_lock:
            self._lock = FileLock(self._path + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()
        try:
            if type(data) == list:
                write_from_array(data, self._path + outname)
            if type(data) == np.ndarray:
                write_from_array(data, self._path + outname)
            else:
                raise ValueError("Unsupported format for data in NETCDFDiskBuffer")
            if self.tinc_client:
                self.tinc_client.send_disk_buffer_current_filename(self, outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()
    
        if self._file_lock:
            self._lock.release()


    def _parse_file(self, filename):
        # TODO being called twice on startup. investigate
        self._data = np.array(netCDF4.Dataset(self.get_path() +filename, mode='r').variables["data"][:])
        self._filename = filename
    