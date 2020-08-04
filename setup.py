#!/usr/bin/env python

from distutils.core import setup
import setuptools  # noqa F401
import versioneer

setup(
    name='NSLS2MachineMonitor',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Slack App Server for NSLS2 Machine Messages',
    author='Stuart B. Wilkins',
    author_email='swilkins@bnl.gov',
    url='https://github.com/stuwilkins/NSLS2MachineMonitor',
    packages=['nsls2mm'],
    entry_points={
      'console_scripts': [
            'nsls2mm = nsls2mm.nsls2mm:main'
        ],
    },
    include_package_data=True
    )
