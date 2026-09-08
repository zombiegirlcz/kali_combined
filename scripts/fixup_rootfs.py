#!/usr/bin/env python3
"""
Fixup skript pro rootfs po extrakci.

Provádí následující úpravy:
- Opravuje /etc/resolv.conf
- Opravuje /etc/hosts
- Opravuje /etc/passwd a /etc/group (Android UID/GID)
- Vytváří /tmp a /dev/shm
- Vytváří fake sysdata

Použití:
    python3 fixup_rootfs.py <rootfs_path> [--container-name NAME] [--uid UID] [--gid GID]
"""

import argparse
import os
import sys

sys.path.insert(0, "/data/data/com.termux/files/usr/lib/python3.14/site-packages")

from proot_distro.helpers.rootfs import (
    write_resolv_conf_at,
    write_hosts_at,
    register_android_ids_at,
)
from proot_distro.sysdata import setup_fake_sysdata
from proot_distro.shm import make_shm_dir, make_guest_tmp


def main():
    parser = argparse.ArgumentParser(description="Fixup rootfs po instalaci")
    parser.add_argument("rootfs", help="Cesta k rootfs adresáři")
    parser.add_argument("--container-name", required=True, help="Název kontejneru")
    parser.add_argument("--uid", type=int, default=None, help="UID")
    parser.add_argument("--gid", type=int, default=None, help="GID")
    parser.add_argument("--dns-primary", default="8.8.8.8")
    parser.add_argument("--dns-secondary", default="8.8.4.4")
    parser.add_argument("--no-sysdata", action="store_true")
    parser.add_argument("--no-shm", action="store_true")
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.rootfs):
        print(f"Chyba: {args.rootfs} není adresář", file=sys.stderr)
        sys.exit(1)
    
    rootfs_fd = os.open(args.rootfs, os.O_RDONLY | os.O_DIRECTORY)
    
    try:
        print(f"[*] Fixup rootfs pro {args.container_name}...")
        
        # 1. DNS
        print("[*] /etc/resolv.conf...")
        write_resolv_conf_at(
            rootfs_fd,
            "etc",
            primary=args.dns_primary,
            secondary=args.dns_secondary,
        )
        
        # 2. Hosts
        print("[*] /etc/hosts...")
        write_hosts_at(rootfs_fd, "etc")
        
        # 3. UID/GID
        print("[*] /etc/passwd + /etc/group...")
        register_android_ids_at(rootfs_fd, "etc", uid=args.uid, gid=args.gid)
        
        # 4. /tmp
        print("[*] /tmp...")
        make_guest_tmp(args.rootfs, rootfs_fd=rootfs_fd)
        
        # 5. sysdata
        if not args.no_sysdata:
            print("[*] sysdata...")
            setup_fake_sysdata(args.rootfs)
        
        # 6. shm
        if not args.no_shm:
            print("[*] /dev/shm...")
            container_dir = os.path.dirname(args.rootfs)
            parent_fd = os.open(container_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                make_shm_dir(args.rootfs, container_fd=parent_fd)
            finally:
                os.close(parent_fd)
        
        print("[+] Fixup dokončen")
        
    finally:
        os.close(rootfs_fd)


if __name__ == "__main__":
    main()
