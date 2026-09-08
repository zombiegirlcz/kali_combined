#!/usr/bin/env python3
"""
Entrypoint wrapper pro proot-distro kontejner.

Tento skript slouží jako výchozí entrypoint, který:
1. Načte environment proměnné z manifest.json
2. Aplikuje profile.d snippet pro Termux kompatibilitu
3. Spustí skutečný shell z /etc/passwd

Použití:
    python3 entrypoint_wrapper.py [<shell>] [-c <příkaz>] [--login]
"""

import argparse
import os
import sys
import json

sys.path.insert(0, "/data/data/com.termux/files/usr/lib/python3.14/site-packages")

from proot_distro.commands.login.env import read_manifest_env, inject_termux_profile
from proot_distro.commands.login.passwd import read_passwd_entry


def get_shell_from_passwd(rootfs="."):
    """Získá shell z /etc/passwd pro root uživatele."""
    try:
        entry = read_passwd_entry(rootfs, "root")
        if entry:
            parts = entry.split(":")
            if len(parts) >= 7:
                return parts[6] or "/bin/sh"
    except Exception:
        pass
    return "/bin/sh"


def load_manifest_env(container_name):
    """Načte Env z manifest.json."""
    try:
        from proot_distro.paths import container_image_config
        config = container_image_config(container_name)
        return config.get("Env", [])
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(description="Entrypoint wrapper")
    parser.add_argument("shell", nargs="?", default=None, help="Shell k spuštění")
    parser.add_argument("-c", "--command", help="Příkaz k vykonání")
    parser.add_argument("--login", action="store_true", help="Login shell")
    parser.add_argument("--container", required=True, help="Název kontejneru")
    parser.add_argument("--rootfs", default=".", help="Cesta k rootfs")
    parser.add_argument("--manifest-env", action="store_true", help="Načíst env z manifestu")
    
    args = parser.parse_args()
    
    # 1. Načtení shell
    shell = args.shell or get_shell_from_passwd(args.rootfs)
    print(f"[*] Entrypoint: {shell}")
    
    # 2. Inject profile.d pro Termux proměnné
    try:
        inject_termux_profile(args.rootfs, {}, rootfs_fd=os.open(args.rootfs, os.O_RDONLY | os.O_DIRECTORY))
    except Exception as e:
        print(f"[!] Nelze injectovat profile: {e}", file=sys.stderr)
    
    # 3. Sestavení příkazu
    if args.command:
        cmd = [shell, "-c", args.command]
    elif args.login:
        cmd = [shell, "-l"]
    else:
        cmd = [shell]
    
    print(f"[*] Spouštím: { .join(cmd)}")
    
    # 4. Exec
    try:
        os.execvp(cmd[0], cmd)
    except FileNotFoundError:
        print(f"Chyba: {cmd[0]} nenalezen", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
