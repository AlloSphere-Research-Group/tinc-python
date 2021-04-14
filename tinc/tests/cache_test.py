# -*- coding: utf-8 -*-
"""
Created on Mon Nov 23 11:13:52 2020

@author: Andres
"""

# Not needed if tinc-python is installed
import sys
sys.path.append('../../tinc-python')

from parameter import Parameter, ParameterInt

p1 = Parameter("param1")
p1.set_values([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])

p2 = ParameterInt("param2")
p2.set_values([i for i in range(5)])

p3 = Parameter("param3")
p3.set_values([i * 0.2 for i in range(2)])

from parameter_space import ParameterSpace

ps = ParameterSpace("cache_test")


ps.register_parameters([p1, p2, p3])

ps.enable_caching()

ps.clear_cache()
