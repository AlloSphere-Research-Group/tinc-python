# -*- coding: utf-8 -*-
"""
Created on Tue Nov 24 10:12:47 2020

@author: Andres
"""

import time
import sys
sys.path.append('../../tinc-python')
from tinc_client import *
tclient = TincClient()

time.sleep(0.5)

tclient.request_parameter_spaces()

time.sleep(2)

#print(tclient.parameter_spaces)
ps=tclient.parameter_spaces[0]

#print(ps)
#ps.print()
#tclient.print()

for i in range(50):
    print(i)
    ps.get_current_path()
    ps.get_root_path()
    ps.get_current_path()
    print(ps.get_root_path())
    print(ps.get_current_path())

time.sleep(5)

tclient.stop()

exit()

time.sleep(0.5)
shellsites = tclient.get_parameter("ShellSiteTypes")
print(shellsites.get_current_elements())

print(tclient.command_parameter_choice_elements(shellsites))


imageBuffer = tclient.get_disk_buffer('graph')
imageBuffer.allow_cache(5)
print(imageBuffer._path)
print(imageBuffer.get_filename_for_writing())



while True:
    print(tclient.command_parameter_choice_elements(shellsites))
    root_path=ps.get_root_path()
    trajectories_path=root_path+ps.get_current_path()+"\\trajectory.nc"
    print(trajectories_path)
    time.sleep(1)