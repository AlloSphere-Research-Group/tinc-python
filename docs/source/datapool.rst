.. _TINCDataPool:

5. Data Pools
===================

.. toctree::
   :maxdepth: 4

A TINC data pool provides an interface for data extraction from files scattered
across the filesystem. TO create a TINC data pool you need data that
is indentically shaped (i.e. the data changes but the structure doesn't) and
whose directory names can be expressed algorithmically from a parameter space.

This tutorial will explain how to create a DataPool from an existing dataset. It
requires the tinc-python unit test data folders.

The "dataset" found in the ``tinc/tests/data`` folder consists of 3 folders:
``folder1``, ``folder2`` and ``folder3``. Each of these contains a file called
``results.json`` that contains data like::

    {
      'field1': [0, 1, 2, 3, 4, 5, 6, 7], 
      'field2': [1, 2, 3, 4, 5, 6, 7, 8],
      'field3': [4, 5, 6, 7, 8, 9, 0, 1]
    }

Although the 3 files contain the same fields with the same number of items, the actual
data within each file is different. This arrangement could be the produce of a parameter sweep 
on a HPC cluster.

The first step is to model the parameter space for this dataset. A parameter will
represent the dimension that maps to the file system::

   param1 = Parameter("param1")
   param1.values = [0.1, 0.2, 0.3] # Arbitrarily defined here, but in a real dataset would represent the parameter values that map to folders
   param1.ids = ["folder1", "folder2", "folder3"]

Notice that we use ``ids`` to set the folder names and ``values`` to set the parameter
values that map to the folders. These parameters could be the specific values that
produced each folder.

A second parameter can map to the internal "columns" in the fields within'
the ``results.json`` file::
    
    inner_param = Parameter("inner_param")
    inner_param.values = linspace(0.1, 0.8, 8)

We then create the parameter space for these two parameters::

    ps = ParameterSpace()
    ps.register_parameters([param1, inner_param])

Now we specify how the filesystem is mapped according to the parameter values::

    tinc_path = "../" # Points to the root path to the tinc sources.
    ps.set_root_path(tinc_path)
    ps.set_current_path_template("tinc/tests/data/%%param1:ID%%")

We can test that paths are being mapped correctly::

    def print_current_path(discard_value = 0):
        print(ps.get_current_relative_path())
    param1.register_callback(print_current_path)
    param1.interactive_widget()

.. image:: img/datapool_param.png
  :width: 300
  :alt: Alternative text

When the parameter space has been defined, the data pool for JSON data
can be created::
    
    dp = DataPoolJson("data", ps)

Then the file needs to be registered with the data pool, indicating
the dimension it contains::

    dp.register_data_file("results.json", "inner_param")

We can then query the available fields within the data pool, which will list
the keys within the json file::

    dp.list_fields()

::

    ['field1', 'field2', 'field3']

The reason why you want to create data pools is to have quick access to the data. This
can be done by "slicing" the data pool. You can request a slice of a specific
field along a specific parameter space dimension. The output of slicing contains
the data values within the field, one for each of the values within the dimension.
The other dimensions are used as constant on the current values::

     dp.get_slice("field1","inner_param")

produces::

    masked_array(data=[0., 1., 2., 3., 4., 5., 6., 7.],
                mask=False,
        fill_value=1e+20,
                dtype=float32)

If you set a different value for ``param1``::

    param1.value = 0.2
    dp.get_slice("field1","inner_param")

You get::

    masked_array(data=[1., 2., 3., 4., 5., 6., 7., 8.],
             mask=False,
       fill_value=1e+20,
            dtype=float32)

In the first case, the slice returns the value under key ``field1``
in folder ``folder1`` and in the second within ``folder2``.

Slicing becomes more useful when the slice cuts across multiple files. So
slicing along dimension ``param1`` will return a list of 3 values taken from
the three files within the three directories::

    inner_param.value = 0.3
    dp.get_slice("field1","param1")

Produces::

    masked_array(data=[2., 3., 8.],
                mask=False,
        fill_value=1e+20,
                dtype=float32)

While::

    inner_param.value = 0.1
    dp.get_slice("field1","param1")

Produces::

    masked_array(data=[0., 1., 5.],
                mask=False,
        fill_value=1e+20,
                dtype=float32)

Data pool with multiple filesystem parameters
---------------------------------------------

There are cases where the folder name depends on two or more
parameters, for example the folder ``data2`` in the TINC tests.
In this example the folders are: ``folderA_1``, ``folderA_2``, 
``folderB_1``, ``folderB_2``. These represents one parameter that has
values A and B and another parameter that has values 1 and 2.

To do this, we need to list all the values for the parameter with
its corresponding folder like so::

    param1 = Parameter("param1")
    param1.values = [0.1, 0.1, 0.2, 0.2]
    param1.ids = ["folderA_1", "folderA_2", "folderB_1", "folderB_2"]

    param2 = Parameter("param2")
    param2.values = [1,1,2,2]
    param2.ids = ["folderA_1", "folderB_1", "folderA_2", "folderB_2"]

    inner_param = Parameter("inner_param")
    inner_param.values = linspace(0.1, 0.8, 8)

As you can see, values there are two folders that map to the same value
on all the parameters. This represents all the folders where that
parameter has that value.

We can then create the parameter space as before::

    ps = ParameterSpace()
    ps.register_parameters([param1, param2, inner_param])
    ps.set_root_path(tinc_path)

To map the filesystem when setting the current path template, we
can provide two parameters separated by commas. What this will do 
is find the common id at the current parameter values::

    ps.set_current_path_template("tinc/tests/data/%%param1,param2%%")

You can test the mapping::

    param1.value = 0.2
    param2.value = 1
    ps.get_current_relative_path()

::

    'tinc/tests/data/folderB_1'

Slicing will now work as it does for single filesystem parameters,
as the parameters will map correctly to a unique folder.