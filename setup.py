#!/usr/bin/env python

import os
from setuptools import setup

def get_long_description():
    filename = os.path.join(os.path.dirname(__file__), 'README.md')
    with open(filename) as f:
        return f.read()

setup(name='typewriter',
      version='1.2.0',
      description="TypeWriter: Generate PEP-484 type annotations",
      long_description=get_long_description(),
      long_description_content_type="text/markdown",
      author='Chad Dombrova',
      author_email='chadrik@gmail.com',
      url='https://github.com/chadrik/typewriter',
      license='Apache 2.0',
      platforms=['POSIX'],
      packages=['pyannotate_runtime', 'typewriter',
                'typewriter.annotations', 'typewriter.fixes'],
      entry_points={'console_scripts': ['typewriter=typewriter.annotations.__main__:main']},
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Software Development',
          ],
      install_requires = ['six',
                          'docutils',
                          'mypy_extensions',
                          'typing >= 3.5.3; python_version < "3.5"'
                          ],
      )
