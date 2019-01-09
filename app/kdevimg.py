# -*- coding: utf-8 -*-
#
# kdevimg cli application
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
import click
import logging
from kdev import KdevBuild, get_recipe_name
import pkg_resources
import fnmatch

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(message)s')
logger.setLevel(logging.INFO)

@click.group(chain=True)
@click.option('--kernel-src', '-k', type=click.Path(), default=os.path.join(os.getcwd(), 'kernel'), help='Kernel source')
@click.option('--out', '-o', type=click.Path(), default=os.path.join(os.getcwd(), 'out'), help='Out directory')
@click.option('--rootfs-src', type=click.Path(), default=os.path.join(os.getcwd(), 'rootfs'), help='Rootfs source')
@click.option('--recipe-dir', '-r', type=click.Path(), default=None, help='Recipe Directory')
@click.option('--recipe-root', type=click.Path(), default=(), multiple=True, help='Additional recipe root')
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx, kernel_src, out, rootfs_src, recipe_dir, recipe_root, debug):
    ctx.obj = {}
    ctx.obj['KSRC'] = kernel_src
    ctx.obj['OUT'] = out
    ctx.obj['ROOTFS_SRC'] = rootfs_src
    ctx.obj['RECIPE_DIR'] = recipe_dir
    ctx.obj['RECIPE_ROOT'] = list(recipe_root)
    ctx.obj['DEBUG'] = debug

    ctx.obj['RECIPE_ROOT'].append(os.path.join(os.path.expanduser("~"), '.kdev-recipes'))
    ctx.obj['RECIPE_ROOT'].append(pkg_resources.resource_filename('kdev', 'recipes'))

    if ctx.obj['DEBUG']:
        logger.level = logging.DEBUG

    def recursive_glob(treeroot, pattern):
        results = []
        logger.info("Root: %s Pattern: %s", treeroot, pattern)
        for base, dirs, files in os.walk(treeroot):
            goodfiles = fnmatch.filter(files, pattern)
            results.extend(os.path.join(base, f) for f in goodfiles)
        return results

    if ctx.obj['RECIPE_DIR'] is None:
        recipe_list = []
        config_list = []

        for root in ctx.obj['RECIPE_ROOT']:
            if os.path.exists(root):
                config_list += recursive_glob(root, 'board.json')

        config_list = reduce(lambda l, x: l if x in l else l + [x], config_list, [])

        for config in config_list:
            recipe_list.append((get_recipe_name(os.path.dirname(config), logger), os.path.dirname(config)))

        recipe_list = reduce(lambda l, x: l if x[0] in [i[0] for i in l] else l + [x], recipe_list, [])

        if len(recipe_list) > 0:
            print("select one of the following recipe")
            for index, recipe in enumerate(recipe_list):
                print("%d: %s" %(index, recipe[0]))
            index = int(raw_input("Enter the index number:"))

            if index > len(recipe_list):
                logger.error("Invalid index %d" % index)
                raise IndexError

            ctx.obj['RECIPE_DIR'] = recipe_list[index][1]

    if ctx.obj['RECIPE_DIR'] is None:
        logger.error("No valid recipe found")
        raise AttributeError

    ctx.obj['OBJ'] = KdevBuild(kernel_dir=ctx.obj['KSRC'], rootfs_dir=ctx.obj['ROOTFS_SRC'], recipe_dir=ctx.obj['RECIPE_DIR'],
                               out_dir=ctx.obj['OUT'], logger=logger)

@cli.command('build-kernel', short_help='build only kernel')
@click.pass_context
def build_kernel(ctx):
    click.echo('Building kernel for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(kbuild=True)

@cli.command('build-rootfs', short_help='build only rootfs')
@click.pass_context
def build_rootfs(ctx):
    click.echo('Building rootfs for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(rbuild=True)

@cli.command('update-rootfs', short_help='Update rootfs')
@click.pass_context
def update_rootfs(ctx):
    click.echo('Updating rootfs for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(rupdate=True)

@cli.command('build-initramfs', short_help='build only initramfs')
@click.pass_context
def build_initramfs(ctx):
    click.echo('Building initramfs for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(ibuild=True)

@cli.command('update-initramfs', short_help='Update initramfs')
@click.pass_context
def update_initramfs(ctx):
    click.echo('Updating initramfs for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(iupdate=True)

@cli.command('gen-image', short_help='Generate images')
@click.pass_context
def gen_image(ctx):
    click.echo('Generating image for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(gen_image=True)

@cli.command('burn-drive', short_help='Burn images to a device')
@click.option('--dev', type=str, default=None, help='Device node /dev/<node>')
@click.option('--kernel-partsize', type=int, default=20, help='kernel partition size')
@click.option('--root-partsize', type=int, default=100, help='kernel partition size')
@click.option('--force/--no-force', default=False)
@click.pass_context
def burn_drive(ctx, dev, kernel_partsize, root_partsize, force):
    click.echo('Generating image for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].burn_drive(dev, kernel_partsize, root_partsize, force)

@cli.command('build-all', short_help='build all')
@click.pass_context
def gen_image(ctx):
    click.echo('Building recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(kbuild=True, rbuild=True, ibuild=True, rupdate=True, iupdate=True, gen_image=True)
