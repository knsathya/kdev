#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# kdev config parser
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
import logging
from configparser import ExtendedInterpolation
from configparser import ConfigParser, SafeConfigParser
from collections import Mapping, Sequence


logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(format=FORMAT)
logger.setLevel(logging.DEBUG)

__all__ = ("Namespace", "as_namespace")

class Namespace(dict, object):
    """A dict subclass that exposes its items as attributes.

    Warning: Namespace instances do not have direct access to the
    dict methods.

    """

    def __init__(self, obj={}):
        super(Namespace, self).__init__(obj)

    def __dir__(self):
        return tuple(self)

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__,
                super(Namespace, self).__repr__())

    def __getattribute__(self, name):
        try:
            return self[name]
        except KeyError:
            msg = "'%s' object has no attribute '%s'"
            raise AttributeError(msg % (type(self).__name__, name))

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        del self[name]

    #------------------------
    # "copy constructors"

    @classmethod
    def from_object(cls, obj, names=None):
        if names is None:
            names = dir(obj)
        ns = {name:getattr(obj, name) for name in names}
        return cls(ns)

    @classmethod
    def from_mapping(cls, ns, names=None):
        if names:
            ns = {name:ns[name] for name in names}
        return cls(ns)

    @classmethod
    def from_sequence(cls, seq, names=None):
        if names:
            seq = {name:val for name, val in seq if name in names}
        return cls(seq)

    #------------------------
    # static methods

    @staticmethod
    def hasattr(ns, name):
        try:
            object.__getattribute__(ns, name)
        except AttributeError:
            return False
        return True

    @staticmethod
    def getattr(ns, name):
        return object.__getattribute__(ns, name)

    @staticmethod
    def setattr(ns, name, value):
        return object.__setattr__(ns, name, value)

    @staticmethod
    def delattr(ns, name):
        return object.__delattr__(ns, name)

class BoardCfgParser(SafeConfigParser, object):
    min_sections = [
            "board_options",
            "build_options",
            "rootfs_options"
            ]

    optional_sections = [
            "bootimg_options"
            ]

    board_options = {
            "arch" : "get",
            "soc" : "get",
            "board" : "get",
            "version" : "get",
            "target_name" : "get"
            }


    build_options = {
            "build_efi" : "getboolean",
            "build_bootimg" : "getboolean",
            "build_yocto" : "getboolean",
            "cross_compile" : "get",
            "kernel_config" : "getfilename",
            "kernel_diffconfig" : "getfilename",
            "cmdline" : "getfilename"
            }

    rootfs_options = {
            "use_initramfs" : "getboolean",
            "rootfs_name" : "get",
            "support_adb" : "getboolean",
            "gen_cpioimage" : "getboolean",
            "gen_hdimage" : "getboolean"
            }

    bootimg_options = {
            "base" : "gethex",
            "kernel_offset" : "gethex",
            "ramdisk_offset" : "gethex",
            "second_offset" : "gethex",
            "os_version" : "get",
            "os_patch_level" : "get",
            "tags_offset" : "gethex",
            "pagesize" : "getint",
            "use_id" : "getboolean"
            }

    def __init__(self, *args, **kwargs):
        self.cfg_path = None
        super(self.__class__, self).__init__(*args, **kwargs)

    # get hex value
    def gethex(self, section, option):
        val = self.get(section, option)
        if val == '':
            return 0x00
        else:
            return int(val, 16)

    def getfilename(self, section, option):
        val = self.get(section, option)
        if val == '':
            return None
        if val[0] == '.':
            return os.path.abspath(os.path.join(self.cfg_path, val))
        else:
            return os.path.abspath(val)

    def __is_valid__(self, name, def_opts):
        options = set(self.options(name))
        defaults = set(def_opts)
        if not defaults.issubset(options):
            err = ', '.join(options-defaults)
            raise Exception("missing %s options %s" % (name, err))

    def __str_options__(self, section, options):
        out_str = section + ":\n"
        for name, attr in options.items():
            val = getattr(self, attr)(section, name)
            out_str += "\t" + name + " = " + str(val) + "\n"

        return out_str

    def __get_options__(self, section, options):
        res = {}
        for name, attr in options.items():
            res[name] = getattr(self, attr)(section, name)

        return Namespace(res)

    def get_board_options(self):
        return self.__get_options__("board_options",
                BoardCfgParser.board_options)

    def get_build_options(self):
        return self.__get_options__("build_options",
                BoardCfgParser.build_options)

    def get_rootfs_options(self):
        return self.__get_options__("rootfs_options",
                BoardCfgParser.rootfs_options)
       
    def get_bootimg_options(self):
        return self.__get_options__("bootimg_options",
                BoardCfgParser.bootimg_options)

    def str_board_options(self):
        return self.__str_options__("board_options",
                BoardCfgParser.board_options)

    def str_build_options(self):
        return self.__str_options__("build_options",
                BoardCfgParser.build_options)

    def str_rootfs_options(self):
        return self.__str_options__("rootfs_options",
                BoardCfgParser.rootfs_options)

    def str_bootimg_options(self):
        if self.getboolean("build_options", "build_bootimg"):
            return self.__str_options__("bootimg_options",
                    BoardCfgParser.bootimg_options)
        else:
            return "bootimg_options"

    def read(self, cfg):
        ret = []

        if type(cfg) is list:
            raise Exception("Multifile parsing disabled")

        ret = super(self.__class__, self).read(cfg)

        # check for min sections
        sections = self.sections()
        if not set(BoardCfgParser.min_sections).issubset(set(sections)):
            raise Exception("Missing section error")

        # check for board_options
        self.__is_valid__("board_options", BoardCfgParser.board_options.keys())

        # check for build_options
        self.__is_valid__("build_options", BoardCfgParser.build_options.keys())

        # check for rootfs_options
        self.__is_valid__("rootfs_options", BoardCfgParser.rootfs_options.keys())

        #check for bootimg options
        if self.getboolean("build_options", "build_bootimg"):
            self.__is_valid__("bootimg_options",
                    BoardCfgParser.bootimg_options.keys())

        self.cfg_path = os.path.dirname(os.path.realpath(cfg))

        return ret

class KdevBoardConfig(object):

    # board config init
    def __init__(self, cfg):
        logger.debug("init cfg %s", cfg)
        self.cfg = cfg

        # create a parser object
        self.parser = BoardCfgParser(os.environ,
                interpolation = ExtendedInterpolation())
        self.parser.read(cfg)

        self.board_options = self.parser.get_board_options()
        self.build_options = self.parser.get_build_options()
        self.rootfs_options = self.parser.get_rootfs_options()
        self.bootimg_options = self.parser.get_bootimg_options()

    def __str__(self):
        out_str = "\n"
        out_str += self.parser.str_board_options()
        out_str += self.parser.str_build_options()
        out_str += self.parser.str_rootfs_options()
        out_str += self.parser.str_bootimg_options()

        return out_str


if __name__ == "__main__":

    board_cfg = KdevBoardConfig("target-recipes/bxt/joule/board.cfg")

    print board_cfg
