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
import multiprocessing
from pyparsing import *
from BuildKernel import BuildKernel

_TOP_DIR = os.getenv("KDEV_TOP", os.getcwd())
_ROOTFS_DIR = os.getenv("KDEV_ROOTFS", os.path.join(os.getcwd(), "/rootfs"))
_KERNEL_DIR = os.getenv("KDEV_KERNEL", os.path.join(os.getcwd(), "/kernel"))
_OUT_DIR = os.getenv("KDEV_OUT", os.path.join(os.getcwd(), "out"))
_KERNEL_OUT_DIR = os.getenv("KDEV_KOBJ_OUT", os.path.join(os.getcwd(), "out/kernel-obj"))
_TARGET_RECIPES_DIR = os.getenv("TARGET_RECIPES", os.getcwd() + "/target-recipes")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def glob_recursive(root, pattern):
    file_list = []
    for subdir, dirs, files in os.walk(root):
        for file in fnmatch.filter(files, pattern):
            file_list.append(os.path.join(subdir, file))

    return file_list

class BoardConfig(object):

    def __init__(self, cfg):

        # Minimum config file sections
        min_cfg_sections = ['BUILD_OPTIONS']

        # build config sections and options
        build_section_name = "BUILD_OPTIONS"
        build_cfg_options = ['arch', 'soc', 'board', 'version']

        self.cfg_file = cfg

        try:
            self.parser = ConfigParser.ConfigParser()
            self.parser.read(self.cfg_file)
        except ConfigParser.ParsingError, err:
            raise Exception("Config parse error")

        sections = self.parser.sections()
        if not set(min_cfg_sections).issubset(set(sections)):
            raise Exception("Missing config sections error")

        #build section checks
        build_options = self.parser.options(build_section_name)
        if not set(build_cfg_options).issubset(set(build_options)):
            raise Exception("Missing config options error")

        get_build_option = lambda x : self.parser.get(build_section_name, x)

        self.arch = get_build_option("arch")
        self.soc = get_build_option("soc")
        self.board = get_build_option("board")
        self.version = get_build_option("version")

    def __str__(self):
        return "Arch = " + self.arch + "\n" + "SOC  = " + self.soc + "\n" +\
               "BOARD = " + self.board + "\n" + "VERSION = " + self.version


class BuildRecipe(object):

    def __init__(self, root):

        board_cfg = "board.cfg"
        kernel_cmdline = "cmdline"
        kernel_config = "kernel.config"

        if not os.path.isdir(root):
            logger.warn("%s: invalid build recipe root", root)
            raise AttributeError

        board_conf_file = os.path.join(root, board_cfg)
        if not os.path.isfile(board_conf_file):
            logger.warn("%s: board config file missing", board_conf_file)
            raise IOError

        self.board_config = BoardConfig(board_conf_file)

        kernel_config_file = os.path.join(root, kernel_config)
        if not os.path.isfile(kernel_config_file):
            logger.warn("%s: kernel config file missing", kernel_config_file)
            raise IOError

        self.kernel_config = kernel_config_file

        kernel_cmdline_file = os.path.join(root, kernel_cmdline)
        if not os.path.isfile(kernel_cmdline_file):
            logger.warn("%s: kernel cmdline file missing", kernel_cmdline_file)
            raise IOError

        self.kernel_cmdline = kernel_cmdline_file

    def __str__(self):
        return self.board_config.soc + "_" + self.board_config.board +\
               "_" + self.board_config.version

def build_main():
    valid_recipes = []
    recipe = None
    selected_target = None

    # get the list of valid recipes
    target_dirs = map(lambda x: os.path.dirname(os.path.realpath(x)),
                      glob_recursive(_TARGET_RECIPES_DIR, "board.cfg"))

    for target_dir in target_dirs:
        try:
            recipe = BuildRecipe(target_dir)
        except Exception as e:
            logger.warn(e)
            logger.warn("Invalid Recipe in %s", target_dir)
            recipe = None

        if recipe is not None:
            logger.debug("valid recipe %s", recipe)
            valid_recipes.append(recipe)

    if len(valid_recipes) <= 0:
        raise Exception("No valid targets found")

    user_input = -1

    while not 0 <= user_input < len(valid_recipes):
        print "Build targets available:"
        index = 0
        for recipe in valid_recipes:
            index = index + 1
            print str(index) + " : " + str(recipe)

        user_input = raw_input("Please select build target: \n")
        if user_input.isdigit():
            user_input = int(user_input) - 1
        else:
            user_input = -1

    selected_target = valid_recipes[user_input]

    logger.debug("Building target image for %s", selected_target)

    logger.info("Board Config file %s", selected_target.board_config)
    logger.info("Kernel Config file %s", selected_target.kernel_config)
    logger.info("Kernel Cmdline file %s", selected_target.kernel_cmdline)
    logger.info("Kernel Source %s", _KERNEL_DIR)
    logger.info("Rootfs Source %s", _ROOTFS_DIR)
    logger.info("Out dir %s", _OUT_DIR)
    logger.info("Kernel Out dir %s", _KERNEL_OUT_DIR)
    logger.info("Build Params:")
    logger.info("ARCH = %s", selected_target.board_config.arch)
    logger.info("SOC = %s", selected_target.board_config.soc)

    kobj = BuildKernel(_KERNEL_DIR)

    kobj.set_build_env(arch=selected_target.board_config.arch,
                       config=selected_target.kernel_config,
                       use_efi_header=True, rootfs=_ROOTFS_DIR,
                       out=_OUT_DIR, threads=multiprocessing.cpu_count())

if __name__ == '__main__':

    print "test func"
    build_main()
