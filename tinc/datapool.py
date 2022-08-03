# -*- coding: utf-8 -*-
"""
Created on Tue Sep  1 15:47:46 2020

@author: Andres
"""

from .tinc_object import TincObject
from .parameter_space import ParameterSpace
from .processor import ProcessorScript

import netCDF4
import numpy as np
import traceback
import os

class DataPool(TincObject):
    '''The DataPool class can unify through a single interface homogeneous data spread across the filesystem.
    
    The DataPool class gathers data files across directories that span a parameter space.
    The parameter space and its current values determine where the files in the
    data pool are found. This class is useful to manage data files that are the
    result of parameter sweeps, generating the same type of file in different
    directories, where each directory represents a sample of the parameter space.

    This base class provides the basic functionality and interface, but in practice you will want
    to use one of the derived classes that matches your data, like :class:`tinc.datapool.DataPoolJson`.
    
    :param tinc_id: the name that identifies the data pool
    :param parameter_space: The :class:`tinc.parameter_space.ParameterSpace` for the data
    :param slice_cache_dir: The folder where slices from the data pool are stored
    :param tinc_client: The :class:`tinc.tinc_client.TincClient` the parameter belongs to. This should be left as None when calling directly.
    '''
    def __init__(self, tinc_id = "_", parameter_space = None, slice_cache_dir = './', tinc_client = None):
        super().__init__(tinc_id)
        self._parameter_space = parameter_space
        if type(self._parameter_space) != ParameterSpace:
            raise ValueError("Must pass a valid ParameterSpace object to constructor")
        self.slice_cache_dir = slice_cache_dir
        self.tinc_client = tinc_client
        self._data_file_names = {}
        self.debug = False

    def __str__(self):
        out = f" ** DataPool: {self.id}\n"
        out += f"      ParameterSpace id: {self._parameter_space.id}\n"
        return out

    def register_data_file(self, filename, dimension_in_file):
        '''Register with the DataPool the filename and the dimension from the parameter space
        that is contained within the file.

        These file should be located relative to the current directory for the parameter space.
        It should be present in all data paths for the parameter space.
        
        :param filename: The relative file name
        :param dimension_in_file: string with the dimension file name
        '''
        if filename in self._data_file_names:
            print(f"DataPool: Overiwriting dimension in file {filename}")
        self._data_file_names[filename] = dimension_in_file
    
    def get_registered_data_files(self):
        return self._data_file_names
    
    def clear_registered_data_files(self):
        self._data_file_names = {}

    def get_parameter_space(self):
        '''Get the :class:`tinc.parameter_space.ParameterSpace` that controls this data pool'''
        return self._parameter_space
    
    def _create_data_slice_internal(self, field, internal_dim, space):
        # Internal dimension
        
        if self._parameter_space.is_filesystem_dimension(\
                self.get_parameter_space().get_dimension(internal_dim)):
            raise ValueError(f'Dimension "{internal_dim}" is not an internal dimension')
        else:
            path = self._parameter_space.get_root_path()
            if len(path) > 0 and path[-1] != '/':
                path += "/" 
            path += self._parameter_space.get_current_relative_path() + "/"
            for data_filename, dim_in_file  in self._data_file_names.items():
                # TODO support more than one file
                slice_values = self._get_field_from_file(field, path + data_filename)
                break           
    
    def create_data_slice(self, field, slice_dimensions, override_value = None):
        '''Write data slice to file.

        The slice will be created as a NetCDF4 file with a single variable called
        "data" that spans a dimension "values". The result will be a multi-
        dimensional slice containing the values of the "field" across all values
        for slice_dimensions (that must be registered in the parameter space).
        
        :param field: Name of the field to extract
        :param slice_dimensions: The name of a dimension or a list of dimension names
        :param override_value: (optional) Override current values in the parameter space. Should contain a map of names to values
        :returns: Filename to the new data slice
        '''

        if type(slice_dimensions) == str:
            slice_dimensions = [slice_dimensions]
        elif type(slice_dimensions) != list:
            raise ValueError("slice_dimensions must be string or list.")
        filesystem_dims = []
        fixed_dims = []
        slice_values = None
        for dim in self._parameter_space.get_dimensions():
            if self._parameter_space.is_filesystem_dimension(dim.id):
                filesystem_dims.append(dim)
            if not dim.id in slice_dimensions:
                fixed_dims.append(dim)
        if len(filesystem_dims) > 1:
            raise ValueError("Only one filesystem dimension supported")
        
        filename = "_slice_" + field + "_"
        # FIXME implement slicing aloneg more than one direction
        field_size = 1 # FIXME get actual field size
        dim_count = field_size
        # This function is not thread safe. There can be race conditions if the parameter
        # is changed while running this. Should we protect?
        for dim_name in slice_dimensions:
            dim = self._parameter_space.get_dimension(dim_name)
            if not dim is None and dim.get_space_stride() > 0:
                dim_count = dim_count * (len(dim.values)/dim.get_space_stride() )
            else:
                raise ValueError(f"Unknown dimension '{dim_name}'")
        
        if self.debug:
            print(f'Field: {field} Filesystem dims: {[d.id for d in filesystem_dims]} Fixed dims: {[d.id for d in fixed_dims]}')
        # TODO check if file exists and is the correct slice to use cache instead.
        # TODO for this we need to add metadata to the file indicating where the
        # slice came from. This is part of the bigger TINC metadata idea
        slice_values = []
        index_map = {}
        if len(slice_dimensions) > 2:
            raise ValueError("multidimensional slicing not supported yet.")
        elif len(slice_dimensions) == 2:
            # Fake it for now. There are much more efficient ways to do it, but this is a quick way to get it working
            p1 = self._parameter_space.get_dimension(slice_dimensions[0])
            for v in p1.values:
                part_slice_file = self.get_slice(field, slice_dimensions, override_value)


            return   
        
        for dim_name in slice_dimensions:
            dim = self._parameter_space.get_dimension(dim_name)
            this_dim_count = (len(dim.values)/dim.get_space_stride() )
            if self._parameter_space.is_filesystem_dimension(dim.id):
                for i in range(int(this_dim_count)):
                    index_map = {dim.id: i * dim.get_space_stride()}
                    if dim.get_space_stride() > 1:
                        ids = {j:dim.ids[i * dim.get_space_stride() + j] for j in range(dim.get_space_stride())}
                        for fs_dim in filesystem_dims:
                            if fs_dim.id != dim_name:
                                new_ids = fs_dim.get_current_ids()
                                to_remove = []
                                for id in ids.values():
                                    if not id in new_ids:
                                        to_remove.append(list(ids.keys())[list(ids.values()).index(id)])
                                for r in to_remove:
                                    ids.pop(r)
                        if len(ids) == 1:
                            index_map[dim.id] += list(ids.keys())[0]
                    path = self._parameter_space.get_root_path()
                    if len(path) > 0:
                        path += '/'
                    path += self._parameter_space.resolve_template( \
                                self._parameter_space._path_template, index_map) + '/'
                    #TODO support multiple files. This only works for one file. 
                    for data_filename, dim_in_file  in self._data_file_names.items():
                        temp_slice_values = self._get_field_from_file(field, path + data_filename)
                        index = self._parameter_space.get_dimension(dim_in_file).get_current_index()
                        if temp_slice_values is not None:
                            slice_values.append(temp_slice_values[index])
                        else:
                            slice_values.append(None)
            else:
                path = self._parameter_space.get_root_path()
                if len(path) > 0:
                    path += "/" 
                path += self._parameter_space.get_current_relative_path() + "/"
                for data_filename, dim_in_file  in self._data_file_names.items():
                    # TODO support more than one file
                    slice_values = self._get_field_from_file(field, path + data_filename)
                    break

            filename += dim_name + "_"

        for dim in self._parameter_space.get_dimensions():
            filename += dim.id + "_" + str(dim.value) + "_"

        # TODO Windows paths cant end with dot or space
        filename = ProcessorScript.sanitize_name(filename)
        filename += ".nc"
        # Now write slice
        if os.path.isabs(self.slice_cache_dir) or self.tinc_client is None:
            slice_path = self.slice_cache_dir
        else:
            slice_path = self.tinc_client._working_path + self.slice_cache_dir

        if not os.path.exists(slice_path):
            os.makedirs(slice_path)

        outfile = None
        try:
            outfile = netCDF4.Dataset(slice_path + filename, mode='w', format='NETCDF4')
            datatype = np.float32
            outfile.createDimension('data_dim', size=len(slice_values))
            var = outfile.createVariable('data', datatype, ('data_dim'), zlib=True)

            var[:] = slice_values
        except:
            print("ERROR writing netcdf file")
            traceback.print_exc()
        
        if outfile:
            outfile.close()
        if self.debug:
            print(f'DataPool wrote slice: {filename} in {slice_path}')
        return filename

    # TODO this function is called readDataSlice() in C++
    def get_slice(self, field, slice_dimensions, override_value = None):
        '''Get data slice from the data pool.

        Called readDataSlice() in the C++ API.

        :param field: Name of the field to extract
        :param slice_dimensions: The name of a dimension or a list of dimension names
        :param override_value: (optional) Override current values in the parameter space. Should contain a map of names to values
        '''
        if not self.tinc_client:
            slice_file = self.create_data_slice(field, slice_dimensions, override_value)
        else:
            slice_file = self.tinc_client._command_datapool_slice_file(self.id, field, slice_dimensions, self.server_timeout)
            if override_value is not None:
                print("Override value ignored for remote slicing")
        if os.path.isabs(self.slice_cache_dir) or self.tinc_client is None:
            slice_path = self.slice_cache_dir
        else:
            slice_path = self.tinc_client._working_path + self.slice_cache_dir

        if not os.path.exists(slice_path):
            os.makedirs(slice_path)
        nc = netCDF4.Dataset(slice_path + slice_file)
        
        if self.debug:
            print(f'DataPool reading slice: {slice_file} in {slice_path}')
        # print(nc.variables.keys())
        slice_data = nc.variables['data'][:]
        nc.close()

        return slice_data

    
    def get_slice_file(self, field, slice_dimensions):
        if not self.tinc_client:
            return self.create_data_slice(field, slice_dimensions)
        return self.tinc_client._command_datapool_slice_file(self.id, field, slice_dimensions, self.server_timeout)
        
    def get_current_files(self):
        if not self.tinc_client:
            files = []
            path = self._parameter_space.get_root_path()
            if len(path) > 0 and path[-1] != '/':
                path += "/" 
            path += self._parameter_space.get_current_relative_path() + '/'
            
            for fname in self._data_file_names.keys():
                fullPath = path + fname
                if not os.path.isabs(fullPath):
                    fullPath = os.path.abspath(fullPath)

                files.append(fullPath)
        
            return files
        else:
            return self.tinc_client._command_datapool_get_files(self.id, self.server_timeout)
    
    def list_fields(self, verify_consistency = False):
        '''List fields available in the data files for this data pool'''
        # TODO verify consistency
        current_file = self.get_current_files()[0]

        return self._list_fields_in_file(current_file)

    def _list_fields_in_file(self, full_path):
        raise RuntimeError("To extract data locally use the DataPool data specific classes (e.g. DataPoolJson)")

    def _get_field_from_file(self, field, full_path):
        raise RuntimeError("To extract data locally use the DataPool data specific classes (e.g. DataPoolJson)")
    

class DataPoolJson(DataPool):
    '''DataPool to read JSON files
    '''
    def __init__(self, tinc_id = "_", parameter_space = None, slice_cache_dir = './', tinc_client = None):
        super().__init__(tinc_id, parameter_space, slice_cache_dir, tinc_client)
    
    def _list_fields_in_file(self, full_path):
        import json
        with open(full_path) as f:
            j = json.load(f)

        return list(j.keys())

    def _get_field_from_file(self, field, full_path):
        import json
        try:
            with open(full_path) as f:
                j = json.load(f)
        except:
            print(f'File not found: {full_path}')
            return None

        try:
            field_data = j[field]
        except ValueError as e:
            raise ValueError(f"Field '{field}' not found in file: {f}")
        if type(field_data) == list:
            return field_data
