import json
import os
import re

from parameter_server import ParameterServer

from filelock import FileLock

class DiskBufferWriter(object):
    def __init__(self, name, filename, path):
        self._data = None
        self.name:str = name
        self._filename:str = filename
        self._path:str = path
        if not os.path.exists(path):
            os.makedirs(path)
        
        self._cache_size:int  = -1
        self._cache_counter: int = 0
        
        self._file_lock:bool = False
        pass
    
    def cleanup_cache(self):
        prefix, suffix = self._get_file_components()
        if os.path.exists(self._path):
            files = [f for f in os.listdir(self._path) if re.match(prefix + '(_[0-9]+)?' + suffix + '(.lock)?', f)]
            for f in files:
                    os.remove(self._path + f)
    
    def allow_cache(self, cache_size: int = 0):
        # 0 is unlimited cache
        self._cache_size = cache_size
        if self._file_lock:
            # To force clearing locks. Should this be optional?
            self.use_file_lock()
    
    def use_file_lock(self, use:bool = True, clear_locks: bool = True):
        self._file_lock = use
        try:
            if self._cache_size == -1:
                os.remove(self._path + self._filename)
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
        
        for l in self.pserver.listeners:
            address = "/__DiskBuffer/" + self.name
            
#             print('sending ' + address)
#             print(l.__dict__)
            l.send_message(address, outname)
    
        
        if self._file_lock:
            self._lock.release()
            
    def get_filename_for_writing(self):
        outname = ''
        if self._file_lock:
            if self._lock:
                print("Error, file is locked")
                return ''
            
            outname = self._make_next_filename()
            self._lock = FileLock(self._path + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()
        else:
            outname = self._make_next_filename()
        self.outname = outname
        return self._path + outname
    
    def done_writing_file(self, filename: str =''):
        if filename.find(self._path) == 0:
            filename = filename[len(self._path):]
        else:
            # TODO more robust checking that we are managing that file.
            raise ValueError('Invalid filename')
        for l in self.pserver.listeners:
            address = "/__DiskBuffer/" + self.name
            
#             print('sending ' + address)
#             print(l.__dict__)
            # TODO check that we are actually managing this file, as it is a vector for attack in unsecure networks.
            l.send_message(address, filename)
        if self._file_lock:
            self._lock.release()
            
    def expose_to_network(self, pserver: ParameterServer):
        self.pserver = pserver
        
    def _make_next_filename(self):
        outname = self._filename
        
        if self._cache_size >=0:
            if self._cache_size > 0 and self._cache_counter == self._cache_size:
                self._cache_counter = 0
            outname = self._make_filename(self._cache_counter)
            self._cache_counter += 1
        return outname
        
    def _make_filename(self, index):
        prefix, suffix = self._get_file_components()
        outname = prefix + '_' + str(index) + suffix
        return outname
    
    def _get_file_components(self):
        outname = self._filename
        try:
            index_dot = outname.index('.')
            prefix = outname[0: index_dot]
            suffix = outname[index_dot:]
        except:
            prefix = outname
            suffix = ''
        return [prefix, suffix]
    
    