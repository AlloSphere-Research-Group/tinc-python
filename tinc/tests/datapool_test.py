# -*- coding: utf-8 -*-
"""
Created on Fri Sep 11 16:30:13 2020

@author: Andres
"""

import sys
import time

sys.path.append('../')

from tinc import *

tclient = TincClient()

while not tclient.connected:
    time.sleep(0.01)

tclient.synchronize()
#tclient.request_data_pools()

try:
    while len(tclient.datapools) == 0 and len(tclient.parameters) == 0 and len(tclient.disk_buffers) == 0:
        time.sleep(0.5)
except:
    pass

dp = tclient.datapools[0]

dp_slice = dp.get_slice("value", "internalValuesDim")

print(dp_slice)
time.sleep(1)

tclient.stop()
