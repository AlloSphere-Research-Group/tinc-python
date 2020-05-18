import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="tinc-python-YOUR-USERNAME-HERE", # Replace with your own username
    version="0.0.1",
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
    python_requires='>=3.6',
)
