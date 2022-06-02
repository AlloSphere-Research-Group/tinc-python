import json
import os
import re
import io # to convert PIL image to bytes
from sys import platform
import traceback
import numpy as np

from .tinc_object import TincObject
#from .tinc_protocol_pb2 import DistributedPath as DistributedPath_proto
from .distributed_path import DistributedPath

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

class DiskBuffer(TincObject):
    '''Base class for all disk buffers.

    A DiskBuffer is a filesystem based buffer for distributed applications that allows notifying other
    nodes of changes. Although data is shared through the file system, the interface to disk buffer
    objects is presented as in memory data.

    The DiskBuffer subclasses implement specific data format decoding: :class:`tinc.diskbuffer.DiskBufferJson`,
    :class:`tinc.diskbuffer.DiskBufferImage`

    All children class must implement the data getter and setter functions and _parse_file
    '''
    def __init__(self, tinc_id, base_filename, rel_path = '', root_path = '', tinc_client = None):
        super().__init__(tinc_id)

        self.type = None # Set this in all derived classes
        self.tinc_client = tinc_client
        self.debug = False

         # Internal data
        self._data = None
        
        self.path = DistributedPath()
        self.path.filename = base_filename
        self.path.set_paths(rel_path, root_path)

        self._round_robin_size  = None
        self._round_robin_counter: int = 0
        
        self._file_lock:bool = False
        self._lock = None
        
        self._filename = ''
        
        self._interactive_widget = None

        self._update_callbacks = []
    
    def __str__(self):
        out = f" ** DiskBuffer: '{self.id}' type {self.type}"
        out += f'      path: {self.path.get_full_path()} basename: {self.path.filename}'
        return out

    @property
    def data(self):
        '''Read the data in the disk buffer. This data is cached in memory until changed.'''
        return self._data
        
    @data.setter
    def data(self, data):
        raise RuntimeError("You must use a specialized DiskBuffer, not the DiskBuffer base class")

    def get_current_filename(self):
        return self._filename
    
    def load_data(self, filename, notify = True):
        if filename == '':
            self._data = None
            self._filename = ''
            return
            
        if os.path.isabs(filename):
            file_path = filename
        else:
            file_path = self.get_full_path() + filename
        
        try:
            self._data = self._parse_file(file_path)
        except FileNotFoundError:
            self._data = None
            print(f"Disk buffer could not load file {file_path}")
        self.done_writing_file(file_path, notify)
        
        self._update_widget()
        for cb in self._update_callbacks:
            cb(self)
    
    def _update_widget(self):
        if self._interactive_widget:
            self._interactive_widget.value = self._data

    def get_base_filename(self):
        return self.path.filename
    
    def set_base_filename(self, filename):
        # TODO validate string
        self.path.filename = filename
        
    def get_relative_path(self):
        return self.path.relative_path
    
    def set_relative_path(self, rel_path):
        if not rel_path == '':
            if rel_path[-1] != '\\' and rel_path[-1] != "/":
                rel_path += '/'
            if not os.path.exists(rel_path):
                os.makedirs(rel_path)
        
        self.path.relative_path = rel_path

    def get_root_path(self):
        return self.path.root_path

    def get_full_path(self):
        path = self.get_root_path()
        if len(path) > 0:
            path += "/" 
        path += self.get_relative_path()
        return path

    def set_root_path(self, root_path):
        if not root_path == '':
            if root_path[-1] != '\\' and root_path[-1] != "/":
                root_path += '/'
            if not os.path.exists(root_path):
                os.makedirs(root_path)
        
        self.path.root_path = root_path
                 
    def cleanup_round_robin_files(self):
        prefix, suffix = self._get_file_components()
        if os.path.exists(self.path.get_full_path()):
            files = [f for f in os.listdir(self.path.get_full_path()) if re.match(prefix + '(_[0-9]+)?' + suffix + '(.lock)?', f)]
            for f in files:
                    os.remove(self.path.get_full_path() + f)
    
    def enable_round_robin(self, cache_size = 2, clear_locks: bool = True):
        # 0 is unlimited cache
        self._round_robin_size = cache_size
        self._round_robin_counter = int(cache_size/2)
        if self._file_lock:
            # To force clearing locks. Should this be optional?
            self.use_file_lock(self._file_lock, clear_locks)
    
    def use_file_lock(self, use:bool = True, clear_locks: bool = True):
        # TODO clear locks
        self._file_lock = use
        try:
            if self._round_robin_size == None:
                os.remove(self.path.get_full_path() + self.path.filename)
            else:
                files = [f for f in os.listdir(self.path.get_full_path()) if re.match(r'.*_[0-9]+.*\.lock', f)]
                for f in files:
                    os.remove(self.path.get_full_path() + f)
        except:
            pass
    
    def get_filename_for_writing(self, timeout_secs = 0):
        # TODO implement timeout when locked.
        outname = ''
        if self._file_lock:
            if self._lock:
                print("Error, file is locked")
                return ''
            
            outname = self._make_next_filename()
            self._lock = FileLock(self.path.get_full_path() + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("File is locked " + outname)
            self._lock.acquire()
        else:
            outname = self._make_next_filename()
        self._filename = outname
        file_path = ''
        #if self.tinc_client:
        #    file_path = self.tinc_client._working_path

        file_path += os.path.normpath(self.path.get_full_path() + outname)
        if self.debug:
            print(f'DiskBuffer file for writing: {file_path}')
        return file_path
    
    def done_writing_file(self, filename: str ='', notify = True):
        
        if self.get_full_path() == '' or os.path.normpath(filename).find(os.path.normpath(self.path.get_full_path())) == 0:
            filename = os.path.normpath(filename)[len(os.path.normpath(self.path.get_full_path())) + 1:]
        self._filename = filename

        if notify and self.tinc_client:
            self.tinc_client._send_disk_buffer_current_filename(self, filename)
            
        if self._file_lock:
            self._lock.release()
            self._lock = None

    def register_update_callback(self, f):
        for i,cb in enumerate(self._update_callbacks):
            if f.__name__ == cb.__name__ \
                and (cb.__qualname__.count('.') == 0 and f != cb):
                self._update_callbacks[i] = f
                if self.debug:
                    print("Replacing callback")
                return
        self._update_callbacks.append(f)
   
    def _parse_file(self, filename):
        # Reimplement in sub classes
        raise RuntimeError("load_data() not implemented. Don't use DiskBuffer directly")
        
    def _make_next_filename(self):
        outname = self.path.filename
        
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
        outname = self.path.filename
        try:
            index_dot = outname.index('.')
            prefix = outname[0: index_dot]
            suffix = outname[index_dot:]
        except:
            prefix = outname
            suffix = ''
        return [prefix, suffix]
    
    def lock(self, outname):
        if self._file_lock:
            # TODO support locking multiple files individually
            self._lock = FileLock(outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()

    def unlock(self,outname):
        if self._file_lock:
            self._lock.release()
    
class DiskBufferJson(DiskBuffer):
    def __init__(self, tinc_id, base_filename, rel_path = '', root_path = '', tinc_client = None):
        super().__init__(tinc_id, base_filename, rel_path, root_path, tinc_client)
        self.type = DiskBufferType['JSON']

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
        
        outname = self.get_filename_for_writing()
        
        self.lock(outname)
        try:
            if type(data) == list:
                self._write_from_array(data, outname)
            elif type(data) == np.ndarray:
                self._write_from_array(data, outname)
            elif type(data) == dict:
                self._write_from_dict(data, outname)
            else:
                raise ValueError("Unsupported data type")
            self.done_writing_file(outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()

        self.unlock(outname)
            
    def _parse_file(self, file_path):
        with open(file_path) as fp:
            return json.load(fp)
        
    def _write_from_array(self, array, filename):
        with open(filename, 'w') as outfile:
            json.dump(array, outfile)
    
    def _write_from_dict(self, data, filename):
        with open(filename, 'w') as outfile:
            json.dump(data, outfile)

class DiskBufferBinary(DiskBuffer):
    def __init__(self, tinc_id, base_filename, rel_path = '', root_path = '', tinc_client = None):
        super().__init__(tinc_id, base_filename, rel_path, root_path, tinc_client)
        self.type = DiskBufferType['BINARY']

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        pass

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        # TODO validata that data is binary
        self._data = data
        
        outname = self.get_filename_for_writing()
        
        self.lock(outname)
        try:
            with open(outname, 'wb') as fp:
                fp.write(self._data)
                self.done_writing_file(outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()

        self.unlock(outname)

    def _parse_file(self, file_path):
        with open(file_path, 'r') as fp:
            return fp.read()

class DiskBufferText(DiskBuffer):
    def __init__(self, tinc_id, base_filename, rel_path = '', root_path = '', tinc_client = None):
        super().__init__(tinc_id, base_filename, rel_path, root_path, tinc_client)
        self.type = DiskBufferType['TEXT']

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        # TODO validata that data can convert to str
        self._data = data
        
        outname = self.get_filename_for_writing()
        
        self.lock(outname)
        try:
            with open(outname, 'w') as fp:
                fp.write(self._data)
                self.done_writing_file(outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()

        if self._interactive_widget:
            self._interactive_widget.value = data
        self.unlock(outname)

    def _parse_file(self, file_path):
        with open(file_path, 'r') as fp:
            return fp.read()

    def interactive_widget(self):
        self._interactive_widget = widgets.HTML(
                 value=self.data,
            # disabled=False
            )
        return self._interactive_widget

#### DiskBufferImage ###
# Data is a PIL.Image object
class DiskBufferImage(DiskBuffer):
    def __init__(self, tinc_id, base_filename, path, root_path = '', tinc_client = None):
        super().__init__(tinc_id, base_filename, path, root_path, tinc_client)
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
            self._lock = FileLock(self.path.get_full_path() + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()
        try:
            if type(data) == list:
                nparray = np.asarray(data)
                im = Image.fromarray(nparray.astype(np.uint8))
                self._data = im
                im.save(self.path.get_full_path() + outname)
            elif type(data) == np.ndarray:
                im = Image.fromarray(data)
                self._data = im
                im.save(self.path.get_full_path() + outname)
            elif type(data) == Image:
                data.save(self.path.get_full_path() + outname)
                self._data = data
            if self._interactive_widget:
                self._interactive_widget.value = data
            if self.tinc_client and self.tinc_client.connected:
                    self.tinc_client._send_disk_buffer_current_filename(self, outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()
    
        if self._file_lock:
            self._lock.release()

    def _update_widget(self):
        if self._interactive_widget:
            imgByteArr = io.BytesIO()
            self._data.save(imgByteArr, format=self._data.format)
            self._interactive_widget.value = imgByteArr.getvalue()

    def interactive_widget(self):
        self._interactive_widget = widgets.Image(
            #     value=image,
                format='png',
                width=300,
                height=400,)
        return self._interactive_widget

    def _parse_file(self, file_path):
        if self.debug:
            print(f'parsing: {file_path}')
        return Image.open(file_path)

class DiskBufferNetCDFData(DiskBuffer):

    def __init__(self, tinc_id, base_filename, rel_path = '', root_path = '', tinc_client = None):
        super().__init__(tinc_id, base_filename, rel_path, root_path, tinc_client)
        self.type = DiskBufferType['NETCDF']
        self.enable_round_robin()
        self._attrs = {}

    def write_from_array(self, array, filename = None, attributes = {}):
        if not filename:
            filename = self._make_next_filename()
        # TODO more flexible data types
        datatype = np.float32
        outfile = None
        try:
            outfile = netCDF4.Dataset(self.get_full_path() + filename, mode='w', format='NETCDF4')
            outfile.createDimension('data_dim', size=len(array))
            var = outfile.createVariable('data', datatype,('data_dim'), zlib=True)
            for name, value in attributes.items():
                # TODO validate values for attributes
                setattr(var, name, value)
            var[:] = array
        except:
            print("ERROR writing netcdf file")
            traceback.print_exc()
        
        if outfile:
            outfile.close()
        # Hack to ensure file has been released for others to read.
        try:
            f = open(self.get_full_path() + filename)
            f.close()
        except:
            print("ERROR attempting to open newly created buffer file " + self.get_full_path() + filename)

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
            self._lock = FileLock(self.path.get_full_path() + outname + ".lock", timeout=1)
            if self._lock.is_locked:
                print("Locked " + outname)
            self._lock.acquire()
        try:
            #if outname.find(self.path.get_full_path()) == 0:
            #    fname = outname
            #else:
            #    fname = self.path.get_full_path() + outname
            if type(data) == list:
                self.write_from_array(data, outname, self._attrs)
            elif type(data) == np.ndarray:
                self.write_from_array(data, outname, self._attrs)
            else:
                raise ValueError(f"Unsupported format for data in NETCDFDiskBuffer: {type(data)}")
            
            self._data = data
            self._filename = outname
            if self.tinc_client:
                self.tinc_client._send_disk_buffer_current_filename(self, outname)
        except:
            print("ERROR parsing data when writing disk buffer")
            traceback.print_exc()
    
        if self._file_lock:
            self._lock.release()


    def _parse_file(self, file_path):
        # TODO being called twice on startup. investigate
        
        # print(self.get_full_path())
        # print(filename)
        f = netCDF4.Dataset(file_path, mode='r')
        return np.array(f.variables["data"][:])
    