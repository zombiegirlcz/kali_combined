# Boot logika: proot-distro entrypointy, bootstrap a první procesy v kontejneru

Tento dokument popisuje, co se spouští při bootu kontejneru v `proot-distro`, jaké jsou entrypointy a kde jsou skripty, které to řídí.

---

## 1. Hlavní spouštěcí mechanismus

`proot-distro` **NEPOUŽÍVÁ** žádný univerzální `/init` jako Docker. Místo toho:
1. Launcher (`proot-distro login <name>`) sestaví argv pro `proot`
2. Spustí `proot` s argumenty: `--rootfs`, `--bind`, `--change-id`, atd.
3. `proot` jako první proces v kontejneru spustí **přímo shell/login** z `/etc/passwd`

Tedy:
```
proot-distro login parrot
    ↓
sestavení argv (bindy, env, change-id)
    ↓
exec proot --rootfs=... --bind=... /bin/sh -l
    ↓
/bin/sh jako PID 1 v kontejneru
```

---

## 2. Entrypointy — co se spustí jako první

### a) Normal-type kontejner (Kali, Parrot, Debian, Arch...)
- **Zdroj:** `/etc/passwd` v rootfs
- **Výchozí uživatel:** `root` (nebo `--user <uid>:<gid>`)
- **Výchozí shell:** `/bin/sh` (nebo shell z `/etc/passwd`)
- **Příkaz:**
  ```bash
  /bin/sh -l              # interaktivní login shell
  # nebo
  /bin/sh -c "<příkaz>"   # pokud zadáno `proot-distro run ... -- <příkaz>`
  ```

### b) Termux-type kontejner
- **Zdroj:** existence souboru `/data/data/com.termux/files/usr/bin/login` v rootfs
- **Příkaz:**
  ```bash
  /data/data/com.termux/files/usr/bin/login
  # nebo s -c pokud zadáno `-- <příkaz>`
  ```

---

## 3. Co se děje PŘED spuštěním prvního procesu (fixup/inicializace)

Při každém `proot-distro login` se provede:

### 3.1 Systémové bindy (přes `commands/login/proot_cmd.py`)
```
--bind=/dev
--bind=/proc
--bind=/sys
--bind=/dev/random:/dev/random
--bind=/proc/self/fd:/dev/fd          # pokud /dev/fd chybí
--bind=/proc/self/fd/0:/dev/stdin     # pokud /dev/stdin chybí
--bind=/proc/self/fd/1:/dev/stdout    # pokud /dev/stdout chybí
--bind=/proc/self/fd/2:/dev/stderr    # pokud /dev/stderr chybí
```

### 3.2 Fake sysdata (přes `commands/login/bindings.py` + `sysdata.py`)
```
--bind=<rootfs>/sysdata/loadavg:/proc/loadavg
--bind=<rootfs>/sysdata/stat:/proc/stat
--bind=<rootfs>/sysdata/uptime:/proc/uptime
--bind=<rootfs>/sysdata/vmstat:/proc/vmstat
--bind=<rootfs>/sysdata/sysctl_*:/proc/sys/*
```

### 3.3 Termux prefix binds (pouze normal-type, ne isolated/minimal)
```
--bind=/data/data/com.termux/files/usr          # Termux binárky
--bind=/data/data/com.termux/files/home         # Termux HOME
--bind=/data/data/com.termux/files/apps         # Termux apps
--bind=/data/data/com.termux/cache              # Termux cache
```

### 3.4 Další binds podle módu
- `--shared-home`: bind hostitelský HOME do guest HOME
- `--shared-tmp`: bind hostitelský /tmp
- `--shared-x11`: bind X11 unix socket
- `--bind <src>:<dst>`: uživatelem definované bindy

---

## 4. Skripty a soubory, které řídí boot

### 4.1 Samotný proot-distro — čistě Python, ŽÁDNÉ .sh

```
/data/data/com.termux/files/usr/lib/python3.14/site-packages/proot_distro/
├── cli.py                  # Entry point + dispatch
├── commands/
│   ├── install.py          # Instalace z Docker/URL
│   ├── install_local.py    # Instalace z lokálního tar/OCI
│   ├── login/
│   │   ├── __init__.py     # Hlavní login logika
│   │   ├── proot_cmd.py    # Sestavení proot argumentů (bindy)
│   │   ├── bindings.py     # Definice systémových bindů
│   │   ├── env.py          # Environment proměnné
│   │   └── passwd.py       # Resolve uživatele z /etc/passwd
│   └── run.py, backup.py, restore.py, ...
└── helpers/
    ├── docker/             # Docker/OCI pull + vrstvy
    ├── tar_extract.py      # Extrakce tar do rootfs
    └── rootfs.py           # Fixup /etc/resolv.conf, passwd, hosts
```

**Žádné `.sh` skripty v `proot_distro` balíčku nejsou.**

### 4.2 Launcher + binárky

| Soubor | Typ | Účel |
|--------|-----|------|
| `/data/data/com.termux/files/usr/bin/proot-distro` | Python wrapper | Spouští `proot_distro.cli:main()` |
| `/data/data/com.termux/files/usr/bin/proot` | C binárka | Uživatelský prostorový emulátor, který spustí kontejner |

### 4.3 Skripty v `kali_core_emulator` (Android app, ne proot-distro)

| Soubor | Účel |
|--------|------|
| `kali_core_emulator/app/src/main/assets/bootstrap.sh` | Bootstrap pro Android app |
| `kali_core_emulator/app/src/main/assets/nethunter_agent.py` | Agent v Pythonu |
| `kali_core_emulator/app/src/main/assets/shizuku/rish.sh` | Shizuku shell |
| `kali_core_emulator/magisk-modules/build.sh` | Magisk modul build |
| `kali_core_emulator/tools/modal_build.py` | Build skript |

---

## 5. Shrnutí

| Co | Kde je |
|----|--------|
| **Entrypoint v kontejneru** | `/bin/sh -l` (normal) nebo `/data/data/com.termux/files/usr/bin/login` (termux) |
| **Bootstrap rootfs** | Python: `commands/install.py`, `helpers/tar_extract.py`, `helpers/docker/*` |
| **Fixup rootfs** | Python: `helpers/rootfs.py` (resolv.conf, passwd, hosts) |
| **Sestavení proot argv** | Python: `commands/login/proot_cmd.py`, `bindings.py` |
| **Skripty `.sh`** | Žádné v samotném `proot-distro`; pouze v `kali_core_emulator` |

---

## 6. Proč není žádný `/init`?

Proot-distro je navržený pro **interaktivní použití** (shell sessions), ne pro dlouho běžící démona. Proto:
- Není potřeba `systemd` nebo jiného init systému
- Přímo se spustí shell jako první proces
- Všechny služby se spouštějí ručně nebo přes skripty v shellu

Pokud potřebuješ bootovat kontejner bez interaktivního shellu, použij:
```bash
proot-distro run <name> -- /usr/bin/topaz-mgmt start
```
