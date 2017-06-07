from setuptools import setup, find_packages

def readme():
    with open("README.md", 'r') as f:
        return f.read()

setup(
    name = "rec_api",
    description = "records api",
    long_description = readme(),
    packages = find_packages(
        exclude = [
        ]
    ),
    install_requires = [
        'flask>0',
        'flask_env',
        'flask_restful',
        'pymongo'
    ],
)
