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
_DIR_MODE = 0775

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

        #initalize some basic env variables
        self.recipe_dir = root
        self.out = _OUT_DIR
        self.kernel_src = _KERNEL_DIR
        self.rootfs_src = _ROOTFS_DIR
        self.kernel_out = _KERNEL_OUT_DIR
        self.rootfs_out = _ROOTFS_OUT_DIR
        #initalize kernel build options
        self.kernel_config = "None"
        self.kernel_cmdline = "None"
        self.kernel_diffconfig = "None"
        self.target_arch = "x86_64"
        #initalize some board options
        self.board_config = None
        self.board_options = None
        self.build_options = None
        self.rootfs_options = None
        self.bootimg_options = None
        self.target_name = "qemu_x86_64"
        self.build_efi = False
        self.build_bootimg = False
        self.build_yocto = False
        self.kobj = None

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
            self.kernel_diff_config = "None"

        self.target_name = self.board_config.board_options.target_name
        self.board_name = self.board_config.board_options.board
        self.target_arch = self.board_config.board_options.arch
        self.build_efi = self.build_options.build_efi
        self.build_bootimg = self.build_options.build_bootimg
        self.build_yocto = self.build_options.build_yocto

    def __sync_rootfs__(self):
        logger.info("Syncing rootfs")
        rsync_cmd = ["rsync -a"]
        rsync_cmd.append(self.rootfs_src + "/")
        rsync_cmd.append(self.rootfs_out)
        os.system(' '.join(rsync_cmd))

    def init_build(self, out=_OUT_DIR, kernel_src=_KERNEL_DIR,
            rootfs_src=_ROOTFS_DIR, build_efi=False,
            build_bootimg=False, build_yocto=False):

        self.out = out
        self.kernel_src = kernel_src
        self.rootfs_src = rootfs_src
        self.build_efi = True if build_efi else False
        self.build_bootimg = True if build_bootimg else False
        self.build_yocto = True if build_yocto else False

        # mkdir out dir
        if not os.path.exists(self.out):
            os.mkdir(self.out, _DIR_MODE)

        # mdkir recipe out dir
        self.out = os.path.join(self.out, recipe.target_name)
        if not os.path.exists(self.out):
            os.mkdir(self.out, _DIR_MODE)

        #mkdir kernel out dir
        if self.kernel_out is None:
            self.kernel_out = os.path.join(self.out, "kernel-obj")
        if not os.path.exists(self.kernel_out):
            os.mkdir(self.kernel_out, _DIR_MODE)

        #mkdir rootfs our dir
        if self.rootfs_out is None:
            self.rootfs_out = os.path.join(self.out, "rootfs")
        if not os.path.exists(self.rootfs_out):
            os.mkdir(self.rootfs_out, _DIR_MODE)

        self.__sync_rootfs__()

        logger.debug("Building target image for %s", self.target_name)
        logger.info("Recipe info %s", self)

    def __build_kernel__(self):
        logger.info("Building kernel")
        kobj = BuildKernel(self.kernel_src)
        kobj.set_build_env(arch=self.target_arch,
                config=self.kernel_config,
                use_efi_header=self.build_efi,
                rootfs=self.rootfs_out, out=self.kernel_out,
                threads=multiprocessing.cpu_count())
        kobj.make_kernel(log=False)
        kobj.make_mod_install(modpath=self.rootfs_out, log=False)

    def __build_rootfs__(self):
        logger.info("Building rootfs")
        rootfs_image = os.path.join(self.out, "rootfs.img")
        rootfs_ext2_image = os.path.join(self.out, "rootfs.img.ext2")
        cwd = os.getcwd()
        os.chdir(self.rootfs_out)
        hostname = os.path.join(self.rootfs_out, 'etc', 'hostname')
        with open(hostname, 'w+') as fp:
            fp.truncate()
            fp.write(self.board_name)
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

    def start_build(self):
        logger.debug("starting build\n")

        self.__build_kernel__()
        self.__build_rootfs__()

    def generate_images(self):
        logger.debug("generate images\n")
        if self.build_efi:
            copyfile(os.path.join(self.kernel_out, "arch",
                self.target_arch, "boot", "bzImage"),
                os.path.join(self.out, "bzImage.efi"))

    def __str__(self):
        out_str= "\n"

        out_str_append = lambda x,y : out_str + "\t" + x + " = " + y +"\n" if x is not None and y is not None else "None"

        out_str += "env options:\n"
        out_str = out_str_append("kernel src", self.kernel_src)
        out_str = out_str_append("rootfs src", self.rootfs_src)
        out_str = out_str_append("out dir", self.out)
        out_str = out_str_append("kernel out dir", self.kernel_out)
        out_str += '%s' % self.board_config

        return out_str

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
            logger.debug("valid recipe %s", recipe.target_name)
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

def select_build_target(target_dir):
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

    #check if kernel_dir is valid
    if not os.path.exists(os.path.expanduser(kernel_dir)):
        logger.error("dir %s does not exist", kernel_dir)
        raise IOError

    #check if its a valid kernel source
    if not os.path.exists(os.path.join(os.path.expanduser(kernel_dir), 'Makefile')):
        logger.error("Invalid kernel %s", kernel_dir)
        raise IOError

    #check if rootfs is valid
    if not os.path.exists(os.path.expanduser(rootfs_dir)):
        logger.error("dir %s does not exist", rootfs_dir)
        raise IOError

if __name__ == '__main__':

    print "test func"
    parser = argparse.ArgumentParser(description='kdev build app')

    parser.add_argument('-k', '--kernel-dir', action='store', dest='kernel_dir',
                        type=lambda x: is_valid_kernel(parser, x),
                        default=_KERNEL_DIR,
                        help='kernel source directory')

    parser.add_argument('-r', '--rootfs-dir', action='store', dest='rootfs_dir',
                        type=lambda x: is_valid_directory(parser, x),
                        default=_ROOTFS_DIR,
                        help='rootfs directory')

    parser.add_argument('-o', '--out-dir', action='store', dest='out_dir',
                        type=lambda x: is_valid_directory(parser, x),
                        default=_OUT_DIR,
                        help='out directory')

    parser.add_argument('-t', '--target-recipe', action='store', dest='recipe_dir',
                        type=lambda x: is_valid_directory(parser, x),
                        default=_SELECTED_TARGET_DIR,
                        help='target recipe directory')

    parser.add_argument('--build-efi', action='store_true', dest='build_efi_image', help='Build efi image')

    parser.add_argument('--log', action='store_true', default=False, dest='use_log',
                        help='logs to file')

    parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')

    args = parser.parse_args()

    print args

    target_dir = args.recipe_dir

    check_env(args.kernel_dir, args.rootfs_dir, args.out_dir)

    recipe = select_build_target(args.recipe_dir)

    recipe.init_build(args.out_dir, args.kernel_dir,
            args.rootfs_dir, args.build_efi_image)

    recipe.start_build()

    recipe.generate_images()