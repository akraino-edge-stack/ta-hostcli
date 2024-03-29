#!/usr/bin/env python
# Copyright 2019 Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


PROJECT = 'hostcli'

VERSION = '0.1'

from setuptools import setup, find_packages

setup(
    name=PROJECT,
    version=VERSION,
    description='HOST CLI',
    author='Janne Suominen',
    author_email='janne.suominen@nokia.com',
    platforms=['Any'],
    scripts=[],
    provides=[],
    install_requires=['cliff', 'requests', 'keystoneauth1', 'osc_lib'],
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'hostcli = hostcli.main:main'
        ],
    },
    zip_safe=False,
)
