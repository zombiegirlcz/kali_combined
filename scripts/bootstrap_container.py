#!/usr/bin/env python3
"""
Bootstrap skript pro proot-distro kontejner.

Tento skript provádí základní inicializaci rootfs po rozbalení:
- Nastavení DNS (/etc/resolv.conf)
- Nastavení /etc/hosts
- Úpravu /etc/passwd a /etc/group (UID/GID)
- Vytvoření sysdata/ a shm/ adresářů

Použití:
    python3 bootstrap_container.py <rootfs_path> <container_name> [--uid UID] [--gid GID]
"""

import argparse
import os
import sys

# Přidání cesty k proot_distro
sys.path.insert(0, "/data/data/com.termux/files/usr/lib/python3.14/site-packages")

from proot_distro.helpers.rootfs import (
    write_resolv_conf_at,
    write_hosts_at,
    register_android_ids_at,
)
from proot_distro.sysdata import setup_fake_sysdata
from proot_distro.shm import make_shm_dir, make_guest_tmp
from proot_distro import dirfd


def main():
    parser = argparse.ArgumentParser(description="Bootstrap proot-distro rootfs")
    parser.add_argument("rootfs", help="Cesta k rootfs adresáři")
    parser.add_argument("container_name", help="Název kontejneru")
    parser.add_argument("--uid", type=int, default=None, help="UID pro uživatele")
    parser.add_argument("--gid", type=int, default=None, help="GID pro skupinu")
    parser.add_argument("--dns-primary", default="8.8.8.8", help="Primární DNS")
    parser.add_argument("--dns-secondary", default="8.8.4.4", help="Sekundární DNS")
    parser.add_argument("--no-sysdata", action="store_true", help="Nevytvářet sysdata")
    parser.add_argument("--no-shm", action="store_true", help="Nevytvářet shm")
    
    args = parser.parse_args()
    
    rootfs = args.rootfs
    container_name = args.container_name
    
    if not os.path.isdir(rootfs):
        print(f"Chyba: {rootfs} není adresář", file=sys.stderr)
        sys.exit(1)
    
    # Otevření rootfs jako descriptor
    rootfs_fd = os.open(rootfs, os.O_RDONLY | os.O_DIRECTORY)
    
    try:
        print(f"[*] Bootstrap kontejneru {container_name}...")
        
        # 1. Nastavení DNS
        print("[*] Nastavuji /etc/resolv.conf...")
        write_resolv_conf_at(
            rootfs_fd,
            "etc",
            primary=args.dns_primary,
            secondary=args.dns_secondary,
        )
        
        # 2. Nastavení /etc/hosts
        print("[*] Nastavuji /etc/hosts...")
        write_hosts_at(rootfs_fd, "etc")
        
        # 3. Úprava UID/GID
        print("[*] Nastavuji UID/GID...")
        register_android_ids_at(rootfs_fd, "etc", uid=args.uid, gid=args.gid)
        
        # 4. Vytvoření sysdata
        if not args.no_sysdata:
            print("[*] Vytvářím sysdata...")
            setup_fake_sysdata(rootfs)
        
        # 5. Vytvoření shm a tmp
        if not args.no_shm:
            print("[*] Vytvářím /dev/shm a /tmp...")
            make_guest_tmp(rootfs, rootfs_fd=rootfs_fd)
            # shm je vedle rootfs, ne uvnitř
            container_dir = os.path.dirname(rootfs)
            make_shm_dir(rootfs, container_fd=os.open(container_dir, os.O_RDONLY | os.O_DIRECTORY))
        
        print("[+] Bootstrap dokončen")
        
    finally:
        os.close(rootfs_fd)


if __name__ == "__main__":
    main()
