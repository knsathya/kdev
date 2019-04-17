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
import re
import tempfile
from klibs import BuildKernel, is_valid_kernel, KernelConfig
from jsonparser import JSONParser
from mkrootfs import RootFS
from shutil import copy2
from pyshell import PyShell

valid_str = lambda x: True if x is not None and isinstance(x, basestring) and len(x) > 0 else False

def get_recipe_name(recipe_dir, logger=None):
    recipe = JSONParser(pkg_resources.resource_filename('kdev', 'schemas/board-schema.json'),
                             os.path.join(recipe_dir, 'board.json'), extend_defaults=True,
                             os_env=True, logger=logger)
    recipecfg = recipe.get_cfg()

    return recipecfg["recipe-name"] if valid_str(recipecfg["recipe-name"]) else None

class KdevBuild(object):
    def __init__(self, kernel_dir, rootfs_dir, recipe_dir, out_dir, logger=None):
        self.logger = logger or logging.getLogger(__name__)

        self.ksrc = os.path.abspath(kernel_dir)
        self.kparams = None
        self.kobj = None

        self.rsrc = os.path.abspath(rootfs_dir)
        self.rparams = None
        self.robj = None

        self.recipe_dir = os.path.abspath(recipe_dir)
        self.recipename = None
        self.bparams = None

        if not os.path.exists(self.ksrc):
            self.logger.error("Kernel Source dir %s does not exist", self.ksrc)
            raise AttributeError

        if not is_valid_kernel(self.ksrc, logger):
            return

        if not os.path.exists(self.recipe_dir):
            self.logger.error("Recipe dir %s does not exist", self.recipe_dir)
            raise AttributeError

        for file in ['board.json', 'kernel.config']:
            if not os.path.exists(os.path.join(self.recipe_dir, file)):
                self.logger.error("Missing %s file in recipe folder" % file)
                raise AttributeError

        self.recipename = get_recipe_name(recipe_dir)

        if self.recipename is None:
            self.logger.error("Invalid recipe name %s" % self.recipename)
            raise AttributeError

        self.kout = os.path.join(os.path.abspath(out_dir), self.recipename, 'obj/kernel')
        self.idir = os.path.join(os.path.abspath(out_dir), self.recipename, 'install/rootfs')
        self.rout = os.path.join(os.path.abspath(out_dir), self.recipename, 'obj/rootfs')
        self.iout = os.path.join(os.path.abspath(out_dir), self.recipename, 'images')

        self.recipe = JSONParser(pkg_resources.resource_filename('kdev', 'schemas/board-schema.json'),
                                 os.path.join(recipe_dir, 'board.json'), extend_defaults=True,
                                 os_env=True, logger=logger)
        self.recipecfg = self.recipe.get_cfg()

        for dirname in [self.rsrc, self.rout, self.idir, self.kout, self.iout]:
            if not os.path.exists(dirname):
                self.logger.warning("dir %s does not exist, so creating it", dirname)
                os.makedirs(dirname)

        self.kparams = self.recipecfg["kernel-params"]
        self.rparams =  self.recipecfg["rootfs-params"]
        self.iparams = self.recipecfg["initramfs-params"]
        self.bparams = self.recipecfg["bootimg-params"]
        self.dparams =  self.recipecfg["diskimg-params"]

        self.robj = RootFS(self.rparams["name"], self.rsrc, self.idir, self.rout, self.logger)
        self.iobj = RootFS(self.iparams["name"], self.rsrc, self.idir, self.rout, self.logger)

        self.kobj = BuildKernel(src_dir=self.ksrc, out_dir=self.kout, arch=self.kparams["arch-name"],
                                cc=self.kparams["compiler-options"]["CC"],
                                cflags=self.kparams["compiler-options"]["cflags"],
                                logger=self.logger)

    def initramfs_build(self):
        if not self.iparams["enable-build"]:
            self.logger.warning("Initramfs build option is not enabled")
            return False

        if self.iobj is None:
            self.logger.error("Invalid initramfs object")
            return False

        get_val = lambda x: self.rparams[x] if len(self.iparams[x]) > 0 else None

        if get_val("config-file") is not None:
            config =  os.path.join(self.recipe_dir, get_val("config-file"))
        else:
            config = None

        if get_val("diffconfig-file") is not None:
            diffconfig =  os.path.join(self.recipe_dir, get_val("diffconfig-file"))
        else:
            diffconfig = None

        self.iobj.build(self.iparams["source-url"], self.iparams["source-branch"],
                        config, diffconfig, self.iparams["arch-name"],
                        self.iparams["compiler-options"]["CC"],
                        ' '.join(self.iparams["compiler-options"]["cflags"]),
                        )
        return True

    def kernel_build(self):
        if not self.kparams["enable-build"]:
            self.logger.warning("Kernel build option is not enabled")
            return False

        if self.kobj is None:
            self.logger.error("Invalid kernel build object")
            return False

        self.kobj.copy_newconfig(os.path.join(self.recipe_dir, self.kparams["config-file"]))

        cobj = KernelConfig(src=self.kobj.cfg, logger=self.logger)
        config_list = []
        config_list.append('CONFIG_BLK_DEV_INITRD=y')
        config_list.append('CONFIG_INITRAMFS_SOURCE=%s' % self.iobj.idir)
        config_list.append('CONFIG_INITRAMFS_ROOT_UID=0')
        config_list.append('CONFIG_INITRAMFS_ROOT_GID=0')
        cobj.merge_config(config_list)

        self.kobj.make_olddefconfig()

        ret, out, err = self.kobj.make_kernel()

        status = True if ret == 0 else False

        if not status:
            self.logger.error(err)
            self.logger.error(out)

        ret, out, err = self.kobj.make_modules_install(flags=["INSTALL_MOD_PATH=%s" % self.robj.idir])

        status = True if ret == 0 else False

        if not status:
            self.logger.error(err)
            self.logger.error(out)

        return status

    def rootfs_build(self):
        if not self.rparams["enable-build"]:
            self.logger.warning("Rootfs build option is not enabled")
            return False

        if self.robj is None:
            self.logger.error("Invalid rootfs object")
            return False

        get_val = lambda x: self.rparams[x] if len(self.rparams[x]) > 0 else None

        if get_val("config-file") is not None:
            config =  os.path.join(self.recipe_dir, get_val("config-file"))
        else:
            config = None

        if get_val("diffconfig-file") is not None:
            diffconfig =  os.path.join(self.recipe_dir, get_val("diffconfig-file"))
        else:
            diffconfig = None

        self.robj.build(self.rparams["source-url"], self.rparams["source-branch"],
                        config, diffconfig, self.rparams["arch-name"],
                        self.rparams["compiler-options"]["CC"],
                        ' '.join(self.rparams["compiler-options"]["cflags"]),
                        )

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
        if gadget:
            services.append(('zero-gadget', []))

        if len(services) > 0:
            self.robj.add_services(services)

        self.robj.set_hostname(self.rparams["hostname"])

        update_dir = self.rparams["custom-update-dir"]

        if os.path.exists(os.path.join(self.recipe_dir, update_dir)):
            if self.rparams["custom-update"]:
                self.robj.update_rootfs(os.path.join(self.recipe_dir, update_dir), self.robj.idir)

        return True

    def initramfs_update(self):
        if self.iobj is None:
            self.logger.error("Invalid initramfs object")
            return False

        if not self.iparams["custom-update"]:
            self.logger.warning("Initramfs custom update option is not enabled")
            return False

        update_dir = self.iparams["custom-update-dir"]

        if os.path.exists(os.path.join(self.recipe_dir, update_dir)):
            if self.iparams["custom-update"]:
                self.iobj.update_rootfs(os.path.join(self.recipe_dir, update_dir), self.iobj.idir)

        return True

    def gen_image(self):
        if self.rparams["gen-image"]:
            if self.robj is None:
                self.logger.error("Invalid rootfs object")
                return False
            else:
                self.robj.gen_image(self.rparams["image-type"], os.path.join(self.iout, self.rparams["image-name"]))

        if self.iparams["gen-image"]:
            if self.iobj is None:
                self.logger.error("Invalid initramfs object")
                return False
            else:
                self.iobj.gen_image(self.iparams["image-type"], os.path.join(self.iout, self.iparams["image-name"]))

        if self.kparams["gen-image"]:
            copy2(os.path.join(self.kout, 'arch', self.kparams["arch-name"], 'boot/bzImage'),
                  os.path.join(self.iout, self.kparams["image-name"]))

        return True

    def build(self, kbuild=False, rbuild=False, ibuild=False, rupdate=False, iupdate=False, gen_image=False):
        self.logger.info("Building recipe %s", self.recipecfg["recipe-name"])
        status = True
        if rbuild:
            status = self.rootfs_build()
            if not status:
                self.logger.error("Rootfs build failed")
                return status

        if ibuild:
            status = self.initramfs_build()
            if not status:
                self.logger.error("Initramfs build failed")
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

        if iupdate:
            status = self.initramfs_update()
            if not status:
                self.logger.error("Initramfs update failed")
                return status

        if gen_image:
            status = self.gen_image()
            if not status:
                self.logger.error("Generate image failed")
                return status

        return status

    def burn_drive(self, dev=None, force=False):

        self.logger.info("Burning %s device to %s", self.recipecfg["recipe-name"], dev)

        if not self.dparams:
            self.logger.error("Invalid dparams")
            return False

        if dev is None:
            dev = self.dparams["disk-name"]

        if not self.dparams["gen-image"]:
            self.logger.warning("Generate disk image is disabled")
            return False

        sh = PyShell(logger=self.logger)

        sh.update_shell()

        if dev is not None:
            sh.cmd("rm -fr %s" %  dev)
            self.logger.warning("Creating device %s" % dev)
            sh.cmd("dd if=/dev/zero of=%s bs=1 count=0 seek=%dM" % (self.dparams["disk-name"], self.dparams["disk-size"]))

        ret = sh.cmd("sudo parted %s print free | grep \"Disk %s\" | cut -d' ' -f3" % (dev, dev))
        if ret[0] != 0:
            self.logger.error("Getting disk size %s command failed" % dev)
            return False

        regex = re.compile(r'(\d+(?:\.\d+)?)\s*([kmgtp]?b)', re.IGNORECASE)

        order = ['b', 'kb', 'mb', 'gb', 'tb', 'pb']

        for value, unit in regex.findall(ret[1].strip()):
            size = int(float(value) * (1024 ** order.index(unit.lower())))

        if size < (1024 * 1024 * 100 ):
            self.logger.warn("Device size should be atleast 100MB")

        self.logger.info("Device size is %d" % size)

        if force is False:
            raw_input("Proceeding further will wipe all data in %s, press enter to continue" % dev)

        ret = sh.cmd("sudo fdisk -l %s | grep '^/dev' | cut -d' ' -f1" % (dev))
        for part in ret[1].split():
            ret = sh.cmd("mount | grep %s" % part)
            if len(ret[1].strip()) == 0:
                self.logger.info("%s partition is not mounted" % part)
            else:
                ret = sh.cmd(("sudo umount %s" % part))
                if ret[0] != 0 and ret[0] != 32:
                    self.logger.error(ret)
                    return False
                if ret[0] == 32:
                    self.logger.warn(ret[1])

        sh.cmd("sudo wipefs -a %s" % (dev))

        ret = sh.cmd('echo -e "g\nw" | fdisk %s' % dev)
        if ret[0] != 0:
            self.logger.error("Creating label failed")
            self.logger.error(ret)
            return False

        part_index = 1

        def create_loopdev():
            ret = sh.cmd("sudo losetup -fP %s" % (dev))
            if ret[0] != 0:
                self.logger.error("losetup partition failed")
                self.logger.error(ret)
                return False

            ret = sh.cmd("losetup -a | grep %s | cut -d':' -f1" % (dev))
            if ret[0] != 0:
                self.logger.error("losetup grep device failed")
                self.logger.error(ret)
                return False

            if ret[1].split() <  1:
                self.logger.error("losetup grep device not found in list")
                return False

            return ret[1].split()[0]

        temp_dir = tempfile.mkdtemp()

        for part in self.dparams["partitions"]:
            ret = sh.cmd('echo -e "n\n%d\n\n+%dM\nw" | fdisk %s' % (part_index, part["part-size"], dev))
            if ret[0] != 0:
                self.logger.error("Creating parition failed")
                self.logger.error(ret)
                return False

            if part_index > 1:
                ret = sh.cmd('echo -e "t\n%d\n%d\nw" | fdisk %s' % (part_index, part["part-type"], dev))
            else:
                ret = sh.cmd('echo -e "t\n%d\nw" | fdisk %s' % (part["part-type"], dev))

            if ret[0] != 0:
                self.logger.error("Setting parition type failed")
                self.logger.error(ret)
                return False

            ldev = create_loopdev()

            if "ext" in part["part-fstype"]:
                ret = sh.cmd("sudo mkfs.%s -L %s %sp%d" % (part["part-fstype"], part["part-name"], ldev, part_index))
            elif part["part-fstype"] == "fat32":
                ret = sh.cmd("sudo mkfs.fat -F 32 -n %s -I %sp%d" % (part["part-name"], ldev, part_index))
            elif part["part-fstype"] == "fat16":
                ret = sh.cmd("sudo mkfs.fat -F 16 -n %s -I %sp%d" % (part["part-name"], ldev, part_index))

            if ret[0] != 0:
                self.logger.error("format partition %s failed" % part["part-name"])
                self.logger.error(ret)
                return False

            sh.cmd("sudo mount -o loop,rw,sync %sp%d %s" % (ldev, part_index, temp_dir))

            def get_update_dir(root, dir):
                if root is None and len(dir) > 0:
                    if dir.startswith("/"):
                        return dir
                    elif dir.startswith("."):
                        return os.path.join(os.getcwd(), dir)
                else:
                    return os.path.join(root, dir)

            if part["part-update"]:
                for uparams in part["updates"]:
                    sdir = get_update_dir(self.recipe_dir, uparams["update-sdir"])
                    ddir = get_update_dir(temp_dir, uparams["update-ddir"])
                    kdir = get_update_dir(temp_dir, uparams["kernel-ddir"])
                    if uparams["sync-kernel"]:
                        sh.cmd("sudo cp %s %s/%s" % (os.path.join(self.iout, self.kparams["image-name"]),
                                                     kdir, self.kparams["image-name"]))
                    if uparams["sync-rootfs"]:
                        self.robj.install_rootfs(temp_dir)
                        #sh.cmd("sudo /usr/bin/rsync -aDzv %s/ %s" % (self.robj.idir, temp_dir))

                    if os.path.isfile(sdir):
                        self.cmd("sudo cp %s %s" % (sdir, ddir))
                    else:
                        if os.path.exists(sdir):
                            sh.cmd("sudo /usr/bin/rsync -azDv %s/ %s" % (sdir, ddir))
                        else:
                            self.logger.error("Source dir %s does not exist" % sdir)

            if part["install-grub"]:
                sh.cmd(
                    "sudo grub-install --efi-directory %s --boot-directory /boot --target x86_64-efi --removable %sp%d" %
                    (temp_dir, ldev, part_index))

            sh.cmd(("sudo umount %s" % temp_dir))

            sh.cmd("sudo losetup -d %s" % (ldev))

            part_index = part_index + 1

        try:
            os.removedirs(temp_dir)
        except Exception as e:
            pass

        if self.dparams["gen-craff-image"]:
            sh.cmd("craff %s -o %s" % (dev, self.dparams["craff-image-name"]))

        return True
