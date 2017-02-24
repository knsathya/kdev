#!/usr/bin/python
#
# Linux kernel related class
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
#            @v0.0 - Basic class support
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
import argparse
import subprocess
from shutil import copyfile

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def exec_command(cmd):
    logger.info("executing %s", ' '.join(cmd))
    p = subprocess.check_call(cmd)

class BuildKernel(object):

    def __init__(self, kernel_dir):
        '''
        Kernel constructor
        :param kernel_dir: Pass the path to your kernel
        '''

        # Check for kernel directory validity
        self.kernel_dir = os.path.expanduser(kernel_dir)
        try:
            with open(os.path.join(self.kernel_dir, 'Makefile'), 'r') as makefile:
                makefile_contents = makefile.read()
        except:
            logger.error("%s Invalid kernel source directory", self.kernel_dir)
            raise IOError

        key_value_format = lambda x, y: Combine(LineStart() + Literal(x) + restOfLine(y))
        version_format = key_value_format("VERSION =", 'version')
        patchlevel_format = key_value_format("PATCHLEVEL =", 'patchlevel')
        sublevel_format = key_value_format("SUBLEVEL =", 'sublevel')
        extraversion_format = key_value_format("EXTRAVERSION =", 'extraversion')
        name_format = key_value_format("NAME = ", 'name')

        # Extract version and name info
        try:
            self.version = version_format.scanString(makefile_contents).next()[0].version
            self.patchelevel = patchlevel_format.scanString(makefile_contents).next()[0].patchlevel
            self.sublevel = sublevel_format.scanString(makefile_contents).next()[0].sublevel
            self.extraversion = extraversion_format.scanString(makefile_contents).next()[0].extraversion
            self.name = name_format.scanString(makefile_contents).next()[0].name
            logger.debug("version : %s", self.version)
            logger.debug("patchlevel : %s", self.patchelevel)
            logger.debug("sublevel : %s", self.sublevel)
            logger.debug("extraversion : %s", self.extraversion)
            logger.debug("name : %s", self.name)
        except StopIteration:
            logger.error("Stop iteration exception")
            logger.debug("version : %s", self.version)
            logger.debug("patchlevel : %s", self.patchelevel)
            logger.debug("sublevel : %s", self.sublevel)
            logger.debug("extraversion : %s", self.extraversion)
            logger.debug("name : %s", self.name)
            raise NameError

        # Initalize kernel version
        self.full_version = '.'.join([self.version, self.patchelevel, self.sublevel])
        self.full_version += self.extraversion
        self.uname = "Linux version " + self.full_version

        # Initialize build params
        self.build_params = {}
        self.build_params['arch'] = "x86_64"
        self.build_params['threads'] = multiprocessing.cpu_count()
        self.build_params['rootfs'] = "Not using initramfs"
        self.build_params['out'] = os.path.join(os.getcwd(), "out")

        # Initalize config params
        def_config_path = "arch/x86/configs/x86_64_defconfig"
        self.config = os.path.join(self.kernel_dir, def_config_path)
        self.update_config_list = {}

        # Initalize efi/initramfs build flags
        self.use_efi_header = False
        self.use_init_ramfs = False

    def set_build_env(self, arch="x86_64", config=None, use_efi_header=False, rootfs=None, out=None, threads=multiprocessing.cpu_count()):
        '''
        Set the build parameters for compilation.
        :param arch: Architecture to be used in compilation.
        :param use_efi_header: True/False
        :param rootfs: Pass rootfs path if need initramfs.
        :param out: kernel out directory.
        :param threads: No of threads to be used in compilation.
        :return: Throws exception if the input parameters are invalid.
        '''
        logger.debug(locals())
        if rootfs is not None:
            logger.debug("updating rootfs")
            if os.path.exists(rootfs):
                self.use_init_ramfs = True
                self.build_params['rootfs'] = rootfs
            else:
                logger.error("rootfs dir %s does not exist", rootfs)
                raise AttributeError

        if out is not None:
            logger.debug("updating out")
            if os.path.exists(out):
                self.build_params['out'] = out
            else:
                logger.error("out dir %s does not exist", out)
                raise AttributeError

        if config is not None:
            logger.debug("updating config")
            if os.path.exists(config):
                self.config = config
            else:
                logger.error("config file does not exist")
                raise AttributeError

        if not os.path.exists(self.build_params['out']):
            os.mkdir(self.build_params['out'])

        copyfile(self.config, os.path.join(self.build_params['out'],'.config'))

        if use_efi_header is not None:
            self.use_efi_header = use_efi_header

        if arch is not None:
            self.build_params['arch'] = arch

        if threads is not None:
            self.build_params['threads'] = threads

        logger.info(self.__str_build_params__())

    def update_config_options(self, update_config_list = []):
        '''
        Updates the .config with updates from config_list
        :param config_list: [CONFIG_* = n/m/y]
        :return: Throws exception if the config_list input is invaid.
        '''

        if not os.path.exists(os.path.join(self.build_params['out'],'.config')):
            logger.error("config file %s does not exist, please set proper build env", os.path.join(self.build_params['out'],'.config'))
            raise AttributeError

        if len(update_config_list) > 0:
            for config in update_config_list:
                config_option = config.split("=")
                #config options len check
                if len(config_option) != 2:
                    logger.error("config option format error")
                    raise AttributeError
                logger.debug(config_option)
                # config option  check
                if not config_option[0].startswith("CONFIG_"):
                    logger.error("config option should start with CONFIG_")
                    raise AttributeError
                # config option value check
                if config_option[1] not in ['y', 'm', 'n']:
                    logger.error("config option value should be y/m/n")
                    raise AttributeError

                logger.debug("updating " + config)

    def __format_command__(self, args=[]):
        cmd = ["make"]
        cmd.append("ARCH="+ self.build_params['arch'])
        cmd.append("O=" + self.build_params['out'])
        cmd.append("-C")
        cmd.append(self.kernel_dir)
        cmd += args

        return cmd

    def make_menuconfig(self, flags=[]):
        if not os.path.exists(self.build_params['out']):
            os.mkdir(self.build_params['out'])

        if type(flags) is not list:
                raise Exception("Invalid make flags")

        exec_command(self.__format_command__(flags + ['menuconfig']))


    def make_kernel(self, flags=[]):
        if not os.path.exists(self.build_params['out']):
            os.mkdir(self.build_params['out'])

        if type(flags) is not list:
                raise Exception("Invalid make flags")

        exec_command(self.__format_command__(flags + ['oldconfig']))
        exec_command(self.__format_command__(flags))

    def __str_build_params__(self):
        build_str = "Build Params :\n" + \
        "Arch : " + self.build_params['arch'] + "\n" + \
        "Rootfs : " + self.build_params['rootfs'] + "\n" + \
        "Out : " + self.build_params['out'] + "\n" + \
        "Threads : " + str(self.build_params['threads']) + "\n" + \
        "Use EFI header : " + str(self.use_efi_header) + "\n" + \
        "Config FILE : " + self.config + "\n"

        return build_str

    def __str__(self):
        out_str = "Kernel Dir : " + self.kernel_dir + "\n" +\
                  "Version : " + self.uname + "\n" +\
                  self.__str_build_params__()

        return out_str

