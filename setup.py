from setuptools import find_packages, setup

setup(
    name="polarise-compute-subnet",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'requests',
        'docker',
        'pyyaml'
    ]
)