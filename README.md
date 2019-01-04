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
> sudo apt-get install virtualenv
> mkdir ~/pyenv
> virtualenv --python=python2.7 ~/pyenv
> source ~/pyenv/bin/activate
> pip install -r scripts/requirements.txt

## How to build

First set your environment by sourcing scripts/setenv.sh
> source ~/pyenv/bin/activate; source scripts/setenv.sh

You can build kdev image(rootfs + bzImage) by executing the build.py. Before you run this script you should make sure you have valid "kernel" project checked out out in the current directory.
> python build.py

Once you run this script, it will parse the target-recipes folder and will display the list of valid build targets and request user to select the build target. You can also skip this selection by setting the following environment variable.
> export SELECTED_TARGET_DIR=target-recipes/\<soc\>/\<board\>/

To get more info on various options of build.py,
> python build.py -h

    Usage: kdevimg [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...

    Options:
      -k, --kernel-src PATH   Kernel source
      -o, --out PATH
      --rootfs-src PATH
      -r, --reciepe-dir PATH
      --debug / --no-debug
      --help                  Show this message and exit.

    Commands:
      build-all      build all
      build-kernel   build only kernel
      build-rootfs   build only rootfs
      gen-image      Generate images
      udpate-rootfs  Update rootfs

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

## Testing kernel+rootfs on target device

To test the kernel on target device create a USB drive with two partitions one for bzImage.efi (boot) and another to host the rootfs (linux filesystem) using the fdisk utility

1. Connect USB drive to Linux host machine
2. Check mount node name (ex . /dev/sde )
    > dmesg | tail -20
3. Create partitions
    > fdisk /dev/sde
4. Choose option n to create new partition of a desired size
5. Choose option n again to create another partition
6. Save changes and exit fdisk utility
7. Format the first partition with vfat type
    > sudo mkfs.vfat -I -n BOOT /dev/sdx1 (here x to be changed with your device node number)
8. Format the second partion using ext4
    > sudo mkfs.ext4 -v -L ROOTFS /dev/sdx2
9. Copy bzImage to first partition
    > sudo mount /dev/sdx1 boot
    > sudo cp bzImage boot
10. Write Rootfs contents to second partition
    > dd if=rootfs.img.ext2 of=/dev/sdx2 bs=4096 conv=noerror

11. Unmount and eject the drive. Your drive is ready to be used as a EFI bootable disk . To boot from USB from EFI shell, execute a   startup.nsh with the boot command. A sample startup.nsh script content is shown below

        @echo -off
        mode 80 25
        ;clean the screen

        cls
        fs0:
        echo "Loading the kernel............"
        bzImage.efi root=/dev/sda2 rw console=ttyS2,115200n8 rootwait init=/sbin/init
        echo "........Done "
        echo "Kernel loading Completed"
        :END
