.. tinc documentation master file, created by
   sphinx-quickstart on Wed May 25 14:28:35 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to TINC's documentation!
================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

The Toolkit for Interactive Computation (TINC) provides a set of C++ and python classes to assist in the interactive exploration of large datasets by managing parameter spaces, interactive computation and caching of data.

TINC can be used standalone in python to assist exploration of complex datasets.

It can also expose a C++ application's computation to the network. This simplifies the development of distributed applications as well as creating applications that can be controlled trhrough python without having the application itself depend on python. A great use case is by interacting with the C++ application through a jupyter notebook.

Installing TINC
===============

TINC requires python >= 3.6.

The simplest way to install TINC is through pip::

    pip install tinc

You can verify your TINC installation::

    from tinc import *
    TincVersion()

Tutorials and examples
======================

There are two primary uses of TINC in Python. The first is controlling and prototyping interactive 
computation and display through the modeling of the parameter space, and the second is the pooling 
of files spread across the filesystem into a multidimensional dataset. These tutorials introduce
the different tools in TINC for these uses.

* :ref:`TINCPythonTutorial`
* :ref:`TINCInteractiveDisplay`
* :ref:`TINCCaching`
* :ref:`TINCNotebookWidgets`
* :ref:`TINCDataPool`

You can try these notebooks in google colab:

 * [https://colab.research.google.com/drive/1XO-babUACUdeyp8YikofT6ySJAdjG1e8?usp=sharing]()
 * [https://colab.research.google.com/drive/1jjJhJHVvunEOXf3bUHmLNVMm_cKqls26?usp=sharing]()
 

Indices and tables
==================

* :ref:`TINCClasses`
* :ref:`genindex`
* :ref:`search`
