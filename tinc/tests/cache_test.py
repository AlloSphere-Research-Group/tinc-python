# -*- coding: utf-8 -*-
"""
Created on Mon Nov 23 11:13:52 2020

@author: Andres
"""

# Not needed if tinc-python is installed
import sys
from tinc import *

import unittest

class CacheTest(unittest.TestCase):
    
    def test_metadata(self):
        cache = CacheManager()
        
        src_info = SourceInfo(
            type = "PythonScript",
            tinc_id= 'id',
            command_line_arguments = 'many args',
            working_path_rel = 'cwd_path/',
            working_path_root = '/root',
            arguments = [SourceArgument(id = 'arg_id', value = VariantValue(nctype = VariantType.VARIANT_FLOAT, 
                                                                            value = 1.3)),
                         SourceArgument(id = 'arg_id2', value = VariantValue(nctype = VariantType.VARIANT_DOUBLE, 
                                                                            value = 1.6))],
            dependencies = [SourceArgument(id = 'dep_id', 
                                           value = VariantValue(nctype = VariantType.VARIANT_DOUBLE, 
                                                                value = 1.6)),
                            SourceArgument(id = 'dep_id2', 
                                           value = VariantValue(nctype = VariantType.VARIANT_FLOAT, 
                                                                value = 1.8))],
            file_dependencies =  [FileDependency(DistributedPath(filename ="dep1")), 
                                  FileDependency(DistributedPath(filename ="dep1"))])
        
        
        entry = CacheEntry(timestamp_start = 'a',
                           timestamp_end =  'b', 
                           files = [FileDependency(DistributedPath(filename ="out1.txt"))],
                           user_info = UserInfo(user_name = 'name',
                                                user_hash = 'hash',
                                                ip = 'ip',
                                                port = 9001,
                                                server = False),
                           source_info  = src_info,
                           cache_hits = 7,
                           stale = True)
        
        cache.clear_cache()
        cache.append_entry(entry)
        cache.write_to_disk()
        
        cache.update_from_disk()
        
        self.assertGreater(len(cache.entries()), 0)
        retrieved = cache.entries()[0]
        
        self.assertEqual(retrieved, entry)
        
    
    def test_find_cache(self):
        cache = CacheManager()
        
        
        src_info = SourceInfo(
            type = "PythonScript",
            tinc_id= 'id',
            command_line_arguments = 'many args',
            working_path_rel = 'cwd_path/',
            working_path_root = '/root',
            arguments = [SourceArgument(id = 'arg_id', value = VariantValue(nctype = VariantType.VARIANT_FLOAT, 
                                                                            value = 1.3)),
                         SourceArgument(id = 'arg_id2', value = VariantValue(nctype = VariantType.VARIANT_DOUBLE, 
                                                                            value = 1.6))],
            dependencies = [SourceArgument(id = 'dep_id', 
                                           value = VariantValue(nctype = VariantType.VARIANT_DOUBLE, 
                                                                value = 1.6)),
                            SourceArgument(id = 'dep_id2', 
                                           value = VariantValue(nctype = VariantType.VARIANT_FLOAT, 
                                                                value = 1.8))],
            file_dependencies =  [FileDependency(DistributedPath(filename ="dep1")), 
                                  FileDependency(DistributedPath(filename ="dep1"))])
        
        
        entry = CacheEntry(timestamp_start = 'a',
                           timestamp_end =  'b', 
                           files = [FileDependency(DistributedPath(filename ="out1.txt"))],
                           user_info = UserInfo(user_name = 'name',
                                                user_hash = 'hash',
                                                ip = 'ip',
                                                port = 9001,
                                                server = False),
                           source_info  = src_info,
                           cache_hits = 7,
                           stale = True)
        
        cache.clear_cache()
        cache.append_entry(entry)
        cache.write_to_disk()
        
        import time
        text = "Cache test " + time.asctime()
        with open("out1.txt", "w") as f:
            f.write(text)
        
        cache.update_from_disk()
        
        files = cache.find_cache(src_info)
        print(files)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], "out1.txt")
        
    def test_cache_param_dependencies(self):
        # Cache with parameter space
        p1 = Parameter("param1")
        p1.set_values([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        
        p2 = ParameterInt("param2")
        p2.set_values([i for i in range(5)])
        
        p3 = Parameter("param3")
        p3.set_values([i * 0.2 for i in range(2)])
        
        ps = ParameterSpace("cache_test")
        
        ps.register_parameters([p1, p2, p3])
        
        ps.enable_cache("python_ps_cache")
        ps.clear_cache()

        def func(param1, param2):
            return param1 * param2, param1* p3.value

        p2.value = 1
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.2
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.3
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.4
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.5
        ps.run_process(func, dependencies=[p3])
        p2.value = 4
        ps.run_process(func, dependencies=[p3])
        
        p2.value = 1
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.2
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.3
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.4
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.5
        ps.run_process(func, dependencies=[p3])
        p2.value = 4
        ps.run_process(func, dependencies=[p3])
        
        p3.value = 0.4
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.2
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.3
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.4
        ps.run_process(func, dependencies=[p3])
        p1.value = 0.5
        ps.run_process(func, dependencies=[p3])
        p2.value = 4
        ps.run_process(func, dependencies=[p3])


    def test_parameter_space_proc(self):
        # Cache with parameter space
        p1 = Parameter("param1")
        p1.set_values([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        
        p2 = ParameterInt("param2")
        p2.set_values([i for i in range(5)])
        
        p3 = Parameter("param3")
        p3.set_values([i * 0.2 for i in range(2)])
        
        ps = ParameterSpace("cache_test")
        
        ps.register_parameters([p1, p2, p3])
        
        ps.enable_cache("python_ps_cache")
        ps.clear_cache()

        def func(param1, param2, param3):
            return param1 * param2, param1* param3

        p2.value = 1
        ps.run_process(func)
        ps._cache_manager
        p1.value = 0.2
        ps.run_process(func)
        p1.value = 0.3
        ps.run_process(func)
        p1.value = 0.4
        ps.run_process(func)
        p1.value = 0.5
        ps.run_process(func)
        p2.value = 4
        ps.run_process(func)
        
        p2.value = 1
        ps.run_process(func)
        p1.value = 0.2
        ps.run_process(func)
        p1.value = 0.3
        ps.run_process(func)
        p1.value = 0.4
        ps.run_process(func)
        p1.value = 0.5
        ps.run_process(func)
        p2.value = 4
        ps.run_process(func)


if __name__ == '__main__': 
    unittest.main()
