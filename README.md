# TINC python module and tools

This is the python module for TINC. It can be used standalone, or in conjunction with a C++ application written with TINC to provide a TINC server:

https://github.com/AlloSphere-Research-Group/tinc

tinc-python depends on numpy, matplotlib, netcdf4, filelock and jsonschema. If ipywidgets is available, tinc-python can provide interactive widgets for the jupyter notebook.

To tinc for python:
```
pip install tinc
```

To install ipywidgets for jupyter widget support:
```
pip install ipywidgets
```
# Documentation

The TINC python documentation is available at: https://tinc-python.readthedocs.io/en/latest/

A set pf tutorials for tinc-python can be found in the documentation.

Try out TINC:

https://colab.research.google.com/drive/1XO-babUACUdeyp8YikofT6ySJAdjG1e8?usp=sharing#scrollTo=15R56pWsdSvg

https://colab.research.google.com/drive/1jjJhJHVvunEOXf3bUHmLNVMm_cKqls26?usp=sharing 

# Installing jupyterlab on macOS Through homebrew
There are many ways to install jupyterlab. Here is one we have tested to work with TINC.
```
brew install jupyterlab
```

When brew installs jupyter lab and installs python3.8, it mentions it is keg only, so need to follow brew's instructions:
```
Python has been installed as /usr/local/opt/python@3.8/bin/python3
You can install Python packages with /usr/local/opt/python@3.8/bin/pip3 install <package>
They will install into the site-package directory
/usr/local/opt/python@3.8/Frameworks/Python.framework/Versions/3.8/lib/python3.8/site-packages
See: https://docs.brew.sh/Homebrew-and-Python
python@3.8 is keg-only, which means it was not symlinked into /usr/local,
because this is an alternate version of another formula.
If you need to have python@3.8 first in your PATH run:
echo 'export PATH="/usr/local/opt/python@3.8/bin:$PATH"' >> /Users/cannedstar/.bash_profile
For compilers to find python@3.8 you may need to set:
export LDFLAGS="-L/usr/local/opt/python@3.8/lib"
For pkg-config to find python@3.8 you may need to set:
export PKG_CONFIG_PATH="/usr/local/opt/python@3.8/lib/pkgconfig"
```

To install additional dependencies for tinc-python for the jupyter python:
```
/usr/local/opt/python@3.8/bin/pip3 install filelock matplotlib ipywidgets
```
