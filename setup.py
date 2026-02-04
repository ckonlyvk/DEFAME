from setuptools import setup, find_packages

setup(
    name="defame",
    version="0.1.0",
    packages=find_packages() + ['config'],  # Include config package
    install_requires=[
        "ezmm",
        "pydantic",
        # Dependencies are already in requirements.txt, 
        # but listing packages here ensures they are found.
    ],
)
