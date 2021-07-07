import json
import os
import re
from sys import platform
import traceback
import numpy as np

from .tinc_object import TincObject

from filelock import FileLock

import netCDF4
from PIL import Image

try:
    from ipywidgets import interact, interactive, interact_manual
    import ipywidgets as widgets
except:
    print("Can't import ipywidgets. Notebook widgets not available")

try:
    import matplotlib.pyplot as plt
except:
    print("Matplotlib not available. DiskBufferImage will not work.")

DiskBufferType = {'BINARY':0, 'TEXT': 1, 'NETCDF': 2, 'JSON': 3, 'IMAGE': 4}

# This is a base class for disk buffers. All children class must implement the data setter function
class DiskBuffer(TincObject):
    def __init__(self, tinc_id, base_filename, path, tinc_client = None):
        super().__init__(tinc_id)
        
        self._data = None
        self._base_filename:str = base_filename
        
        if not path == '':
            if path[-1] != '\\' and path[-1] != "/":
                path += '/'
            if not os.path.exists(path):
                os.makedirs(path)
        
        self._path:str = path
        
        self._round_robin_size  = None
        self._round_robin_counter: int = 0
        
        self._file_lock:bool = False
        self._lock = None
        
        self._filename = ''

        self.type = None # Set this in all derived classes
        
        self.tinc_client = tinc_client
        self._interactive_widget = None
        pass
    
    def get_current_filename(self):
        return self._filename
    
    def load_data(self, filename, notify = True):
        if filename == '':
            self._data = None
            self._filename = ''
            return
        self._data = self._parse_file(filename)
        self.done_writing_file(filename, notify)
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
    
    def enable_round_robin(self, cache_size = 2, clear_locks: bool = True):
        # 0 is unlimited cache
        self._round_robin_size = cache_size
        self._round_robin_counter = int(cache_size/2)
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
        file_path = ' '
        if self.tinc_client:
            file_path = self.tinc_client._working_path

        file_path += self._path + outname
        return file_path
    
    def done_writing_file(self, filename: str ='', notify = True):
        # print(filename)
        if self._path == '' or filename.find(self._path) == 0:
            filename = filename[len(self._path):]

        self._filename = filename
        if notify and self.tinc_client:
            self.tinc_client.send_disk_buffer_current_filename(self, filename)
            
        if self._file_lock:
            self._lock.release()
            self._lock = None
   
    def _parse_file(self, filename):
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
    
class DiskBufferJson(DiskBuffer):
    
    def __init__(self, tinc_id, base_filename, path = '', tinc_client = None):
        super().__init__(tinc_id, base_filename, path, tinc_client)
        self.type = DiskBufferType['JSON']

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
        
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

    def _parse_file(self, filename):
        with open(self.get_path() + filename) as fp:
            return fp.read()
        
    def _write_from_array(self, array, filename):
        with open(filename, 'wb') as outfile:
            outfile.write(array)

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

    def _parse_file(self, filename):
        pass


#### DiskBufferImage ###
# Data is a PIL.Image object
class DiskBufferImage(DiskBuffer):
    def __init__(self, tinc_id, base_filename, path, tinc_client = None):
        super().__init__(tinc_id, base_filename, path, tinc_client)
        self.type = DiskBufferType['IMAGE']

    def write_pixels(self, pixels):
        self.data = pixels

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        '''Data can be set as a python list, a numpy ndarray or a PIL.Image.
        Data is always stored in memory as PIL.Image, which is what is returned
        by the data property.
        '''
    
        outname = self._make_next_filename()
        
        if self._file_lock:
            self._lock = FileLock(self._path + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()
        try:
            if type(data) == list:
                nparray = np.asarray(data)
                im = Image.fromarray(nparray.astype(np.uint8))
                self._data = im
                im.save(self._path + outname)
            elif type(data) == np.ndarray:
                im = Image.fromarray(data)
                self._data = im
                im.save(self._path + outname)
            elif type(data) == Image:
                data.save(self._path + outname)
                self._data = data
            if self._interactive_widget:
                self._interactive_widget.value = data
            if self.tinc_client and self.tinc_client.connected:
                    self.tinc_client.send_disk_buffer_current_filename(self, outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()
    
        if self._file_lock:
            self._lock.release()


    def interactive_widget(self):
        self._interactive_widget = widgets.Image(
            #     value=image,
                format='png',
                width=300,
                height=400,);
        return self._interactive_widget

    def _parse_file(self, filename):
        print(f'parsing: {self.get_path() + filename}')
        return Image.open(self.get_path() + filename)

class DiskBufferNetCDFData(DiskBuffer):

    def __init__(self, tinc_id, base_filename, path, tinc_client = None):
        super().__init__(tinc_id, base_filename, path, tinc_client)
        self.type = DiskBufferType['NETCDF']
        self.enable_round_robin()
        self._attrs = {}

    def write_from_array(self, array, filename, attributes = {}):
        # TODO more flexible data types
        datatype = np.float32
        outfile = netCDF4.Dataset(self.get_path() + filename, mode='w', format='NETCDF4')
        dim = outfile.createDimension('data_dim', size=len(array))
        var = outfile.createVariable('data', datatype,('data_dim'), zlib=True)
        for name, value in attributes.items():
            # TODO validate values for attributes
            setattr(var, name, value)
        var[:] = array
        outfile.close()
        # Hack to ensure file has been released for others to read.
        try:
            f = open(self.get_path() + filename)
            f.close()
        except:
            print("ERROR attempting to open newly created buffer file " + self.get_path() + filename)

    def set_attributes(self, attrs):
        self._attrs = attrs

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        
        # TODO implement file lock
        
        outname = self._make_next_filename()
        
        if self._file_lock:
            self._lock = FileLock(self._path + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()
        try:
            if outname.find(self._path) == 0:
                fname = outname
            else:
                fname = self._path + outname
            if type(data) == list:
                self.write_from_array(data, outname, self._attrs)
            elif type(data) == np.ndarray:
                self.write_from_array(data, outname, self._attrs)
            else:
                raise ValueError(f"Unsupported format for data in NETCDFDiskBuffer: {type(data)}")
            
            self._data = data
            self._filename = outname
            if self.tinc_client:
                self.tinc_client.send_disk_buffer_current_filename(self, outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()
    
        if self._file_lock:
            self._lock.release()


    def _parse_file(self, filename):
        # TODO being called twice on startup. investigate
        
        # print(self.get_path())
        # print(filename)
        f = netCDF4.Dataset(self.get_path() +filename, mode='r')
        return np.array(f.variables["data"][:])
    