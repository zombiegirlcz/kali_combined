# Vysvětlení struktury `proot-distro` — launcher, rootfs a bindování

Tento dokument shrnuje, jak je v aktuální verzi `proot-distro` uspořádaná struktura kontejneru, co jeho launcher dělá, co v rootfs hledá a co do něj binduje. Vychází z kódu ve verzi balíčku nainstalovaného v Termuxu (viz `proot_distro` pod `/data/data/com.termux/files/usr/lib/python3.14/site-packages/proot_distro/`).

---

## 1. Celková struktura úložiště

`proot-distro` ukládá vše pod běhovým adářem. V Termuxu je to:
- `/data/data/com.termux/files/usr/var/lib/proot-distro/`

Struktura:
```
proot-distro/
├── containers/          # Všechny nainstalované kontejnery
│   └── <název_kontejneru>/
│       ├── manifest.json   # Metadata kontejneru (distro, arch, env nastavení z image)
│       ├── rootfs/         # Samotný rootfs Linuxové distribuce (/bin, /etc, /usr atd.)
│       ├── sysdata/        # Falešné /proc a /sys soubory (kvůli omezením Androidu)
│       └── shm/            # Adresář pro /dev/shm (sdílená paměť mezi procesy v kontejneru)
├── cache/              # Cache stažených OCI image a vrstev
├── sessions/           # Registrace aktuálně běžících proot sessions (pro `ps` a `kill`)
└── locks/              # Zámky pro operace s kontejnery (zabraňuje současné instalaci a spuštění)
```

### Proč je struktura takto navržena?
- **Oddělení hostitele a guestu**: Celý rootfs je v izolovaném adáři, takže může běžet více kontejnerů současně bez konfliktů.
- **`sysdata` a `shm` jsou vedle `rootfs`, ne uvnitř něj**: To je bezpečnostní opatření. Pokud by byly uvnitř rootfs, guest (který má v non-isolated módu přístup k rootfs) by mohl přepsat symlinkem např. `/proc/loadavg` na hostitelský soubor, nebo `/dev/shm` na hostitelský adresář a uniknout z kontejneru. Když jsou vedle, guest nemá přímou cestu k jejich rodičovskému adáři.
- **`manifest.json`**: Umožňuje `proot-distro` vědět, co je za distribuci nainstalovanou, bez nutnosti číst obsah celého rootfs.

---

## 2. Jak funguje launcher

Samotný spustitelný soubour `/data/data/com.termux/files/usr/bin/proot-distro` je jen malý Python wrapper:
```python
#!/data/data/com.termux/files/usr/bin/python3.14
import sys
from proot_distro.cli import main
if __name__ == '__main__':
    sys.argv[0] = sys.argv[0].removesuffix('.exe')
    sys.exit(main())
```

Veškerá logika je v Python balíčku `proot_distro`. Při spuštění příkazu (nejčastěji `login` nebo `run`) se postupuje takto:
1. **Kontrola prostředí**: Ověří se, že nejedete uvnitř jiného `proot` (nested proot není podporované), že je nainstalovaný `proot` binárka.
2. **Validace kontejneru**: Ověří se že kontejner existuje, pomocí `O_NOFOLLOW` chůzi po adářích — guest nemůže podstrčit symlink na hostitelský adresář jako rootfs.
3. **Detekce typu kontejneru**: Rozpozná se zda je to:
   - `termux` typ: pokud v rootfs existuje soubor `/data/data/com.termux/files/usr/bin/login` (jedná se o Termux instalaci uvnitř kontejneru, sdílí stejný prefix jako hostitel)
   - `normal` typ: běžná Linuxová distribuce (Kali, Debian, Arch atd.)

---

## 3. Co `proot-distro` hledá v rootfs

Během instalace a spouštění se v rootfs hledají a upravují tyto věci:

### Při instalaci:
- `/etc/resolv.conf`: Nastaví se DNS servery (výchozí 8.8.8.8 a 8.8.4.4)
- `/etc/hosts`: Přidá se základní záznam pro localhost
- `/etc/passwd`, `/etc/group`, `/etc/shadow`: Upraví se UID/GID uživatele, aby odpovídaly hostitelskému uživateli (aby mohl přistupovat k souborům v kontejneru i na hostiteli)
- Ověří se, že `/etc` je adáář (ne symlink)

