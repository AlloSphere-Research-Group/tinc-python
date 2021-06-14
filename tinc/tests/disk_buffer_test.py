import unittest

import sys,time
import io
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
    
if __name__ == '__main__': 
    unittest.main()
 
