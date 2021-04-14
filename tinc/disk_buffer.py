import json
import os
import re

from .tinc_object import TincObject

from filelock import FileLock
from .tinc_protocol_pb2 import DiskBufferType

class DiskBuffer(TincObject):
    def __init__(self, tinc_id, db_type, base_filename, path, tinc_client = None):
        super().__init__(tinc_id)
        self.type = db_type
        
        self._data = None
        self._base_filename:str = base_filename
        self._path:str = path
        if not path == '' and not os.path.exists(path):
            os.makedirs(path)
        
        self._round_robin_size  = None
        self._round_robin_counter: int = 0
        
        self._file_lock:bool = False
        self._lock = None
        
        self.tinc_client = tinc_client
        pass
    
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
        self._data = data
        
        # TODO implement file lock
        
        outname = self._make_next_filename()
        
        if self._file_lock:
            self._lock = FileLock(self._path + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()
        with open(self._path + outname, 'w') as outfile:
            json.dump(data, outfile)
            
        if self.tinc_client:
            self.tinc_client.send_disk_buffer_current_filename(self, outname)
    
        if self._file_lock:
            self._lock.release()
            
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
        if self._path == '' or filename.find(self._path) == 0:
            filename = filename[len(self._path):]
        else:
            # TODO more robust checking that we are managing that file.
            raise ValueError('Invalid filename')

        if self.tinc_client:
            self.tinc_client.send_disk_buffer_current_filename(self, filename)
            
        if self._file_lock:
            self._lock.release()
            self._lock = None
            
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
    
    