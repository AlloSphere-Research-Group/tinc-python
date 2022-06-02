# -*- coding: utf-8 -*-
"""
Created on Thu Oct 15 14:32:03 2020

@author: Andres
"""

import json
import os, shutil
import jsonschema
import threading

import traceback

from typing import NamedTuple, List

from .variant import VariantType
# Causes cyclic import issue...
#from .parameter import to_variant
from .distributed_path import DistributedPath

TINC_META_VERSION_MAJOR = 1
TINC_META_VERSION_MINOR = 0

# C++ cache structs - they are used as NamedTuple here
class UserInfo(NamedTuple):
    user_name: str = ''
    user_hash: str = ''
    ip: str = ''
    port: int = 0
    server: bool = False

class VariantValue(NamedTuple):
    nctype: VariantType = VariantType.VARIANT_NONE
    value: any = None

class SourceArgument(NamedTuple):
    id: str = ''
    value: VariantValue = VariantValue()

class FileDependency(NamedTuple):
    file: DistributedPath = DistributedPath()
    modified: str = ''
    size: int = 0
    hash: str = ''

def arguments_from_param_list(param_list):
    args = []
    for p in param_list:
        args.append(SourceArgument(p.tinc_id, to_variant()))

class SourceInfo(NamedTuple):
    type: str = ''
    tinc_id: str = ''
    command_line_arguments: str = ''
    working_path_rel: str = ''
    working_path_root: str = ''
    arguments: List[SourceArgument] = []
    dependencies: List[SourceArgument] = []
    file_dependencies: List[FileDependency] = []



class CacheEntry(NamedTuple):
    timestamp_start: str = ''
    timestamp_end: str = ''
    files: List[str] = []
    user_info: UserInfo = UserInfo()
    source_info: SourceInfo = SourceInfo()
    cache_hits: int = 0
    stale: bool = False