### Při spouštění:
- **Detekce architektury**: Čte se ELF hlavička binárek (`/usr/bin/bash`, `/bin/sh`, `/usr/bin/busybox` atd.) z rootfs, aby se vědělo zda je potřeba emulátor (QEMU) pro jinou architekturu.
- **Typ kontejneru**: Hledá se soubor `/data/data/com.termux/files/usr/bin/login` (pro Termux typ).
- **Uživatel**: Čte se `/etc/passwd` a `/etc/group` pro resolucí uživatele zadaného parametrem `--user` (výchozí je `root`).
- **Shell**: Ověří se, že zadaný shell (výchozí `/bin/sh`) v rootfs existuje.

---

## 4. Co `proot-distro` binduje do kontejneru

Seznam bindování se sestavuje dynamicky podle módu spuštění (výchozí, `--minimal`, `--isolated`):

### Základní bindování (vždy):
| Cíl v kontejneru | Zdroj na hostiteli | Účel |
|------------------|-------------------|------|
| `/dev` | Hostitelský `/dev` | Přístup k zařízením |
| `/proc` | Hostitelský `/proc` | Informace o systému a procesech |
| `/sys` | Hostitelský `/sys` | Informace o hardwaru |

### Pokud není mód `--minimal` ani `--isolated`:
#### Bezpečnostní / funkcionality:
| Cíl v kontejneru | Zdroj | Účel |
|------------------|-------|------|
| `/dev/random` | Hostitelský `/dev/urandom` | Generování náhodných čísel (Android nemá `/dev/random`) |
| `/dev/fd` | `/proc/self/fd` (pokud chybí) | Přístup k otevřeným deskriptorům |
| `/dev/stdin`, `/dev/stdout`, `/dev/stderr` | `/proc/self/fd/0/1/2` (pokud chybí) | Standardní vstup/výstup |
| `/proc/loadavg`, `/proc/stat`, `/proc/uptime`, `/proc/vmstat` | `containers/<jmeno>/sysdata/` | Falešné hodnoty, protože Android blokuje přímý přístup k těmto souborům (potřebné pro `top`, `htop` atd.) |
| `/proc/sys/*` | `containers/<jmeno>/sysdata/` | Falešné sysctl hodnoty (potřebné pro některé nástroje) |
| `/dev/shm` | `containers/<jmeno>/shm/` | Sdílená paměť mezi procesy (Android nemá funkční `/dev/shm`) |
| `/tmp` | Vytvoří se prázdný adáář v rootfs | Dočasné soubory pro guest |

#### Android systémové cesty (potřebné pro spouštění binárek a přístup k hardwaru):
| Cíl v kontejneru | Zdroj | Účel |
|------------------|-------|------|
| `/apex` | Hostitelský `/apex` | Android rozšíření jádra |
| `/odm` | Hostitelský `/odm` | Ovladače zařízení |
| `/product` | Hostitelský `/product` | Systémové produkty |
| `/system` | Hostitelský `/system` | Systémové binárky a knihovny Androidu |
| `/system_ext` | Hostitelský `/system_ext` | Rozšířené systémové komponenty |
| `/vendor` | Hostitelský `/vendor` | Vendor specifické soubory |
| `/linkerconfig/ld.config.txt` | Hostitelský soubor | Konfigurace Android linkéru |
| `/linkerconfig/com.android.art/ld.config.txt` | Hostitelský soubor | ART linker konfigurace |
| `/plat_property_contexts`, `/property_contexts` | Hostitelský soubor | SELinux kontexty vlastností |

