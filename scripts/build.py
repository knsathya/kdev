#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
import tempfile
from shutil import copyfile, move
from board_config import KdevBoardConfig

_TOP_DIR = os.getenv("KDEV_TOP", os.getcwd())
_ROOTFS_DIR = os.getenv("KDEV_ROOTFS", os.path.join(os.getcwd(), "rootfs", "rootfs"))
_KERNEL_DIR = os.getenv("KDEV_KERNEL", os.path.join(os.getcwd(), "kernel"))
_OUT_DIR = os.getenv("KDEV_OUT", os.path.join(os.getcwd(), "out"))
_KERNEL_OUT_DIR = os.getenv("KDEV_KOBJ_OUT", None)
_ROOTFS_OUT_DIR = os.getenv("KDEV_ROOTFS_OUT", None)
_TARGET_RECIPES_DIR = os.getenv("TARGET_RECIPES", os.path.join(os.getcwd(), "target-recipes"))
_SELECTED_TARGET_DIR = os.getenv("SELECTED_TARGET_DIR", None)

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

class BuildRecipe(object):

    def __init__(self, root):

        board_cfg = "board.cfg"

        if not os.path.isdir(root):
            logger.warn("%s: invalid build recipe root", root)
            raise AttributeError

        board_conf_file = os.path.join(root, board_cfg)
        if not os.path.isfile(board_conf_file):
            logger.warn("%s: board config file missing", board_conf_file)
            raise IOError

        self.board_config = KdevBoardConfig(board_conf_file)
        self.board_options = self.board_config.board_options
        self.build_options = self.board_config.build_options
        self.rootfs_options = self.board_config.rootfs_options
        self.bootimg_options = self.board_config.bootimg_options

        if not os.path.isfile(self.build_options.kernel_config):
            logger.warn("%s: kernel config file missing",
                    self.build_options.kernel_config)
            raise IOError

        self.kernel_config = self.build_options.kernel_config

        if not os.path.isfile(self.build_options.cmdline):
            logger.warn("%s: kernel cmdline file missing",
                    self.build_options.cmdline)
            raise IOError

        self.kernel_cmdline = self.build_options.cmdline

        self.kernel_diff_config = self.build_options.kernel_diffconfig
        if self.kernel_diff_config is None:
            logger.warn("%s: kernel diff config file missing",
                    self.kernel_diff_config)

        self.target_name = self.board_config.board_options.target_name
        self.target_arch = self.board_config.board_options.arch

    def __str__(self):
        out_str= ""

        out_str_append = lambda x,y : out_str + x + " = " + y +"\n"

        out_str = out_str_append("BOARD_CONFIG", self.board_config.cfg)
        out_str = out_str_append("KERNEL_CONFIG", self.kernel_config)
        out_str = out_str_append("KERNEL_CMDLINE", self.kernel_cmdline)
        out_str = out_str_append("KERNEL_DIFFCONFIG",
                                 self.kernel_diff_config if self.kernel_diff_config is not None else "None")

        return out_str

def build_rootfs():
    logger.info("Building rootfs")
    rootfs_image = os.path.join(_OUT_DIR, "rootfs.img")
    rootfs_ext2_image = os.path.join(_OUT_DIR, "rootfs.img.ext2")
    cwd = os.getcwd()
    os.chdir(_ROOTFS_DIR)
    os.system("find . | cpio --quiet -H newc -o | gzip -9 -n > %s" % (rootfs_image))
    os.system("dd if=/dev/zero of=%s bs=1M count=1024" % (rootfs_ext2_image))
    os.system("mkfs.ext2 -F %s -L rootfs" % (rootfs_ext2_image))
    os.chdir(cwd)
    temp_dir = tempfile.mkdtemp()
    os.system("sudo mount -o loop,rw,sync %s %s" % (rootfs_ext2_image, temp_dir))
    os.chdir(temp_dir)
    os.system("sudo gzip -cd %s | sudo cpio -imd --quiet" % (rootfs_image))
    os.chdir(cwd)
    os.system(("sudo umount %s" % temp_dir))
    os.removedirs(temp_dir)

def sync_rootfs():
    logger.info("Syncing rootfs")
    rsync_cmd = ["rsync -a"]
    rsync_cmd.append(_ROOTFS_DIR + "/")
    rsync_cmd.append(_ROOTFS_OUT_DIR)
    os.system(' '.join(rsync_cmd))

def build_kernel(arch, config, use_efi_header, rootfs_dir, kernel_dir, out_dir):
    logger.info("Building kernel")
    kobj = BuildKernel(kernel_dir)
    kobj.set_build_env(arch=arch, config=config, use_efi_header=use_efi_header,
                       rootfs=rootfs_dir, out=out_dir,
                       threads=multiprocessing.cpu_count())
    kobj.make_kernel(log=False)
    kobj.make_mod_install(modpath=rootfs_dir, log=False)

def generate_image(arch, build_efi_image=False, build_android_image=False, build_yocto_image=False):

    if build_efi_image:
        copyfile(os.path.join(_KERNEL_OUT_DIR, "arch", arch, "boot", "bzImage"), os.path.join(_OUT_DIR, "bzImage.efi"))

def get_build_target():
    valid_recipes = []
    recipe = None
    selected_target = None

    # get the list of valid recipes
    target_dirs = map(lambda x: os.path.dirname(os.path.realpath(x)),
                      glob_recursive(_TARGET_RECIPES_DIR, "board.cfg"))

    print target_dirs

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
            print str(index) + " : " + recipe.target_name

        user_input = raw_input("Please select build target: \n")
        if user_input.isdigit():
            user_input = int(user_input) - 1
        else:
            user_input = -1

    selected_target = valid_recipes[user_input]

    return selected_target