def is_valid_directory(parser, arg):
    if not os.path.isdir(arg):
        parser.error('The directory {} does not exist!'.format(arg))
    else:
        # File exists so return the directory
        return arg

if __name__ == '__main__':

    print "test func"
    #build_main()
    parser = argparse.ArgumentParser(description='Build kernel python application')
    parser.add_argument('kernel_src', action="store", type=lambda x: is_valid_directory(parser, x), help='kernel source directory path')
    parser.add_argument('-c', '--config', action='store', dest='config', type=argparse.FileType(), help='config file used for kernel compliation')
    parser.add_argument('-a', '--arch', action='store', dest='arch', type=str, help='kernel architecture')
    parser.add_argument('-r', '--rootfs', action='store', dest='rootfs', type=lambda x: is_valid_directory(parser, x), help='if using initramfs, specify path to rootfs')
    parser.add_argument('-o', '--out', action='store', dest='out', type=lambda x: is_valid_directory(parser, x), help='path to kernel out directory')
    parser.add_argument('-j', '--threads', action='store', dest='threads', type=int, default=multiprocessing.cpu_count(), help='no of threds for compilation')
    parser.add_argument('--use-efi-header', action='store_true', default=False, dest='use_efi_header', help='use efi header')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')
    args = parser.parse_args()

    print args

    kobj = BuildKernel(args.kernel_src)
    kobj.set_build_env(arch=args.arch, config=args.config.name, use_efi_header=args.use_efi_header,
                       rootfs=args.rootfs, out=args.out, threads=args.threads)
    #kobj.update_config_options(update_config_list=["CONFIG_EFI_STUB=y"])
    kobj.make_menuconfig()
    kobj.make_kernel()
