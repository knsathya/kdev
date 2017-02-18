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

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
            logger.error("Invalid kernel source directory")
            raise IOError

        key_value_format = lambda x, y: Combine(LineStart() + Literal(x) + restOfLine(y))
        version_format = key_value_format("VERSION = ", 'version')
        patchlevel_format = key_value_format("PATCHLEVEL = ", 'patchlevel')
        sublevel_format = key_value_format("SUBLEVEL = ", 'sublevel')
        extraversion_format = key_value_format("EXTRAVERSION = ", 'extraversion')
        name_format = key_value_format("NAME = ", 'name')

        # Extract version and name info
        try:
            self.version = version_format.scanString(makefile_contents).next()[0].version
            self.patchelevel = patchlevel_format.scanString(makefile_contents).next()[0].patchlevel
            self.sublevel = sublevel_format.scanString(makefile_contents).next()[0].sublevel
            self.extraversion = extraversion_format.scanString(makefile_contents).next()[0].extraversion
            self.name = name_format.scanString(makefile_contents).next()[0].name
        except StopIteration:
            logger.error("Stop iteration exception")
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
        def_config_path = "arch/x86/config/x864_defconfig"
        self.config = os.path.join(self.kernel_dir, def_config_path)
        self.update_config_list = {}

        # Initalize efi/initramfs build flags
        self.use_efi_header = False
        self.use_init_ramfs = False

    def set_build_env(self, arch="x86_64", use_efi_header=False, rootfs="", out="", threads=multiprocessing.cpu_count()):
        '''
        Set the build parameters for compilation.
        :param arch: Architecture to be used in compilation.
        :param use_efi_header: True/False
        :param rootfs: Pass rootfs path if need initramfs.
        :param out: kernel out directory.
        :param threads: No of threads to be used in compilation.
        :return: Throws exception if the input parameters are invalid.
        '''

        if rootfs != "":
            if os.path.exists(rootfs):
                self.use_init_ramfs = True
                self.build_params['rootfs'] = rootfs
            else:
                logger.error("rootfs dir %s does not exist", rootfs)
                raise AttributeError

        if out != "":
            if os.path.exists(out):
                self.build_params['out'] = out
            else:
                logger.error("out dir %s does not exist", out)
                raise AttributeError

        self.use_efi_header = use_efi_header

        self.build_params['arch'] = arch
        self.build_params['threads'] = threads

        logger.info(self.__str_build_params__())

    def update_config_options(self, config="", update_config_list = []):
        '''
        Updates the .config with updates from config_list
        :param config: kernel config file
        :param config_list: [CONFIG_* = n/m/y]
        :return: Throws exception if the config_list input is invaid.
        '''

        if config != "" :
            if os.path.exists(config):
                self.config_faile = config
            else:
                logger.error("config file does not exist")
                raise AttributeError

        if len(update_config_list) > 0:
            for config in update_config_list:
                config_option = config.split("=")
                #config options len check
                if len(config_option) != 2:
                    logger.error("config option format error")
                    raise AttributeError
                # config option  check
                if not config_option[0].startswith("CONFIG_"):
                    logger.error("config option should start with CONFIG_")
                    raise AttributeError
                # config option value check
                if config_option[1] not in ['y', 'm', 'n']:
                    logger.error("config option value should be y/m/n")
                    raise AttributeError

                logger.debug("updating " + config)

    def make_menuconfig(self):
        logger.info("Run menuconfig")

    def make_kernel(self):
        logger.info("Build kernel")

    def __str_build_params__(self):
        build_str = "Build Params :\n" + \
        "Arch : " + self.build_params['arch'] + "\n" + \
        "Rootfs : " + self.build_params['rootfs'] + "\n" + \
        "Out : " + self.build_params['out'] + "\n" + \
        "Threads : " + str(self.build_params['threads']) + "\n" + \
        "Use EFI header : " + str(self.use_efi_header) + "\n"

        return build_str

    def __str__(self):
        out_str = "Version : " + self.uname + "\n" +\
                  self.__str_build_params__()

        return out_str

if __name__ == '__main__':

    print "test func"
    #build_main()
    kobj = BuildKernel(os.getcwd())
    kobj.set_build_env(arch="arm8", use_efi_header=True, rootfs=os.getcwd())
    kobj.update_config_options(config=os.path.join(os.getcwd(), "x86_64_defconfig"))
    kobj.make_menuconfig()
    kobj.make_kernel()
