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
import argparse

_TOP_DIR = os.getenv("KDEV_TOP", os.getcwd())
_ROOTFS_DIR = os.getenv("KDEV_ROOTFS", os.path.join(os.getcwd(), "/rootfs"))
_KERNEL_DIR = os.getenv("KDEV_KERNEL", os.path.join(os.getcwd(), "/kernel"))
_OUT_DIR = os.getenv("KDEV_OUT", os.path.join(os.getcwd(), "out"))
_KERNEL_OUT_DIR = os.getenv("KDEV_KOBJ_OUT", os.path.join(os.getcwd(), "out/kernel-obj"))
_TARGET_RECIPES_DIR = os.getenv("TARGET_RECIPES", os.getcwd() + "/target-recipes")

logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(format=FORMAT)
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

        #KERNEL_BUILD_OPTIONS
        kernel_build_section_name = "KERNEL_BUILD_OPTIONS"

        #BOOT_IMAGE_OPTIONS
        boot_image_section_name = "BOOT_IMAGE_OPTIONS"

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

        get_image_option = lambda x : self.parser.get(boot_image_section_name, x)

        self.use_efi_header = False
        self.use_init_ramfs = False
        self.build_header = None

        if self.parser.has_section(boot_image_section_name):
            if self.parser.has_option(boot_image_section_name, "header"):
                self.build_header = get_image_option("header")
                self.use_efi_header = True if get_image_option("header") == "efi" else False

        if self.parser.has_section(kernel_build_section_name):
            if self.parser.has_option(kernel_build_section_name, "use_init_ramfs"):
                self.use_init_ramfs = self.parser.getboolean(kernel_build_section_name, "use_init_ramfs")

    def __str__(self):
        out_str= ""

        out_str_append = lambda x,y : out_str + x + " = " + y +"\n"

        out_str = out_str_append("ARCH", self.arch)
        out_str = out_str_append("SOC", self.soc)
        out_str = out_str_append("BOARD", self.board)
        out_str = out_str_append("VERSION", self.version)
        out_str = out_str_append("HEADER", self.build_header if self.build_header is not None else "None")
        out_str = out_str_append("USE-INITRAMFS", str(self.use_init_ramfs))
        out_str = out_str_append("USE-EFI-HEADER", str(self.use_efi_header))

        return out_str


class BuildRecipe(object):

    def __init__(self, root):

        board_cfg = "board.cfg"
        kernel_cmdline = "cmdline"
        kernel_config = "kernel.config"
        kernel_diff_config = "kernel_diff.config"

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

        kernel_diff_config_file = os.path.join(root, kernel_diff_config)
        if not os.path.isfile(kernel_cmdline_file):
            logger.warn("%s: kernel diff config file missing", kernel_diff_config_file)
            self.kernel_diff_config = None
        else:
            self.kernel_diff_config = kernel_diff_config_file

    def target_name(self):
        out_str = self.board_config.soc
        if not self.board_config.board == "":
            out_str += "_" + self.board_config.board
        if not self.board_config.version == "":
            out_str += "_" + self.board_config.version

        return out_str

    def __str__(self):
        out_str= ""

        out_str_append = lambda x,y : out_str + x + " = " + y +"\n"

        out_str = out_str_append("BOARD_CONFIG", self.board_config.cfg_file)
        out_str = out_str_append("KERNEL_CONFIG", self.kernel_config)
        out_str = out_str_append("KERNEL_CMDLINE", self.kernel_cmdline)
        out_str = out_str_append("KERNEL_DIFFCONFIG",
                                 self.kernel_diff_config if self.kernel_diff_config is not None else "None")


        return out_str

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
            print str(index) + " : " + recipe.target_name()

        user_input = raw_input("Please select build target: \n")
        if user_input.isdigit():
            user_input = int(user_input) - 1
        else:
            user_input = -1

    selected_target = valid_recipes[user_input]

    logger.debug("Building target image for %s", selected_target.target_name())
    logger.info("Kernel Source %s", _KERNEL_DIR)
    logger.info("Rootfs Source %s", _ROOTFS_DIR)
    logger.info("Out dir %s", _OUT_DIR)
    logger.info("Kernel Out dir %s", _KERNEL_OUT_DIR)
    logger.info("RECIPE INFO:")
    logger.info("%s", selected_target)
    logger.info("Build Params:")
    logger.info("%s", selected_target.board_config)

    kobj = BuildKernel(_KERNEL_DIR)

    kobj.set_build_env(arch=selected_target.board_config.arch,
                       config=selected_target.kernel_config,
                       use_efi_header=True, rootfs=_ROOTFS_DIR,
                       out=_OUT_DIR, threads=multiprocessing.cpu_count())


def is_valid_kernel(parser, arg):
    if not os.path.isdir(arg) or not os.path.exists(os.path.join(arg, 'Makefile')):
        parser.error('{} is not a valid kernel source!'.format(arg))
    else:
        # File exists so return the directory
        return arg

def is_valid_directory(parser, arg):
    if not os.path.isdir(arg):
        parser.error('The directory {} does not exist!'.format(arg))
    else:
        # File exists so return the directory
        return arg

def is_valid_recipe(parser, arg):
    if not os.path.isdir(arg):
        parser.error('The directory {} does not exist!'.format(arg))

    try:
        recipe = BuildRecipe(arg)
    except Exception as e:
        parser.error('{} is not a valid recipe directory!'.format(arg))

        return arg


if __name__ == '__main__':

    print "test func"
    parser = argparse.ArgumentParser(description='kdev build app')

    parser.add_argument('-k', '--kernel-dir', action='store', dest='kernel-dir',
                        type=lambda x: is_valid_kernel(parser, x),
                        help='kernel source directory')

    parser.add_argument('-r', '--rootfs-dir', action='store', dest='rootfs-dir',
                        type=lambda x: is_valid_directory(parser, x),
                        help='rootfs directory')

    parser.add_argument('-t', '--target-recipe', action='store', dest='recipe-dir',
                        type=lambda x: is_valid_recipe(parser, x),
                        help='target recipe directory')

    parser.add_argument('--log', action='store_true', default=False, dest='use_log',
                        help='logs to file')

    parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')

    args = parser.parse_args()

    build_main()
