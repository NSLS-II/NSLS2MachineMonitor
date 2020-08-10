#!/usr/bin/env python

import os
from setuptools import setup, find_packages
import versioneer

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

with open(os.path.join(here, 'requirements.txt')) as f:
    requirements = f.read().split()

setup(
    name='NSLS2MachineMonitor',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Slack App Server for NSLS2 Machine Messages',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='BSD (3-clause)',
    author='Stuart B. Wilkins',
    author_email='swilkins@bnl.gov',
    url='https://github.com/stuwilkins/NSLS2MachineMonitor',
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
      'console_scripts': [
            'nsls2mm = nsls2mm.nsls2mm:main'
        ],
    },
    include_package_data=True
    )
