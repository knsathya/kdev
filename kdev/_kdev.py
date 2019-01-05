# -*- coding: utf-8 -*-
#
# KdevBuild class
#
# Copyright (C) 2019 Sathya Kuppuswamy
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
import logging
import pkg_resources
from klibs import BuildKernel, is_valid_kernel, KernelConfig
from jsonparser import JSONParser
from mkrootfs import RootFS, supported_rootfs
from shutil import copy2

valid_str = lambda x: True if x is not None and isinstance(x, basestring) and len(x) > 0 else False

def get_recipe_name(recipedir, logger=None):
    recipe = JSONParser(pkg_resources.resource_filename('kdev', 'schemas/board-schema.json'),
                             os.path.join(recipedir, 'board.json'), extend_defaults=True,
                             os_env=True, logger=logger)
    recipecfg = recipe.get_cfg()

    return recipecfg["recipe-name"] if valid_str(recipecfg["recipe-name"]) else None

class KdevBuild(object):
    def __init__(self, ksrcdir, rsrcdir, recipedir, outdir, logger=None):
        self.logger = logger or logging.getLogger(__name__)

        self.ksrc = os.path.abspath(ksrcdir)
        self.kparams = None
        self.kobj = None

        self.rsrc = os.path.abspath(rsrcdir)
        self.rparams = None
        self.robj = None

        self.recipedir = os.path.abspath(recipedir)
        self.recipename = None
        self.bparams = None

        if not os.path.exists(self.ksrc):
            self.logger.error("Kernel Source dir %s does not exist", self.ksrc)
            raise AttributeError

        if not is_valid_kernel(self.ksrc, logger):
            return

        if not os.path.exists(self.recipedir):
            self.logger.error("Recipe dir %s does not exist", self.recipedir)
            raise AttributeError

        for file in ['board.json', 'kernel.config']:
            if not os.path.exists(os.path.join(self.recipedir, file)):
                self.logger.error("Missing %s file in recipe folder" % file)
                raise AttributeError

        self.recipename = get_recipe_name(recipedir)

        if self.recipename is None:
            self.logger.error("Invalid recipe name %s" % self.recipename)
            raise AttributeError

        self.kout = os.path.join(os.path.abspath(outdir), self.recipename, 'kernel')
        self.rout = os.path.join(os.path.abspath(outdir), self.recipename, 'rootfs')
        self.iout = os.path.join(os.path.abspath(outdir), self.recipename, 'images')

        self.recipe = JSONParser(pkg_resources.resource_filename('kdev', 'schemas/board-schema.json'),
                                 os.path.join(recipedir, 'board.json'), extend_defaults=True,
                                 os_env=True, logger=logger)
        self.recipecfg = self.recipe.get_cfg()

        for dirname in [self.rsrc, self.rout, self.kout, self.iout]:
            if not os.path.exists(dirname):
                self.logger.warning("dir %s does not exist, so creating it", dirname)
                os.makedirs(dirname)

        self.kparams = self.recipecfg["kernel-params"]
        self.rparams =  self.recipecfg["rootfs-params"]
        self.bparams = self.recipecfg["bootimg-params"]
        self.oparams = self.recipecfg["out-image"]

        self.robj = RootFS(self.rparams["rootfs-name"], self.rsrc, self.rout, self.logger)

        self.kobj = BuildKernel(src_dir=self.ksrc, out_dir=self.kout, arch=self.kparams["arch_name"],
                                cc=self.kparams["compiler_options"]["CC"],
                                cflags=self.kparams["compiler_options"]["cflags"],
                                logger=self.logger)

    def kernel_build(self):
        if not self.kparams["build"]:
            self.logger.warning("Kernel build option is not enabled")
            return False

        if self.kobj is None:
            self.logger.error("Invalid kernel build object")
            return False

        self.kobj.copy_newconfig(os.path.join(self.recipedir, self.kparams["config-file"]))

        cobj = KernelConfig(src=self.kobj.cfg, logger=self.logger)
        config_list = []
        config_list.append('CONFIG_BLK_DEV_INITRD=y')
        config_list.append('CONFIG_INITRAMFS_SOURCE=%s' % self.rout)
        config_list.append('CONFIG_INITRAMFS_ROOT_UID=0')
        config_list.append('CONFIG_INITRAMFS_ROOT_GID=0')
        cobj.merge_config(config_list)

        self.kobj.make_olddefconfig()

        ret, out, err = self.kobj.make_kernel()

        status = True if ret == 0 else False

        if not status:
            self.logger.error(err)
            self.logger.error(out)

        ret, out, err = self.kobj.make_modules_install(flags=["INSTALL_MOD_PATH=%s" % self.rout])

        status = True if ret == 0 else False

        if not status:
            self.logger.error(err)
            self.logger.error(out)

        return status

    def rootfs_build(self):
        if not self.rparams["build"]:
            self.logger.warning("Rootfs build option is not enabled")
            return False

        if self.robj is None:
            self.logger.error("Invalid rootfs object")
            return False

        self.robj.build(config=os.path.join(self.recipedir, self.rparams["rootfs-config"]),
                        branch=self.rparams["rootfs-branch"])

        return True

    def rootfs_update(self):
        if self.robj is None:
            self.logger.error("Invalid rootfs object")
            return False

        services = []

        gadget = self.rparams["adb-gadget"]
        if gadget["enable"]:
            services.append(('adb-gadget',
                             [gadget["manufacturer"],
                              gadget["product"],
                              gadget["vendorid"],
                              gadget["productid"]]))

        gadget = self.rparams["zero-gadget"]
        if gadget["enable"]:
            services.append(('zero-gadget', []))

        if len(services) > 0:
            self.robj.add_services(services)

        self.robj.set_hostname(self.rparams["hostname"])

        if os.path.exists(os.path.join(self.recipedir, 'rootfs-updates')):
            self.robj.update_rootfs(os.path.join(self.recipedir, 'rootfs-updates'), self.rout)

        return True

    def gen_image(self):
        if not self.oparams["enable"]:
            self.logger.warning("Generate image option is not enabled")
            return False

        if self.robj is None:
            self.logger.error("Invalid rootfs object")
            return False

        self.robj.gen_image(self.oparams["rimage-type"], os.path.join(self.iout, self.oparams["rimage-name"]))
        self.robj.gen_image("cpio", os.path.join(self.iout, self.oparams["initramfs-name"]))

        copy2(os.path.join(self.kout, 'arch', self.kparams["arch_name"], 'boot/bzImage'),
              os.path.join(self.iout, self.oparams["kimage-name"]))

        return True

    def build(self, kbuild=True, rbuild=True, rupdate=True, gen_image=True):
        self.logger.info("Building recipe %s", self.recipecfg["recipe-name"])
        status = True
        if rbuild:
            status = self.rootfs_build()
            if not status:
                self.logger.error("Rootfs build failed")
                return status

        if kbuild:
            status = self.kernel_build()
            if not status:
                self.logger.error("Kernel build failed")
                return status

        if rupdate:
            status = self.rootfs_update()
            if not status:
                self.logger.error("Rootfs update failed")
                return status

        if gen_image:
            status = self.gen_image()
            if not status:
                self.logger.error("Generate image failed")
                return status

        return status

