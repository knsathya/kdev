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

    def burn_drive(self, dev, ksize=20, rsize=100, force=False):
        self.logger.info("Burning %s device to %s", self.recipecfg["recipe-name"], dev)

        if not os.path.exists(dev):
            self.logger.error("Disk %s does not exist" % dev)
            return False

        if self.rparams["image-type"] not in ["ext2", "ext3", "ext4"]:
            self.logger.error("Rootfs image type %s does not support creating boot disk" % self.rparams["image-type"] )
            return False

        sh = PyShell(logger=self.logger)
        sh.update_shell()

        ret = sh.cmd("sudo parted %s print free | grep \"Disk %s\" | cut -d' ' -f3" % (dev, dev))
        if ret[0] != 0:
            self.logger.error("Getting disk size %s command failed" % dev)
            return False

        regex = re.compile(r'(\d+(?:\.\d+)?)\s*([kmgtp]?b)', re.IGNORECASE)

        order = ['b', 'kb', 'mb', 'gb', 'tb', 'pb']

        for value, unit in regex.findall(ret[1].strip()):
            size = int(float(value) * (1024 ** order.index(unit.lower())))

        if size < (1024 * 1024 * 1024 * 4):
            self.logger.error("Device size should be atleast 4GB")
            return False

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

        def format_size(min, max):
            return str(min) + '%' + ' ' + str(max) + '% '

        ret = sh.cmd("sudo parted %s mklabel msdos" % dev)
        if ret[0] != 0:
            self.logger.error("Creating label failed")
            self.logger.error(ret)
            return False

        ret = sh.cmd("sudo parted %s mkpart primary fat32 %s" % (dev, format_size(0, ksize)))
        if ret[0] != 0:
            self.logger.error("Creating kernel parition failed")
            self.logger.error(ret)
            return False

        ret = sh.cmd("sudo parted %s set 1 boot on" % (dev))
        if ret[0] != 0:
            self.logger.error("Setting boot parition flag failed")
            self.logger.error(ret)
            return False

        ret = sh.cmd("sudo parted %s set 1 esp on" % (dev))
        if ret[0] != 0:
            self.logger.error("Setting boot parition flag failed")
            self.logger.error(ret)
            return False

        ret = sh.cmd("sudo parted %s mkpart primary ext4 %s" % (dev, format_size(ksize, rsize)))
        if ret[0] != 0:
            self.logger.error("Creating rootfs parition failed")
            self.logger.error(ret)
            return False

        ret = sh.cmd("sudo fdisk -l %s | grep '^/dev' | cut -d' ' -f1" % (dev))

        if "%s1" % dev not in ret[1].split():
            self.logger.error("Missing %s1 device" % dev)
            self.logger.error(ret[1].split())
            return False

        if "%s2" % dev not in ret[1].split():
            self.logger.error("Missing %s2 device" % dev)
            self.logger.error(ret[1].split())
            return False

        ret = sh.cmd("sudo mkfs.fat -F 32 -n KERNEL -I %s1" % (dev))
        if ret[0] != 0:
            self.logger.error("Making kernel fs failed")
            self.logger.error(ret)
            return False

        ret = sh.cmd("sudo mkfs.ext4 -L ROOTFS %s2" % (dev))
        if ret[0] != 0:
            self.logger.error("Making rootfs fs failed")
            self.logger.error(ret)
            return False

        temp_dir = tempfile.mkdtemp()

        cmd_text = ''

        if os.path.exists(os.path.join(self.recipe_dir, 'cmdline.txt')):
            with open(os.path.join(self.recipe_dir, 'cmdline.txt')) as fobj:
                cmd_text = fobj.read()

        nshfile = tempfile.NamedTemporaryFile(mode='w+t')

        try:
            nshfile.write("@echo -off\n")
            nshfile.write("mode 80 25\n")
            nshfile.write(";clean the screen\n")
            nshfile.write("cls\n")
            nshfile.write("fs0:\n")
            nshfile.write('echo "============================================================="\n')
            nshfile.write('echo "This script will load the kernel"\n')
            nshfile.write('echo "============================================================="\n')
            nshfile.write("pause\n")
            nshfile.write('echo "Loading the kernel............"\n')
            nshfile.write("%s %s\n" % (self.kparams["image-name"], cmd_text.strip()))
            nshfile.write('echo "........Done "\n')
            nshfile.write('echo "Kernel loading Completed"\n')
            nshfile.write(':END\n')
            nshfile.seek(0)
            print nshfile.read()
        finally:
            sh.cmd("sudo mount -o loop,rw,sync %s1 %s" % (dev, temp_dir))
            sh.cmd("sudo grub-install --efi-directory %s --boot-directory /boot --target x86_64-efi --removable %s" %
                   (temp_dir, dev))
            #sh.cmd("sudo cp %s %s/%s" % (os.path.join(self.kout, 'vmlinux'), temp_dir, self.kparams["image-name"]))
            sh.cmd("sudo cp %s %s/%s" % (os.path.join(self.iout, self.kparams["image-name"]), temp_dir, self.kparams["image-name"]))
            sh.cmd("sudo chmod 777 %s" % os.path.join(self.iout, self.kparams["image-name"]))
            if os.path.exists(os.path.join(temp_dir, 'startup.nsh')):
                sh.cmd("sudo rm %s" % os.path.join(temp_dir, 'startup.nsh'))
            sh.cmd("sudo cp %s %s" % (nshfile.name, os.path.join(temp_dir, 'startup.nsh')))
            sh.cmd("sudo chmod 755 %s" % os.path.join(temp_dir, 'startup.nsh'))
            sh.cmd(("sudo umount %s" % temp_dir))
            nshfile.close()

        sh.cmd("sudo mount -o loop,rw,sync %s2 %s" % (dev, temp_dir))
        sh.cmd("sudo /usr/bin/rsync -a -D %s/ %s" % (self.robj.idir, temp_dir))
        sh.cmd(("sudo umount %s" % temp_dir))
        try:
            os.removedirs(temp_dir)
        except Exception as e:
            pass

        return True