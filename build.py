#!/usr/bin/python
#
# kdev build script
#
# Copyright (C) 2017 Sathya Kuppuswamy
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Normally this is called as '. ./oe-init-build-env <builddir>'
#
# This works in most shells (not dash), but not all of them pass the arguments
# when being sourced.  To workaround the shell limitation use "set <builddir>"
# prior to sourcing this script.
#
#
# @Author  : Sathya Kupppuswamy(sathyaosid@gmail.com)
# @History :
#            @v0.0 - Inital script
# @TODO    : 
#
#

import os
import sys
import fnmatch
import logging
import ConfigParser

_TOP_DIR = os.getenv("TOP", os.getcwd())
_ROOTFS_DIR = os.getenv("ROOTFS", os.getcwd() + "/rootfs")
_TARGET_RECIPES_DIR = os.getenv("TARGET_RECIPES", os.getcwd() + "/target-recipes")
_BOARD_CONF_FILE_PATTERN = "board.conf"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def glob_recursive(root, pattern):
    file_list = []
    for subdir, dirs, files in os.walk(root):
        for file in fnmatch.filter(files, pattern):
            file_list.append(os.path.join(subdir, file))

    return file_list

def get_recipes_list():
    board_conf_files = []

    # get the list of config files
    conf_files = glob_recursive(_TARGET_RECIPES_DIR, _BOARD_CONF_FILE_PATTERN)
    for subdir, dirs, files in os.walk(_TARGET_RECIPES_DIR):
        for file in fnmatch.filter(files, _BOARD_CONF_FILE_PATTERN):
            board_conf_files.append(os.path.join(subdir, file))

    #read the board config files
    config = ConfigParser.ConfigParser()
    for f in conf_files:
        config.read(f)

if __name__ == '__main__':

    print "test func"
    get_recipes_list()