# TODO implement a file based mutex (perhaps using file lock) to protect usage by multiple users
class CacheManager(object):
    def __init__(self, directory = "python_cache", metadata_file = "tinc_cache.json"):
        if not os.path.exists(directory):
            os.makedirs(directory)
        self._cache_root = ''
        self._cache_dir = directory
        self._metadata_file = metadata_file
        if len(self._cache_root) > 0 and not self._cache_root[-1] == "/":
            self._cache_root += '/'
        if len(self._cache_dir) > 0 and not self._cache_dir[-1] == "/":
            self._cache_dir += '/'
        self._validator = None
        self._entries = []
        self.debug = False
        self.mutex = threading.Lock()
        try:
            schema_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    'tinc_cache_schema.json')
            with open(schema_path) as f:
                schema = json.load(f)
                self._validator = jsonschema.Draft7Validator(schema)
                print("Validating json with " + schema_path)
        except:
            print("ERROR loading cache schema. Not validating schema.")
        if os.path.exists(self.cache_directory() + self._metadata_file):
            self.update_from_disk()
        else:
            self.write_to_disk() # Generate empty cache file.

    def append_entry(self, entry):
        self._lock()
        self._entries.append(entry)
        self._unlock()
        
    def entries(self, count = 0):
        self._lock()
        if count == 0 or count >= len(self._entries):
            e = self._entries
        else:
            e = self._entries[len(self._entries) - count:]
        self._unlock()
        return e

    def find_cache(self, source_info, verify_hash = True):
        self._lock()
        for entry in self._entries:
            if entry.source_info.command_line_arguments == source_info.command_line_arguments \
                and entry.source_info.tinc_id == source_info.tinc_id \
                and entry.source_info.type == source_info.type:
                    entry_args = entry.source_info.arguments[:]
                    entry_deps = entry.source_info.dependencies[:]
                    if len(source_info.arguments) == len(entry_args) \
                        and len(source_info.dependencies) == len(entry_deps):
                            match_count = 0
                            for src_arg in source_info.arguments:
                                for arg in entry_args:
                                    if src_arg.id == arg.id:
                                        if type(arg.value) == type(src_arg.value) \
                                            and arg.value == src_arg.value:
                                                entry_args.remove(arg)
                                                match_count += 1
                                                break
                                        
                            for src_dep in source_info.dependencies:
                                for dep in entry_deps:
                                    if src_dep.id == dep.id:
                                        if type(dep.value) == type(src_dep.value) \
                                            and dep.value == src_dep.value:
                                                entry_deps.remove(dep)
                                                match_count += 1
                                                break
                            if match_count == (len(source_info.arguments) + len(source_info.dependencies)) \
                                and len(entry_args) == 0 and len(entry_deps) == 0:
                                    self._unlock()
                                    return [f.file.filename for f in entry.files]
                    else:
                        print(f"Warning, cache entry found, but argument size mismatch: {source_info.arguments}  --  {entry_args}")
        
        self._unlock()
        return []

    def clear_cache(self):
        try:
            self.update_from_disk()
        except:
            traceback.print_exc()
            print("Failed to load cache, cached files will not be removed automatically")
        self._lock()
        for entry in self._entries:
            for f in entry.files:
                full_name = self.cache_directory() + f.file.filename
                try:
                    os.remove(full_name)
                except:
                    print("ERROR removing cache entry: " + full_name)
        
        self._entries = []
        self._unlock()
        self.write_to_disk()

    def update_from_disk(self):
        self._lock()
        try:
            if os.path.exists(self.cache_directory() + self._metadata_file):
                with open(self.cache_directory() + self._metadata_file) as f:
                    try:
                        j = json.load(f)
                        if j["tincMetaVersionMajor"] != TINC_META_VERSION_MAJOR or \
                            j["tincMetaVersionMinor"] != TINC_META_VERSION_MINOR:
                                print("Invalid cache format")
                                self._unlock()
                                return
                    except:
                        if self.debug:
                            traceback.print_exc()
                        print("Metadata file is not a TINC cache file. Ignoring.")
                        self._unlock()
                        return
                    
                    if self._validator:
                        try:
                            self._validator.validate(j)
                        except:
                            print("Cache metadata not valid according to schema. Ignoring.")
                            self._unlock()
                            return
                            
                    self._entries = []
                    for entry in j["entries"]:
                        filenames = []
                        for fdep in entry["files"]:
                            filenames.append(FileDependency(file = DistributedPath(filename = fdep["file"]["filename"],
                                                                            relative_path = fdep["file"]["relativePath"],
                                                                            root_path = fdep["file"]["rootPath"],
                                                                            protocol_id = fdep["file"]["protocolId"]),
                                                    modified = fdep["modified"],
                                                    size = fdep["size"],
                                                    hash = fdep["hash"]
                                                    ))
                                    
                        args = []
                        for a in entry["sourceInfo"]["arguments"]:
                            args.append(SourceArgument(id = a["id"], 
                                                    value = VariantValue(nctype = VariantType(a["nctype"]),
                                                                            value = a["value"])))
                            
                        deps = []
                        for a in entry["sourceInfo"]["dependencies"]:
                            deps.append(SourceArgument(id = a["id"], 
                                                    value = VariantValue(nctype = VariantType(a["nctype"]),
                                                                            value = a["value"])))
                            
                        fdeps = []
                        for fdep in entry["sourceInfo"]["fileDependencies"]:
                            fdeps.append(FileDependency(file = DistributedPath(filename = fdep["file"]["filename"],
                                                                            relative_path = fdep["file"]["relativePath"],
                                                                            root_path = fdep["file"]["rootPath"],
                                                                            protocol_id = fdep["file"]["protocolId"]),
                                                    modified = fdep["modified"],
                                                    size = fdep["size"],
                                                    hash = fdep["hash"]
                                                    ))

                        user_info = UserInfo(user_name = entry["userInfo"]["userName"],
                                            user_hash = entry["userInfo"]["userHash"],
                                            ip = entry["userInfo"]["ip"],
                                            port = entry["userInfo"]["port"],
                                            server = entry["userInfo"]["server"])
                        
                        source_info = SourceInfo(type = entry["sourceInfo"]["type"],
                                                tinc_id = entry["sourceInfo"]["tincId"],
                                                command_line_arguments = entry["sourceInfo"]["commandLineArguments"],
                                                working_path_rel = entry["sourceInfo"]["workingPath"]["relativePath"],
                                                working_path_root = entry["sourceInfo"]["workingPath"]["rootPath"],
                                                arguments = args,
                                                dependencies = deps,
                                                file_dependencies = fdeps)
                        
                        new_entry = CacheEntry(timestamp_start = entry["timestamp"]["start"],
                                            timestamp_end = entry["timestamp"]["end"],
                                            files = filenames,
                                            user_info = user_info,
                                            source_info = source_info,
                                            cache_hits = entry["cacheHits"],
                                            stale = entry["stale"])
                        self._entries.append(new_entry)
        except:
            print("Writing entry failed")
            
        self._unlock()

    '''
    Get full cache path
    '''
    def cache_directory(self):
        return self._cache_root + self._cache_dir
                    
    def write_to_disk(self):
        self._lock()
        try:
            if os.path.exists(self.cache_directory() + self._metadata_file):
                bak_filename = self.cache_directory() + self._metadata_file + ".bak"
                if(os.path.exists(bak_filename)):
                    os.remove(bak_filename) # Is this remove needed?
 
                shutil.copy(self.cache_directory() + self._metadata_file,
                    bak_filename)


            j = {}
            j["tincMetaVersionMajor"] = TINC_META_VERSION_MAJOR
            j["tincMetaVersionMinor"] = TINC_META_VERSION_MINOR
            j["entries"] = []
            for entry in self._entries:
                j_entry = {"timestamp":{"start": entry.timestamp_start, "end" :entry.timestamp_end }}
                j_entry["files"] = []
                for fdep in entry.files:
                    f_entry = {"file": {"filename": fdep.file.filename, 
                                    "relativePath": fdep.file.relative_path,
                                    "rootPath": fdep.file.root_path,
                                    "protocolId": fdep.file.protocol_id},
                        "modified": fdep.modified,
                        "size" : fdep.size,
                        "hash" : fdep.hash}
                    j_entry["files"].append(f_entry)


                j_entry["cacheHits"] = entry.cache_hits
                j_entry["stale"] = entry.stale
                j_entry["userInfo"] = {
                    "userName": entry.user_info.user_name,
                    "userHash": entry.user_info.user_hash,
                    "ip": entry.user_info.ip,
                    "port": entry.user_info.port,
                    "server": entry.user_info.server
                    }
                    
                args = []
                for a in entry.source_info.arguments:
                    args.append({"id" : a.id, 
                        "nctype" : int(a.value.nctype), "value" : a.value.value})
                        
                deps = []
                for a in entry.source_info.dependencies:
                    deps.append({"id" : a.id, 
                        "nctype" : int(a.value.nctype), "value" : a.value.value})
                    
                fdeps = []
                for fdep in entry.source_info.file_dependencies:
                    dep = {"file": {"filename": fdep.file.filename, 
                                    "relativePath": fdep.file.relative_path,
                                    "rootPath": fdep.file.root_path,
                                    "protocolId": fdep.file.protocol_id},
                        "modified": fdep.modified,
                        "size" : fdep.size,
                        "hash" : fdep.hash}
                    fdeps.append(dep)

                j_entry["sourceInfo"] = {
                    "type": entry.source_info.type,
                    "tincId" : entry.source_info.tinc_id,
                    "commandLineArguments" : entry.source_info.command_line_arguments,
                    "workingPath" : {"relativePath":entry.source_info.working_path_rel,
                                    "rootPath":entry.source_info.working_path_root},
                    "arguments" : args,
                    "dependencies" : deps,
                    "fileDependencies" : fdeps
                    }
                # TODO compute CRC
                #hash = str(zlib.crc32())

                j["entries"].append(j_entry)
            
            with open(self.cache_directory() + self._metadata_file, 'w') as f:
                json.dump(j, f, indent=4)
        except:
            print("ERROR writing cache entry metadata")
            print(j)
            traceback.print_exc()
        self._unlock()

    def dump(self):
        #print json metadata
        pass

    def _lock(self):
        # FIXME Implement file locking as well to protect cache metadata from multiple user access
        self.mutex.acquire()

    def _unlock(self):
        self.mutex.release()


if __name__ == "__main__":
    c = CacheManager()
    #print(c._validator)