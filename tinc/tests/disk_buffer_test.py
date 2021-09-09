import unittest

import json
import random
from tinc import *

# self.assertEqual(p.id, "name")
 

class DiskBufferTests(unittest.TestCase):

    def test_nc_diskbuffer(self):
        db = DiskBufferNetCDFData("nc", "out.nc", "./")
        array = [1,2,3,4,8.9,20]
        db.data = array
        self.assertEqual(array, db.data)

    def test_nc_diskbuffer_round_robin(self):

        db = DiskBufferNetCDFData("nc", "out.nc", "./")
        db.enable_round_robin(5)

        for i in range(20):
            array = [random.random() for i in range(100)]
            db.data = array
            db._parse_file(db.get_current_filename())
            for v1, v2 in zip(array, db.data):
                self.assertAlmostEqual(v1,v2, places= 5)

    def test_json_diskbuffer(self):
        
        db = DiskBufferJson("nc", "out.json", "./")
        # Integer list
        db.data = [2,3,5]

        with open('out.json') as f:
            read_data = json.load(f)
        self.assertEqual([2,3,5], read_data)

        # Float list
        db.data = [2.1,3.4,5.6]

        with open('out.json') as f:
            read_data = json.load(f)
        self.assertEqual([2.1,3.4,5.6], read_data)

        # String list
        db.data = ["2.1","3.4","5.6"]

        with open('out.json') as f:
            read_data = json.load(f)
        self.assertEqual(["2.1","3.4","5.6"], read_data)

        # Mixed list
        db.data = ["2.1",3.4,5]

        with open('out.json') as f:
            read_data = json.load(f)
        self.assertEqual(["2.1",3.4,5], read_data)

        # json object/python dict

        d = {"key1": 1, "key2": [1,2,3], "key3": {"inner1": "string", "inner2": 3.4, "inner3": [5.4, 3.4]}}
        db.data = d

        with open('out.json') as f:
            read_data = json.load(f)
        self.assertEqual(d, read_data)


if __name__ == '__main__': 
    unittest.main()
 
