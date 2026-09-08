# Proot-distro: bootstrap rootfs a entrypointy

Vysvětlení, jak se v `proot-distro` získá rootfs nového kontejneru a co se spustí jako první proces uvnitř něj.

---

## 1. Zdroje bootstrap rootfs

`proot-distro` podporuje 3 zdroje rootfs:

### a) Docker Hub / OCI registry
- Stáhne image přes `helpers/docker.py` (`pull_image`)
- Image se skládá z vrstev (layers), které jsou postupně aplikovány do `containers/<name>/rootfs/`
- Vrstvy se cachují pod `cache/oci_layers/` podle digestu (sha256)
- Pokud už je daná vrstva v cache, nebere se znovu
- Podporuje multi-arch manifesty (filtruje se podle `dist_arch`)

### b) Lokální soubor
- `install_from_local_file()` v `commands/install_local.py`
- Podporuje 2 formáty:
  1. **OCI image layout tar** — má `oci-layout`, `index.json`, `blobs/sha256/...`
     - Rozbaluje se jako Docker image (vrstvy, manifest, config)
     - Digesty se ověřují při rozbalování
  2. **Plain rootfs tar** — prostý tar s `/etc`, `/usr`, `/bin` atd.
     - Automaticky detekuje, kolik prvních komponent cesty je třeba odstranit (`strip count`), aby se adresáře rozbalily přímo do rootfs (např. pokud je tar zabalený jako `rootfs/etc`, `rootfs/usr`)

### c) HTTP/HTTPS URL
- Soubor se stáhne do cache (`download_file`) a zpracuje se stejně jako lokální soubor

---

## 2. Co se rootfs děje po rozbalení

Po rozbalení se ještě provede několik fixupů (přes `helpers/rootfs.py`):
- `/etc/resolv.conf` — nastaví DNS (výchozí 8.8.8.8, 8.8.4.4)
- `/etc/hosts` — přidá localhost
- `/etc/passwd`, `/etc/group` — upraví UID/GID na UID hostitele (aby fungovala práva na soubory)
- Vytvoří se `containers/<name>/sysdata/` (falešné /proc, /sys)
- Vytvoří se `containers/<name>/shm/` (pro /dev/shm)
- Zapiše se `manifest.json` s metadaty (architektura, image ref, Env z image)

---

## 3. Entrypointy — co se spustí jako první proces

**Proot-distro nepoužívá žádný univerzální `/init` jako Docker.** Místo toho přímo spustí shell/login proces:

### a) Termux-type kontejner
Pokud v rootfs existuje soubor:
```
/data/data/com.termux/files/usr/bin/login
```
(čili pokud rootfs je vlastně Termux instalace, která sdílí prefix s hostitelem)

Spustí se jako první proces:
```bash
/data/data/com.termux/files/usr/bin/login
```
 případně s `-c <příkaz>` pokud byl zadán `-- <příkaz>`

Tedy výchozí entrypoint = **hostitelský Termux `login`**, který se nachází přímo v rootfs.

### b) Normal-type kontejner (Kali, Debian, Arch, Parrot...)
Čte se `/etc/passwd` z rootfs, získá se uživatel (výchozí `root`), jeho domovský adresář a **shell** (výchozí `/bin/sh`).

Spustí se jako první proces:
```bash
/bin/sh -l          # pro interaktivní login shell
```
nebo pokud byl zadán `-- <příkaz>`:
```bash
/bin/sh -c "<příkaz>"
```

Pokud je v `/etc/passwd` jiný shell (např. `/bin/bash`), použije se ten.

---

## 4. Dodatečné inicializace při spuštění

Při každém `login` se ještě děje:

1. **Falešné sysdata** — `setup_fake_sysdata()` vytvoří/ověří `containers/<name>/sysdata/` a binduje falešné:
   - `/proc/loadavg`, `/proc/stat`, `/proc/uptime`, `/proc/vmstat`
   - `/proc/sys/*` (sysctl)

2. **Profile injection** — pro normal-type se do rootfs zapíše:
   ```
   <rootfs>/etc/profile.d/termux-profile.sh
   ```
   Tento skript se při každém spuštění shellu znovu načte (přes `/etc/profile`) a obnoví proměnné jako `PATH`, `MOZ_FAKE_NO_SANDBOX`, `PULSE_SERVER`, image Env atd., které by jinak při `su -` nebo re-loginu zmizely.

3. **Termux prefix bind** — pro normal-type se binduje:
   ```
   --bind=/data/data/com.termux/files/usr
   ```
   aby guest viděl hostitelské Termux nástroje.

---

## 5. Shrnutí

| Krok | Co se děje |
|------|-----------|
| **Instalace** | Stáhne/rozbalí rootfs do `containers/<name>/rootfs/` |
| **Fixup** | Upraví DNS, hosts, passwd/group, vytvoří sysdata+shm |
| **Manifest** | Zapíše `manifest.json` s metadaty |
| **Spuštění** | Rozpozná typ kontejneru |
| **Entrypoint (termux)** | `/data/data/com.termux/files/usr/bin/login` |
| **Entrypoint (normal)** | `/bin/sh -l` (nebo shell z `/etc/passwd`) |
| **Init při login** | Vytvoří fake sysdata, injectuje profile.d snippet |

Pokud tedy řešíš vlastní bootstrap nebo entrypoint pro Kali/Parrot v rámci `proot-distro`, tak **nemusíš řešit žádný `/init`** — prostě zajisti, že v rootfs je funkční `/bin/sh` a `/etc/passwd`, a `proot-distro login <name>` to spustí automaticky. Pro Termux typ pak musí být v rootfs přítomen Termux `login` binárka.
