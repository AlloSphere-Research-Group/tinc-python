import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

print(setuptools.find_packages())

setuptools.setup(
    name="tinc", 
    version="0.9.56",
    author="Andres Cabrera",
    author_email="mantaraya36@gmail.com",
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
    install_requires=['numpy', 'matplotlib', 'filelock', 'netcdf4', "jsonschema", "protobuf", "Pillow"],
    package_data = {"tinc" : ["tinc_cache_schema.json"]},
    python_requires='>=3.6',
)
