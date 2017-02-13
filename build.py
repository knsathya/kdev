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

_TOP_DIR = os.getenv("KDEV_TOP", os.getcwd())
_ROOTFS_DIR = os.getenv("KDEV_ROOTFS", os.getcwd() + "/rootfs")
_KERNEL_DIR = os.getenv("KDEV_KERNEL", os.getcwd() + "/kernel")
_OUT_DIR = os.getenv("KDEV_OUT", os.getcwd() + "/out")
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

class BoardConfigParser(object):
    #Minimum config file sections
    min_cfg_sections = ['BUILD_OPTIONS']
    #Minimum config file optioons
    min_cfg_options = ['arch', 'soc_name', 'board_name', 'version']
    #Build section name
    build_section_name = "BUILD_OPTIONS"

    def __init__(self, cfg):
        self.cfg_file = cfg
        try:
            self.parser = ConfigParser.ConfigParser()
            self.parser.read(self.cfg_file)
        except ConfigParser.ParsingError, err:
            print 'cfg parse error:', err

        sections = self.parser.sections()

        assert set(BoardConfigParser.min_cfg_sections).issubset(set(sections)), \
            self.cfg_file + " : Missing section error"

        build_options = self.parser.options(BoardConfigParser.build_section_name)

        assert set(BoardConfigParser.min_cfg_options).issubset(set(build_options)), \
            self.cfg_file + " : Missing option error"

        self.arch_name = self.parser.get(BoardConfigParser.build_section_name, "arch")
        self.soc_name = self.parser.get(BoardConfigParser.build_section_name, "soc_name")
        self.board_name = self.parser.get(BoardConfigParser.build_section_name, "board_name")
        self.version_name = self.parser.get(BoardConfigParser.build_section_name, "version")

    def __str__(self):
        return "Arch = " + self.arch_name + "\n" + "SOC  = " + self.soc_name + "\n" +\
               "BOARD = " + self.board_name + "\n" + "VERSION = " + self.version_name


class BuildRecipe(object):
    board_conf_file_pattern = "board.cfg"
    kernel_cmdline_file_pattern = "cmdline"
    kernel_config_file_pattern = "kernel.config"

    def __init__(self, root):

        if not os.path.isdir(root):
            raise AttributeError

        board_conf_file = root + "/" + BuildRecipe.board_conf_file_pattern
        if not os.path.isfile(board_conf_file):
            logger.warn("%s: kernel config file missing", root)
            raise IOError

        try:
            self.bconf_parser = BoardConfigParser(board_conf_file)
            self.board_config = board_conf_file
        except AssertionError:
            logger.warn("%s: config file parse error", board_conf_file)
            raise AssertionError

        kernel_config_file = root + "/" + BuildRecipe.kernel_config_file_pattern
        if not os.path.isfile(kernel_config_file):
            logger.warn("%s: kernel config file missing", root)
            raise IOError

        self.kernel_config = kernel_config_file

        kernel_cmdline_file = root + "/" + BuildRecipe.kernel_cmdline_file_pattern
        if not os.path.isfile(kernel_cmdline_file):
            logger.warn("%s: kernel cmdline file missing", root)

        self.kernel_cmdline = kernel_cmdline_file

    def build_name(self):
        return self.bconf_parser.soc_name + "_" + self.bconf_parser.board_name +\
               "_" + self.bconf_parser.version_name

    def __str__(self):
        return self.build_name()



def build_main():

    valid_recipes = []
    recipe = None
    selected_target = None

    # get the list of valid recipes
    target_dirs = map(lambda x: os.path.dirname(os.path.realpath(x)),
                      glob_recursive(_TARGET_RECIPES_DIR, BuildRecipe.board_conf_file_pattern))

    for target_dir in target_dirs:
        try:
            recipe = BuildRecipe(target_dir)
        except Exception as e:
            logger.warn("Invalid Recipe in %s", target_dir)
            recipe = None

        if recipe is not None:
            logger.debug("valid recipe %s", recipe)
            valid_recipes.append(recipe)

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

if __name__ == '__main__':

    print "test func"
    build_main()
