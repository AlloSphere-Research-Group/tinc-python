import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

print(setuptools.find_packages())

setuptools.setup(
    name="tinc", 
    version="0.9.10",
    author="Andres Cabrera",
    author_email="acabrera@ucsb.edu",
    description="TINC python module",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AlloSphere-Research-Group/tinc-python",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    py_modules= ['tinc'],
    install_requires=['numpy', 'matplotlib', 'filelock', 'netcdf4', "jsonschema", "protobuf"],
    package_data = {"tinc" : ["tinc_cache_schema.json"]},
    python_requires='>=3.6',
)
