# -*- coding: utf-8 -*-
"""
Created on Mon Nov 23 11:13:52 2020

@author: Andres
"""

import sys
import os

from tinc import *

import unittest
import random

class ProcessorTest(unittest.TestCase):
    def test_processor_script_template_basic(self):
        proc = ProcessorScript("proc")
        proc.command = "python"
        proc.script_name = "processor_test_data.py"
        proc.set_argument_template("-p %%p1%% -a %%p2%%")

        p1 = Parameter("p1", "group")
        p1.value = random.randint(0, 100) + 0.14
        proc.register_parameter(p1)
        p2 = Parameter("p2", "group2")
        p2.value = p1.value * 2
        proc.register_parameter(p2)
        
        self.assertEqual(f'-p {p1.value} -a {p2.value}', proc._get_arguments())
        
    def test_processor_script_template(self):
        proc = ProcessorScript("proc")
        proc.command = "python"
        proc.script_name = "processor_test_data.py"
        proc.set_argument_template("-p %%p1%%")

        p1 = Parameter("p1", "group")
        p1.value = random.randint(0, 100) + 0.14
        
        proc.register_parameter(p1)
        
        self.assertEqual(f'-p {p1.value}', proc._get_arguments())
        #TODO ML test all parameter representation types
        
        
    def test_processor_script_capture_output(self):
        proc = ProcessorScript("proc")
        proc.command = "python"
        proc.script_name = "processor_test_data.py"
        proc.output_files = ['out.txt']

        proc.set_argument_template("-p %%p1%%")

        p1 = Parameter("p1", "group")
        p1.value = random.randint(0, 100) + 0.14
        
        proc.register_parameter(p1)
        proc.capture_output()
        
        proc.process()
        with open('out.txt') as f:
            out = f.read()
            
        self.assertEqual(p1.value, float(out))
        
    def test_processor_script_output_db(self):

        proc = ProcessorScript("proc")
        proc.command = "python"
        proc.script_name = "processor_test_data.py"

        db = DiskBufferJson("json_buffer", "out.json", "proc_output/")
        proc.output_files = [db]

        proc.set_argument_template("-p %%p1%% -o %%:OUTFILE:0%%")

        p1 = Parameter("p1", "group")
        p1.value = random.randint(0, 100) + 0.14
        
        proc.register_parameter(p1)
        
        proc.process()
        with open(db.get_full_path() +db.get_current_filename()) as f:
            out = json.load(f)
            
        self.assertEqual(out, [p1.value, 450])
        
    def test_processor_script_capture_output_db(self):
        proc = ProcessorScript("proc")
        proc.command = "python"
        proc.script_name = "processor_test_data.py"

        db = DiskBufferJson("json_buffer", "out.json", "proc_output/")
        proc.output_files = [db]

        proc.set_argument_template("-p %%p1%%")

        p1 = Parameter("p1", "group")
        p1.value = random.randint(0, 100) + 0.14
        
        proc.register_parameter(p1)
        proc.capture_output()
        
        proc.process()
        with open(db.get_full_path() + db.get_current_filename()) as f:
            out = f.read()
            
        self.assertEqual(p1.value, float(out))

if __name__ == '__main__': 
    unittest.main()
    print('done')