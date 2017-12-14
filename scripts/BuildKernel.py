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
import tempfile
from shutil import copy, move
from threading  import Thread


logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(format=FORMAT)
logger.setLevel(logging.DEBUG)

def tee(infile, *files):
    """Print `infile` to `files` in a separate thread."""
    def fanout(infile, *files):
        for line in iter(infile.readline, ''):
            for f in files:
                f.write(line)
        infile.close()
    t = Thread(target=fanout, args=(infile,)+files)
    t.daemon = True
    t.start()
    return t

def teed_call(cmd_args, **kwargs):
    stdout, stderr = [kwargs.pop(s, None) for s in 'stdout', 'stderr']
    p = subprocess.Popen(cmd_args,
              stdout=subprocess.PIPE if stdout is not None else None,
              stderr=subprocess.PIPE if stderr is not None else None,
              **kwargs)
    threads = []
    if stdout is not None: threads.append(tee(p.stdout, stdout, sys.stdout))
    if stderr is not None: threads.append(tee(p.stderr, stderr, sys.stderr))
    for t in threads: t.join() # wait for IO completion
    return p.wait()

def exec_command(cmd, tee_log=False, out_log=sys.stdout, err_log=sys.stderr):
    logger.info("executing %s", ' '.join(map(lambda x: str(x), cmd)))
    if tee_log is False:
        return subprocess.check_call(cmd)
    else:
        return teed_call(cmd, stdout=out_log, stderr=err_log, bufsize=0)

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
            self.version = version_format.scanString(makefile_contents).next()[0].version.strip()
            self.patchelevel = patchlevel_format.scanString(makefile_contents).next()[0].patchlevel.strip()
            self.sublevel = sublevel_format.scanString(makefile_contents).next()[0].sublevel.strip()
            self.extraversion = extraversion_format.scanString(makefile_contents).next()[0].extraversion.strip()
            self.name = name_format.scanString(makefile_contents).next()[0].name.strip()
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
        self.target_arch = "x86_64"
        self.no_threads = multiprocessing.cpu_count()
        self.rootfs_src = "No initramfs"
        self.cross_compile = False
        self.compiler_prefix = ""
        self.out = os.path.join(os.getcwd(), "out")

        # Initalize config params
        self.config = None
        self.update_config_list = {}

        # Initalize efi/initramfs build flags
        self.use_efi_header = False
        self.use_initramfs = False

        self.log_dir = os.path.join(os.getcwd(), ".log", self.full_version)

        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        self.out_log = open(os.path.join(self.log_dir, 'out.log'), 'w')
        self.err_log = open(os.path.join(self.log_dir, 'err.log'), 'w')


    def __config_update__(self, config=None):
        if config == None:
            config = self.config
        if config is None:
            return
        new_config = os.path.join(self.out, '.config')
        if os.path.exists(config) and config != new_config:
            copy(config, new_config)
        self.config = new_config

    def __out_dir_update__(self, out=None):
        if out == None:
            out = self.out
        if not os.path.exists(out):
            s.makedirs(out)
        self.out = out
        self.config = os.path.join(self.out, '.config')

    def set_build_env(self, arch="x86_64", cross_compile=False, compiler_prefix="", config=None,
            use_efi_header=False, rootfs=None, out=None, threads=multiprocessing.cpu_count()):
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
                self.use_initramfs = True
                self.rootfs_src = rootfs
            else:
                logger.error("rootfs dir %s does not exist", rootfs)
                raise AttributeError

        if out is not None:
            logger.debug("updating out")
            if os.path.exists(out):
                self.out = out
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

        if cross_compile:
            self.cross_compile = cross_compile
            self.compiler_prefix = compiler_prefix

        if use_efi_header is not None:
            self.use_efi_header = use_efi_header

        if arch is not None:
            self.target_arch =  arch

        if threads is not None:
            self.no_threads = threads

        self.__out_dir_update__(out)

        self.__config_update__(config)

        logger.info(self.__str_build_params__())

    def update_config_options(self, update_config_list = []):
        '''
        Updates the .config with updates from config_list
        :param config_list: [CONFIG_* = n/m/y]
        :return: Throws exception if the config_list input is invaid.
        '''

        if not os.path.join(self.out, '.config'):
            logger.error("please first set config file using set_build_env() func\n")
            raise AttributeError

        config_temp = tempfile.NamedTemporaryFile(suffix='.config', prefix='kernel_', dir=self.log_dir,)
        if not os.path.exists(os.path.join(self.out,'.config')):
            logger.error("config file %s does not exist, please set proper build env", os.path.join(self.out, '.config'))
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

                logger.debug("updating " + config)

                logger.info(config_temp.name)

                config_temp.write(config + "\n")

        config_temp.seek(0)
        merge_command = [os.path.join(self.kernel_dir, "scripts", "kconfig", "merge_config.sh")]
        merge_command.append("-m")
        merge_command.append("-O")
        merge_command.append(self.log_dir)
        merge_command.append(self.config)
        merge_command.append(config_temp.name)
        exec_command(merge_command)
        move(os.path.join(self.log_dir, ".config"),  os.path.join(self.out,'.config'))
        self.config =  os.path.join(self.out,'.config')
        config_temp.close()

    def __update_config_initramfs__(self, rootfs):
        if not os.path.exists(rootfs):
            logger.error("rootfs dir does not exist\n")
            raise AttributeError

        if not os.path.join(self.out, '.config'):
            logger.error("missing config file\n")
            raise AttributeError

        update_command = [os.path.join(self.kernel_dir, "scripts", "config")]
        update_command.append("--file")
        update_command.append(os.path.join(self.out, '.config'))
        update_command.append("--set-str")
        update_command.append("CONFIG_INITRAMFS_SOURCE")
        update_command.append(rootfs)
        update_command.append("--set-val")
        update_command.append("CONFIG_INITRAMFS_ROOT_UID")
        update_command.append("0")
        update_command.append("--set-val")
        update_command.append("CONFIG_INITRAMFS_ROOT_GID")
        update_command.append("0")

        exec_command(update_command)

    def __update_config_efistub__(self):
        if not os.path.join(self.out, '.config'):
            logger.error("missing config file\n")
            raise AttributeError

        update_command = [os.path.join(self.kernel_dir, "scripts", "config")]
        update_command.append("--file")
        update_command.append(os.path.join(self.out, '.config'))
        update_command.append("--enable")
        update_command.append("CONFIG_EFI")
        update_command.append("--enable")
        update_command.append("CONFIG_EFI_STUB")

        exec_command(update_command)

    def __exec_cmd__(self, cmd, log=False):
        if log is True:
            self.out_log.seek(0)
            self.out_log.truncate()
            self.err_log.seek(0)
            self.err_log.truncate()
            return exec_command(cmd, tee_log=True, out_log=self.out_log,
                    err_log=self.err_log)
        else:
            return exec_command(cmd)

    def __make_cmd__(self, cmd="", flags=[], log=False):
        self.__out_dir_update__()
        # check for input validity
        if type(flags) is not list:
                raise Exception("Invalid make flags")
        mkcmd = ["/usr/bin/make"]
        mkcmd.append("-j" + str(self.no_threads))
        mkcmd.append("ARCH="+ self.target_arch)
        if self.cross_compile:
            mkcmd.append("CROSS_COMPILE="+ self.compiler_prefix)
        mkcmd.append("O=" + self.out)
        mkcmd.append("-C")
        mkcmd.append(self.kernel_dir)
        mkcmd += flags
        if cmd != "":
            if cmd not in ["menuconfig", "xconfig", "oldconfig",
                    "clean", "modules_install"]:
                raise Exception("Invalid make cmd {0} ".format(cmd))
            mkcmd += [cmd]

        return (self.__exec_cmd__(mkcmd, log) == 0)

    def make_menuconfig(self, flags=[], log=False):
        if self.__make_cmd__("menuconfig", flags, log):
            self.config =  os.path.join(self.out,'.config')

    def make_oldconfig(self, flags=[], log=False):
        if self.__make_cmd__("oldconfig", flags, log):
            self.config =  os.path.join(self.out,'.config')

    def make_defconfig(self, flags=[], log=False):
        if self.__make_cmd__("defconfig", flags, log):
            self.config =  os.path.join(self.out,'.config')

    def make_allyesconfig(self, flags=[], log=False):
        if self.__make_cmd__("allyesconfig", flags, log):
            self.config =  os.path.join(self.out,'.config')

    def make_allnoconfig(self, flags=[], log=False):
        if self.__make_cmd__("allnoconfig", flags, log):
            self.config =  os.path.join(self.out,'.config')

    def make_allmodconfig(self, flags=[], log=False):
        if self.__make_cmd__("allmodconfig", flags, log):
            self.config =  os.path.join(self.out,'.config')

    # return true on success
    def make_kernel(self, flags=[], log=False):
        if self.config is not None:
            self.make_oldconfig(flags, log)
        else:
            self.make_defconfig(flags, log)

        if self.use_efi_header:
            self.__update_config_efistub__()

        if self.use_initramfs:
            self.__update_config_initramfs__(self.rootfs_src)

        return self.__make_cmd__(flags=flags, log=log)

    # return true on success
    def make_mod_install(self, flags=[], modpath=None, log=False):
        if type(flags) is not list:
                raise Exception("Invalid make flags")
        if modpath is not None:
            if os.path.exists(os.path.expanduser(modpath)):
                flags.append("INSTALL_MOD_PATH=" + modpath)
            else:
                raise Exception("modpath does not exist")

        return self.__make_cmd__("modules_install", flags, log)

    def __str_build_params__(self):
        build_str = "Build Params :\n" + \
        "Arch : " + self.target_arch + "\n" + \
        "Rootfs : " + self.rootfs_src + "\n" + \
        "Out : " + self.out + "\n" + \
        "Threads : " + str(self.no_threads) + "\n" + \
        "Use EFI header : " + str(self.use_efi_header) + "\n" + \
        "Config FILE : " + self.config if self.config else "None" + "\n"

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
    parser.add_argument('--log', action='store_true', default=False, dest='use_log',
                        help='logs to file')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')
    args = parser.parse_args()

    print args

    kobj = BuildKernel(args.kernel_src)
    kobj.set_build_env(arch=args.arch, config=args.config.name if args.config else None, use_efi_header=args.use_efi_header,
                       rootfs=args.rootfs, out=args.out, threads=args.threads)
    kobj.update_config_options(update_config_list=["CONFIG_EFI_STUB=y"])
    #kobj.make_menuconfig(log=args.use_log)
    kobj.make_kernel(log=args.use_log)
