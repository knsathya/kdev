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
logger.setLevel(logging.DEBUG)

@click.group(chain=True)
@click.option('--kernel-src', '-k', type=click.Path(), default=os.path.join(os.getcwd(), 'kernel'), help='Kernel source')
@click.option('--out', '-o', type=click.Path(), default=os.path.join(os.getcwd(), 'out'))
@click.option('--rootfs-src', type=click.Path(), default=os.path.join(os.getcwd(), 'rootfs'))
@click.option('--reciepe-dir', '-r', type=click.Path(), default=None)
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx, kernel_src, out, rootfs_src, reciepe_dir, debug):
    ctx.obj = {}
    ctx.obj['KSRC'] = kernel_src
    ctx.obj['OUT'] = out
    ctx.obj['ROOTFS_SRC'] = rootfs_src
    ctx.obj['RECIPE_DIR'] = reciepe_dir
    ctx.obj['DEBUG'] = debug
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
        config_list = recursive_glob(pkg_resources.resource_filename('kdev', 'recipes'), 'board.json')
        if os.path.exists(os.path.join(os.path.expanduser("~"), '.kdev-recipes')):
            config_list +=  recursive_glob(os.path.join(os.path.expanduser("~"), '.kdev-recipes'), 'board.json')
        for config in config_list:
            recipe_list.append((get_recipe_name(os.path.dirname(config), logger), os.path.dirname(config)))

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

    ctx.obj['OBJ'] = KdevBuild(ksrcdir=ctx.obj['KSRC'], rsrcdir=ctx.obj['ROOTFS_SRC'], recipedir=ctx.obj['RECIPE_DIR'],
                               outdir=ctx.obj['OUT'], logger=logger)

@cli.command('build-kernel', short_help='build only kernel')
@click.pass_context
def build_kernel(ctx):
    click.echo('Building kernel for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(kbuild=True, rbuild=False, rupdate=False, gen_image=False)

@cli.command('build-rootfs', short_help='build only rootfs')
@click.pass_context
def build_rootfs(ctx):
    click.echo('Building rootfs for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(kbuild=False, rbuild=True, rupdate=False, gen_image=False)

@cli.command('udpate-rootfs', short_help='Update rootfs')
@click.pass_context
def build_rootfs(ctx):
    click.echo('Updating rootfs for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(kbuild=False, rbuild=False, rupdate=True, gen_image=False)

@cli.command('gen-image', short_help='Generate images')
@click.pass_context
def gen_image(ctx):
    click.echo('Generating image for recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(kbuild=False, rbuild=False, rupdate=False, gen_image=True)

@cli.command('build-all', short_help='build all')
@click.pass_context
def gen_image(ctx):
    click.echo('Building recipe %s' % (ctx.obj['OBJ'].recipename))
    ctx.obj['OBJ'].build(kbuild=True, rbuild=True, rupdate=True, gen_image=True)