def select_build_target(target_dir=None):

    global _OUT_DIR, _KERNEL_OUT_DIR, _ROOTFS_OUT_DIR
    recipe = None

    if target_dir is not None:
        try:
            recipe = BuildRecipe(target_dir)
        except Exception as e:
            logger.warn(e)
            logger.warn("Invalid Recipe in %s", target_dir)
            recipe = None

    logger.info("Falling back to user selection")

    if recipe is None:
        recipe = get_build_target()

    # mkdir out dir
    if not os.path.exists(_OUT_DIR):
        os.mkdir(_OUT_DIR, 0775)

    # mdkir recipe out dir
    _OUT_DIR = os.path.join(_OUT_DIR, recipe.target_name)
    if not os.path.exists(_OUT_DIR):
        os.mkdir(_OUT_DIR, 0775)

    #mkdir kernel our dir
    if _KERNEL_OUT_DIR is None:
        _KERNEL_OUT_DIR = os.path.join(_OUT_DIR, "kernel-obj")
    if not os.path.exists(_KERNEL_OUT_DIR):
        os.mkdir(_KERNEL_OUT_DIR, 0775)

    #mkdir rootfs our dir
    if _ROOTFS_OUT_DIR is None:
        _ROOTFS_OUT_DIR = os.path.join(_OUT_DIR, "rootfs")
    if not os.path.exists(_ROOTFS_OUT_DIR):
        os.mkdir(_ROOTFS_OUT_DIR, 0775)

    logger.debug("Building target image for %s", recipe.target_name)
    logger.info("Kernel Source %s", _KERNEL_DIR)
    logger.info("Rootfs Source %s", _ROOTFS_DIR)
    logger.info("Out dir %s", _OUT_DIR)
    logger.info("Kernel Out dir %s", _KERNEL_OUT_DIR)
    logger.info("Rootfs Out dir %s", _ROOTFS_OUT_DIR)
    logger.info("RECIPE INFO:")
    logger.info("%s", recipe)
    logger.info("Build Params:")
    logger.info("%s", recipe.board_options)

    return recipe

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

def check_env(kernel_dir, rootfs_dir, out_dir):

    print "test"

    global _ROOTFS_DIR, _KERNEL_DIR
    global _OUT_DIR

    if kernel_dir is not None and os.path.exists(kernel_dir):
        _KERNEL_DIR = kernel_dir

    if rootfs_dir is not None and os.path.exists(rootfs_dir):
        _ROOTFS_DIR = rootfs_dir

    #check if kernel_dir is valid
    if not os.path.exists(os.path.expanduser(_KERNEL_DIR)):
        logger.error("dir %s does not exist", _KERNEL_DIR)
        raise IOError

    if not os.path.exists(os.path.join(os.path.expanduser(_KERNEL_DIR), 'Makefile')):
        logger.error("Invalid kernel %s", _KERNEL_DIR)
        raise IOError

    #check if rootfs is valid
    if not os.path.exists(os.path.expanduser(_ROOTFS_DIR)):
        logger.error("dir %s does not exist", _ROOTFS_DIR)
        raise IOError

    if out_dir is not None:
        if not os.path.exists(os.path.expanduser(out_dir)):
            os.mkdir(out_dir, 0775)
            _OUT_DIR = out_dir

if __name__ == '__main__':

    print "test func"
    parser = argparse.ArgumentParser(description='kdev build app')

    parser.add_argument('-k', '--kernel-dir', action='store', dest='kernel_dir',
                        type=lambda x: is_valid_kernel(parser, x),
                        help='kernel source directory')

    parser.add_argument('-r', '--rootfs-dir', action='store', dest='rootfs_dir',
                        type=lambda x: is_valid_directory(parser, x),
                        help='rootfs directory')

    parser.add_argument('-o', '--out-dir', action='store', dest='out_dir',
                        type=lambda x: is_valid_directory(parser, x),
                        help='out directory')

    parser.add_argument('-t', '--target-recipe', action='store', dest='recipe_dir',
                        type=lambda x: is_valid_directory(parser, x),
                        help='target recipe directory')

    parser.add_argument('--build-efi', action='store_true', dest='build_efi_image', help='Build efi image')

    android_group = parser.add_argument_group('build-android')
    android_group.add_argument('--build-android', action="store_true", default=False, dest='build_android_image',
                               help='Build android image')
    android_group.add_argument('--pk8', metavar='pk8-cert', type=argparse.FileType('rt'), help="pk8 certificate")
    android_group.add_argument('--x509', metavar='x509-cert', type=argparse.FileType('rt'), help="x509 certificate")

    parser.add_argument('--log', action='store_true', default=False, dest='use_log',
                        help='logs to file')

    parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')

    args = parser.parse_args()

    print args

    target_dir = args.recipe_dir

    if target_dir is None:
        target_dir  = _SELECTED_TARGET_DIR

    check_env(args.kernel_dir, args.rootfs_dir, args.out_dir)

    recipe = select_build_target(target_dir)

    sync_rootfs()

    build_kernel(arch=recipe.target_arch,
                 config=recipe.kernel_config,
                 use_efi_header=True, rootfs_dir=_ROOTFS_OUT_DIR,
                 kernel_dir=_KERNEL_DIR, out_dir=_KERNEL_OUT_DIR)

    build_rootfs()

    build_efi_image = args.build_efi_image | recipe.build_options.build_efi

    generate_image(recipe.target_arch, build_efi_image)

