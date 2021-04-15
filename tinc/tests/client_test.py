# -*- coding: utf-8 -*-
"""
Created on Tue Nov 24 10:12:47 2020

@author: Andres
"""

import time
import sys
from tinc import *

tclient = TincClient()
tclient.debug = True
time.sleep(0.5)

tclient.request_parameter_spaces()
tclient.synchronize()

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

#time.sleep(50)

from parameter import *
eci1_param=tclient.create_parameter(Parameter,\
                                    "tet_oct_eci","casm",-0.375,0.375,\
                                    [-0.375,-0.125,0.125,0.375],-0.375)

eci2_param=tclient.create_parameter(Parameter,\
                                "oct_tet_NN","casm",2.0,6.0,[2.0,6.0],6.0)
    
eci3_param=tclient.create_parameter(Parameter,\
                                    "oct_oct_NN","casm",0.0,1.0,\
                                    [0.0,1.0],0.0)
    
eci4_param=tclient.create_parameter(Parameter,\
                                    "tet_tet_NN","casm",0.0,0.5,[0.0,0.5])

time.sleep(0.5)

root_dir = "C:/Users/Andres/source/repos/vdv_data/visualization/"
def create_dir_string_from_eci_param(eci_value):
    datasetname=root_dir + "AMX2_spinel_diffusion_0.0_0.0"+\
    "_"+str(eci1_param.value)+\
    "_"+str(eci2_param.value)+\
    "_"+str(eci3_param.value)+\
    "_"+str(eci4_param.value)+\
    "/kinetic_mc"
    tclient.get_parameter("dataset").value=datasetname
    print("registered change " + datasetname)
    return

eci1_param.register_callback(create_dir_string_from_eci_param)

eci2_param.register_callback(create_dir_string_from_eci_param)

eci3_param.register_callback(create_dir_string_from_eci_param)

eci4_param.register_callback(create_dir_string_from_eci_param)


time.sleep(3)

shellsites = tclient.get_parameter("ShellSiteTypes")
print(shellsites.get_current_elements())

print(tclient.command_parameter_choice_elements(shellsites))

tclient.synchronize()

imageBuffer = tclient.get_disk_buffer('graph')
imageBuffer.enable_round_robin(5)
print(imageBuffer._path)
print(imageBuffer.get_filename_for_writing())

import random
import matplotlib.pyplot as plt
import threading
import shutil
image_names=["oct_doub_va_cleared_path",
            "oct_doub_va_double_cleared_path",
             "oct_doub_va_queued_path",
             "oct_no_va",
             "oct_sing_va",
             "oct_trip_va_forced_path",
             "oct_trip_va_free_range_path",
             "oct_trip_va_semiforced_path",
             "oct_trip_va_trapped_path",
             "tet_no_va",
             "tet_sing_va"]
def update_shellsite_pic(shellSite):
    #print("Shell bitstring " + str(shellSite))
    b = int(shellSite)
    current_image_name=""
    for iname in image_names:
        if b & 1 == 1:
            current_image_name=iname
            break
        b = b >> 1
    fname = imageBuffer.get_filename_for_writing()
    #print(fname)
    shutil.copyfile("C:/Users/askje/Documents/"+current_image_name+".png",fname)
    imageBuffer.done_writing_file(fname)
    print(current_image_name)

shellsites = tclient.get_parameter("ShellSiteTypes")
shellsites.register_callback(update_shellsite_pic)

param=tclient.parameter_spaces[0]
root_path=param.get_root_path()
trajectories_path=root_path+param.get_current_path()+"\\trajectory.nc"
print(trajectories_path)

ps = tclient.get_parameter_space("casm_space_0")
ps.enable_caching()

ps.get_parameter("time").value = 10

ps.get_current_path()

print("Bye")

# while True:
#     print(tclient.command_parameter_choice_elements(shellsites))
#     root_path=ps.get_root_path()
#     trajectories_path=root_path+ps.get_current_path()+"\\trajectory.nc"
#     print(trajectories_path)
#     time.sleep(1)