#### Úložiště a Termux:
| Cíl v kontejneru | Zdroj | Účel |
|------------------|-------|------|
| `/storage`, `/storage/emulated/0` | Hostitelský adáář (pokud má aplikace povolení k úložišti) | Přístup k SD kartě a sdílenému úložišti |
| `/sdcard`, `/mnt/sdcard` | `/storage/emulated/0` | Zpětná kompatibilita s cestami k úložišti |
| `/data/app`, `/data/dalvik-cache` | Hostitelský adáář | Přístup k nainstalovaným aplikacím a Dalvik/ART cache |
| `/data/data/com.termux` (vše) | Hostitelský Termux adáář | Přístup k nainstalovaným Termux balíčkům a cache |
| `/data/data/com.termux/files/home` | Hostitelský `$HOME` | Přístup k domovskému adáři Termuxu |
| `/data/data/com.termux/files/usr` | Hostitelský Termux prefix | Spouštění hostitelských Termux nástrojů uvnitř kontejneru |

#### Volitelné bindování (parametry příkazu):
- `--shared-home`: Binduje hostitelský `$HOME` do guestova domovského adáře (pro uživatele root se binduje do `/root`)
- `--shared-tmp`: Binduje hostitelský `/tmp` do guestova `/tmp`
- `--shared-x11`: Binduje X11 unix socket pro grafické aplikace
- `--bind <zdroj>:<cíl>`: Uživatelem definované bindování libovolných cest

---

## 5. Proč je potřeba tolik bindování?

`proot` není plná virtualizace — je to uživatelský prostorový emulátor, který přepisuje systémová volání. Aby běžné Linuxové distribuce běžely na Androidu, potřebují přístup k:
- Systémovým binárkám a knihovnám Androidu (pro spouštění nativních bináře, přístup k hardwaru)
- `/dev` zařízením (pro vstup/výstup, generování náhodných čísel)
- Úložišti (aby bylo možné pracovat se soubory na SD kartě)
- Termux nástrojům (aby guest mohl používat nástroje nainstalované na hostiteli)

`sysdata` a `shm` jsou speciální případy — Android blokuje nebo omezuje přístup k `/proc` a `/sys` a nemá funkční sdílenou paměť, takže `proot-distro` poskytuje falešné, ale funkční náhrady.

---

## 6. Co se děje před finálním spuštěním

Po sestavení argumentů se ještě:
1. Nastaví environmentální proměnné: `PATH`, `HOME`, `USER`, `TERM`, `PULSE_SERVER` (pro zvuk), `MOZ_FAKE_NO_SANDBOX` (pro Firefox), Android systémové proměnné.
2. Nastaví `PROOT_L2S_DIR` na adáář v rootfs (pro funkci `--link2symlink` proot, která opravuje práva u symlinků).
3. Odstraní `LD_PRELOAD` (aby se nenačítaly hostitelské knihovny do guestu, což by způsobilo haváry).
4. Zaregistruje session pro příkaz `proot-distro ps`.
5. Přepne se do rootfs adáře a spustí `proot` se všemi argumenty.

### Ukázka finálního příkazu
Pokud chceš vidět přesný příkaz `proot`, který se spouští, použij:
```bash
proot-distro login parrot --get-proot-cmd
```

---

## 7. Bezpečnostní mechanismy

- **`O_NOFOLLOW` chůzí**: Při ověřování cest se nikdy ne následují symlinky, které by mohly odkazovat mimo rootfs nebo na hostitelský adresář.
- **Zámky (`locks`)**: Před instalací/spuštěním se získává zámek, aby se zabránilo souběžné modifikaci stejného kontejneru.
- **Omezení `--isolated` a `--minimal`**: Tyto módy omezují nebo eliminují hostitelské bindování, čímž zvyšují izolaci kontejneru.
- **Registrace session**: Umožňuje sledovat a ukončit běžící proot procesy.

---

## 8. Shrnutí

- **Struktura** je navržena tak, aby izolovala guest od hostitele, ale zároveň mu poskytla vše potřebné pro běh na Androidu.
- **Launcher** je jen wrapper, veškerá logika je v Python balíčku `proot_distro`.
- **Rootfs** se ověřuje, upravuje a čte bez následování symlinků, aby se předešlo únikům z kontejneru.
- **Bindování** je kombinace bezpečnostních právních, funkcionalit a přístupu k hostitelskému systému — bez něj by běžné nástroje nefungovaly.
