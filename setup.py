# -*- coding: utf-8 -*-
#
# kdev setup script
#
# Copyright (C) 2018 Sathya Kuppuswamy
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# @Author  : Sathya Kupppuswamy(sathyaosid@gmail.com)
# @History :
#            @v0.0 - Initial update
# @TODO    :
#
#

from setuptools import setup


with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(name='kdev',
      version='0.1',
      description='Python support classes for building kernel dev image',
      long_description=readme,
      classifiers=[
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Programming Language :: Python :: 2.7',
        'Topic :: Text Processing :: Linguistic',
      ],
      keywords='python git rootfs busybox buildroot toybox scripts shell linux kernel image ext2 ext3 cpio',
      url='https://github.com/knsathya/kdev.git',
      author='Kuppuswamy Sathyanarayanan',
      author_email='sathyaosid@gmail.com',
      license='GPLv2',
      packages=['kdev', 'app'],
      install_requires=[
          'click',
          'pyshell',
          'jsonparser',
          'klibs',
          'mkrootfs'
      ],
      dependency_links=[
          'git+https://github.com/knsathya/pyshell.git#egg=pyshell',
          'git+https://github.com/knsathya/jsonparser.git#egg=jsonparser',
          'git+https://github.com/knsathya/klibs.git#egg=klibs',
          'git+https://github.com/knsathya/mkrootfs.git#egg=mkrootfs'
      ],
      test_suite='tests',
      tests_require=[
          ''
      ],
      entry_points={
          'console_scripts': ['kdevimg = app.kdevimg:cli'],
      },
      include_package_data=True,
      zip_safe=False)
