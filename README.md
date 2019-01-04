# kdev

Welcome to the kdev readme!

## Introduction

Kdev is a python based Linux kernel build script. You can use this script to build kernel and rootfs image for a supported target platform. It also has support for creating kernel image in both efi and bootimage format.

## Enviroment setup

#### Get kdev repo
    git clone --recursive https://github.com/knsathya/kdev.git
    cd kdev

#### Library requirements
    python > 2.7
    sudo apt-get install virtualenv
    mkdir ~/pyenv
    virtualenv --python=python2.7 ~/pyenv
    source ~/pyenv/bin/activate
    python setup.py install

## How to build

First set your environment by sourcing scripts/setenv.sh
> source ~/pyenv/bin/activate;

You can build kdev image(rootfs + bzImage) by executing the kdevimg. Before you run this script you should make sure you have valid "kernel" project checked out out in the kernel directory.
> kdevimg -k <KERNEL_DIR> -o <OUT_DIR> --rootfs-src <ROOTFS_SRC> -r <RECIPE_DIR> build-all

Once you run this script, it will parse the target-recipes folder and will display the list of valid build targets and request user to select the build target. You can also skip this selection by passing the recipe dir directly.
> kdevimg -r $RECIPE_DIR

To get more info on various options of build.py,
> kdevimg --help

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
* out/kernel             - obj directory for kernel.
* out/rootfs             - copy of rootfs.
* images/rootfs.img.ext2 - rootfs image in ext2 format.
* images/rootfs.img.ext2 - rootfs image in ext2 format.

## How to add a new target recipe

To create a new target recipe, create a separate target folder under $HOME/.kdev-recipes in the following format.

> mkdir $HOME/.kdev-recipes/<TARGET_DIR>/\*

Each target recipe should contain following files. If one of this file is missing, then it will not be considered as a valid target.

> board.json - config file to specify board params
> cmdline - kernel command line parameters
> kernel.config - Target kernel config
> rootfs.config - Target rootfs config

Following is the board.json format.

    {
        "recipe-name": "qemu-x86_64",
        "kernel-params": {
            "arch_name": "x86_64",
            "build": true,
            "use-initramfs": true,
            "compiler_options": {
                "CC": "",
                "cflags": []
            },
            "config-file": "kernel.config" //Name of the kernel config file.
        },
        "rootfs-params": {
            "hostname": "qemu", // Name of the host
            "rootfs-name": "busybox",
            "rootfs-config": "rootfs.config", // Name of the rootfs config file.
            "rootfs-branch": "master", // Name of the rootfs git branch.
            "build": true,
            "adb-gadget": {
                "enable": false
            },
            "zero-gadget": {
                "enable": false
            }
        },
        "out-image": {
            "enable": true,
            "rimage-type": "ext2", //rootfs image type
            "rimage-name": "bootimg.ext2", // rootfs image name
            ""kimage-name": "kerenl.img" // kernel image name
        },
        "bootimg-params": {
            "build": false
        }
    }

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
