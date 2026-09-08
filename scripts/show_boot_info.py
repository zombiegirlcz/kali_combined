#!/usr/bin/env python3
"""
Zobrazení boot/entrypoint informací o proot-distro kontejneru.

Zobrazí:
- Typ kontejneru (termux vs normal)
- Entrypoint co se spustí
- Seznam bindů
- Environment proměnné
- Architekturu

Použití:
    python3 show_boot_info.py <container_name>
"""

import sys
import os

sys.path.insert(0, "/data/data/com.termux/files/usr/lib/python3.14/site-packages")

from proot_distro.constants import TERMUX_PREFIX, TERMUX_HOME, IS_TERMUX, PROGRAM_NAME
from proot_distro.paths import container_rootfs, container_image_config
from proot_distro.commands.login import _detect_dist_type, _resolve_login_user
from proot_distro.commands.login.env import read_manifest_env, image_env_pairs
from proot_distro.commands.login.bindings import storage_bindings, system_bindings
from proot_distro.arch import detect_installed_arch, get_device_cpu_arch


def main():
    if len(sys.argv) < 2:
        print("Použití: python3 show_boot_info.py <container_name>")
        sys.exit(1)
    
    container_name = sys.argv[1]
    rootfs = container_rootfs(container_name)
    
    if not os.path.isdir(rootfs):
        print(f"Chyba: Kontejner {container_name} nenalezen ({rootfs})")
        sys.exit(1)
    
    print(f"{=*60}")
    print(f"Kontejner: {container_name}")
    print(f"Rootfs: {rootfs}")
    print(f"{=*60}")
    
    # 1. Typ kontejneru
    dist_type = _detect_dist_type(rootfs)
    print(f"\nTyp: {dist_type}")
    
    # 2. Architektura
    try:
        arch = detect_installed_arch(container_name)
        device_arch = get_device_cpu_arch()
        print(f"Architektura: {arch} (zařízení: {device_arch})")
    except Exception as e:
        print(f"Architektura: nelze detekovat ({e})")
    
    # 3. Entrypoint
    if dist_type == "termux":
        entrypoint = f"{TERMUX_PREFIX}/bin/login"
    else:
        try:
            user = _resolve_login_user(rootfs, container_name, "root")
            entrypoint = f"{user[shell]} -l (jako {user[name]} uid={user[uid]} gid={user[gid]})"
        except Exception:
            entrypoint = "/bin/sh -l (root)"
    print(f"Entrypoint: {entrypoint}")
    
    # 4. Image Env
    try:
        env_entries = read_manifest_env(container_name)
        if env_entries:
            print(f"\nImage Env ({len(env_entries)}):")
            for e in env_entries[:10]:
                print(f"  {e}")
    except Exception:
        pass
    
    # 5. Binds
    print(f"\nBinds:")
    binds = ["--bind=/dev", "--bind=/proc", "--bind=/sys"]
    binds += storage_bindings()
    binds += system_bindings()
    
    for b in binds[:15]:
        print(f"  {b}")
    if len(binds) > 15:
        print(f"  ... a {len(binds)-15} dalších")
    
    # 6. Manifest
    try:
        config = container_image_config(container_name)
        print(f"\nManifest:")
        print(f"  Arch: {config.get(architecture, N/A)}")
        print(f"  OS: {config.get(os, N/A)}")
        print(f"  Cmd: {config.get(Cmd, [])}")
        print(f"  Entrypoint: {config.get(Entrypoint, [])}")
    except Exception as e:
        print(f"\nManifest: nelze načíst ({e})")
    
    print(f"\n{=*60}")


if __name__ == "__main__":
    main()
