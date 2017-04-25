# kdev

Welcome to the kdev readme!

## Introduction

Kdev is a python based Linux kernel build script. You can use this script to build kernel and rootfs image for a supported target platform. It also has support for creating kernel image in both efi and bootimage format.

## Enviroment setup

#### Get kdev repo
> git clone --recursive https://github.com/knsathya/kdev.git  
> cd kdev   
> ln -s [path to your kernel] kernel  

#### Library requirements
> python > 2.7    
> pip install -r scripts/requirements.txt  

## How to build

First set your environment by sourcing scripts/setenv.sh  
> source scripts/setenv.sh

You can build kdev image(rootfs + bzImage) by executing the build.py. Before you run this script you should make sure you have valid "kernel" project checked out out in the current directory.
> python build.py

Once you run this script, it will parse the target-recipes folder and will display the list of valid build targets and request user to select the build target. You can also skip this selection by setting the following environment variable.
> export SELECTED_TARGET_DIR=target-recipes/\<soc\>/\<board\>/

To get more info on various options of build.py,
> python build.py -h

    usage: build.py [-h] [-k KERNEL_DIR] [-r ROOTFS_DIR] [-o OUT_DIR]
                    [-t RECIPE_DIR] [--build-efi] [--skip-build-rootfs] [--log]
                    [-v]

    kdev build app

    optional arguments:
      -h, --help            show this help message and exit
      -k KERNEL_DIR, --kernel-dir KERNEL_DIR
                            kernel source directory
      -r ROOTFS_DIR, --rootfs-dir ROOTFS_DIR
                            rootfs directory
      -o OUT_DIR, --out-dir OUT_DIR
                            out directory
      -t RECIPE_DIR, --target-recipe RECIPE_DIR
                            target recipe directory
      --build-efi           Build efi image
      --skip-build-rootfs   skip building rootfs
      --log                 logs to file
      -v, --version         show program's version number and exit

After successfully running this script, it will generate the kdev images in the "out" folder. For example, for bxt_joule_pr0, you can find images under,    
> out/bxt_joule_pr0/images  

Following are the list of out dir content.  
* images/bzImage.efi     - kernel image with EFI stub.    
* kernel-obj      - obj directory for kernel.  
* rootfs          - copy of rootfs.  
* images/rootfs.img      - cpio.gz format of rootfs image.  
* images/rootfs.img.ext2 - rootfs image in ext2 format.   

## How to add a new target recipe

To create a new target recipe, create a separate target folder under "target-recipes" in the following format.

> mkdir target-recipes/\<soc\>/\<board\>

Each target recipe should contain following files. If one of this file is missing, then it will not be considered as a valid target.
  
> board.cfg - config file to specify board params  
> cmdline - kernel command line parameters  
> kernel.config - Target kernel config

Following is the board.cfg format.  

    [board_options]
    arch = x86_64
    soc = bxt 
    board = joule
    version = pr0 
    target_name = ${soc}_${board}_${version}

    [build_options]
    build_efi = true
    build_bootimg = true
    build_yocto = true
    kernel_config = ./kernel.config
    kernel_diffconfig =
    cmdline = ./cmdline

    [rootfs_options]
    use_initramfs = false
    rootfs_name = busybox
    gen_cpioimage = true
    gen_hdimage = true

    [bootimg_options]
    base = 0x10000000
    kernel_offset = 0x00008000
    ramdisk_offset = 0x01000000
    second_offset =
    os_version = "v1.0"
    os_patch_level = "1" 
    tags_offset =
    pagesize = 4096
    use_id = false

