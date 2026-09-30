# Kompletni bezpecnostni a kvalitativni audit — kali_combined

Datum: 2026-09-30. Repozitare: kali_ai_assistant, kali_core_emulator, kali_GUI.

## Exekutivni shrnuti

Na základě auditu tří repozitářů (kali_ai_assistant, kali_core_emulator, kali_GUI) má **nejvyšší rizikový profil kali_core_emulator** – kombinuje čtyři kritické nálezy (commitnutý signing keystore, prolomenou autentizaci AI agenta na portu 13338, fakticky mrtvý bearer-token mechanismus v LocalApiServeru) se šesti vysoce závažnými zjištěními včetně zcela neověřeného lokálního REST API a cleartext HTTP navzdory deklarovanému zákazu. Jde přitom o nejcitlivější komponentu ekosystému, protože obsluhuje privilegovaný shell bez rootu, VPN/MITM vrstvu a nativní C démony. Repozitář kali_ai_assistant má rovněž kritické bezpečnostní nálezy (keystore v gitu, sdílené UID rušící sandboxing aplikací) a kali_GUI, ač s menším provozním rizikem, sdílí stejný vzor kompromitovaného podpisového klíče. Napříč všemi třemi repozitáři se opakuje identický vzor: **commitnutý produkční signing keystore s hardcoded slabým fallback heslem** – jde o systémový, ne izolovaný problém, pravděpodobně způsobený sdíleným build procesem (Modal). Druhým společným vzorem jsou **chybějící nebo formální autentizační/autorizační mechanismy** – od mrtvého auth kódu a neověřeného API v core_emulator, přes akce bez potvrzení v ai_assistant, až po neintegrovaný a needitovaný attack surface v kali_GUI. Třetím opakujícím se tématem je **nedostatečné CI/testovací pokrytí** – chybí lint, statická analýza a instrumentované testy ve všech třech projektech, přičemž kali_GUI nemá testy ani CI vůbec. Čtvrtým vzorem je zastaralost oproti standardům (targetSdk 28 napříč projekty, stale dokumentace, mrtvý/vendorovaný kód). **Top 3 doporučení:** (1) okamžitě rotovat všechny signing klíče, odstranit je z git historie ve všech třech repozitářích a nahradit hardcoded hesla bezpečnou správou secrets (Modal secrets/keystore management); (2) prioritně opravit autentizační díry v kali_core_emulator (LocalApiServer, AI agent démon) jako nejrizikovější komponentě, následované path-traversal a race condition nálezy v ai_assistant; (3) zavést jednotný CI standard napříč repozitáři zahrnující lint, statickou analýzu a alespoň základní automatizované testy, včetně sjednocení targetSdk a odstranění mrtvého/vendorovaného kódu.

Celkem nalezu: 98 (z toho 26 kritickych/vysokych overenych adversarialni kontrolou, 1 vyvraceno jako false-positive, 71 strednich/nizkych).

---

# Auditní zpráva – repozitář kali_ai_assistant

## KRITICKÉ

**1. Commitnutý produkční signing keystore + hardcoded heslo "password123"**
- Soubory: `app/release.jks`, `app/build.gradle.kts` (ř. 25–38), `.github/workflows/build.yml` (ř. 20–22), `modal_build.py` (ř. 635)
- `.gitignore` ignoruje `*.jks`, ale explicitně vyjímá `!app/release.jks` → keystore je trackovaný od commitu 9eaf1eb. `build.gradle.kts` defaultuje `storePassword`/`keyPassword` (release i debug) na literál `password123`, pokud nejsou nastaveny env proměnné; stejný fallback je i v CI workflow a v `modal_build.py`. `keytool -list -storepass password123` keystore skutečně otevře (alias `releasekey`). Kompromitace umožní podepsat škodlivou APK, kterou OS uzná jako legitimní update, a splní i signature-permission `BIND_BRIDGE` vůči kali_core_emulator.
- **Oprava:** Okamžitě rotovat podpisový klíč (starý považovat za kompromitovaný natrvalo, protože zůstává v historii gitu). Vyčistit historii (`git filter-repo`/BFG) a force-push do všech klonů/forků. Nový keystore ukládat mimo repo (CI secret store / Android Keystore na buildserveru), odstranit fallback `?: "password123"` ve všech třech místech a build nechat selhat (`error("KEYSTORE_PASSWORD not set")`), pokud proměnná chybí. Zvážit re-signing schéma přes signature verification hash (viz commit s "sanity check") jako trvalou kontrolu.

## VYSOKÁ

**2. `sharedUserId` ruší sandboxování mezi aplikacemi**
- Soubor: `app/src/main/AndroidManifest.xml` (`android:sharedUserId="cz.nethunter.agent"`, sdíleno i s kali_core_emulator)
- Sdílené UID = sdílený sandbox; zranitelnost v jedné app kompromituje i druhou. Google atribut deprecatuje a plánuje odstranit.
- **Oprava:** Nahradit sdílené UID standardní meziprocesovou komunikací (AIDL/Binder service s `signature`-level permission, `ContentProvider` s URI grants) místo přímého sdíleného souborového přístupu z `PiGuest.kt`. Je to větší refaktor, ale eliminuje systémové riziko.

**3. Path-traversal přes prefix matching v session read/delete**
- Soubor: `bridge/pi-rpc-bridge.js` – `opSessionsDelete` (~ř. 982–991) a handler `bridge.sessions.read` (~ř. 1358–1364)
- `path.resolve(p).startsWith(CFG.sessionsDir)` je neukotvený prefix check – sourozenecká cesta typu `<sessionsDir>-evil/x` projde, ačkoli leží mimo zamýšlený adresář. Bezpečný vzor (`insidePiDir()`, ř. 490–496) v kódu existuje, ale není zde použit.
- **Oprava:** Nahradit oběma místy voláním existujícího `insidePiDir()` (nebo `path.relative(CFG.sessionsDir, resolved)` a kontrolou, že výsledek nezačíná `..` a není absolutní), stejně jako to dělají ostatní operace.

**4. Race condition v `CoreBridgeClient.ensureBound()`**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/api/CoreBridgeClient.kt`
- Neatomický check-then-act (`bridge?.let { return it }` → `bindService(...)`) bez zámku; souběžná volání vytvoří více `ServiceConnection` objektů, starší zůstanou navázané a nikdy neuvolněné (leak), pole `connection` přepíše jen poslední.
- **Oprava:** Obalit bind logiku `Mutex`/`synchronized` blokem nebo použít `CompletableDeferred` pro in-flight bind, na který se další volající připojí místo nového `bindService()`.

**5. Možná NPE v `PiBridgeClient.isConnected`**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/api/PiBridgeClient.kt` (ř. 86)
- `socket?.isConnected == true && !socket!!.isClosed` čte pole `socket` dvakrát bez synchronizace; reader coroutine nuluje `socket` v `finally` bloku (ř. 150–159) souběžně na jiném IO vlákně → TOCTOU race → NPE.
- **Oprava:** Uložit `socket` do lokální `val` na začátku getteru (`val s = socket; return s?.isConnected == true && !s.isClosed`), případně synchronizovat čtení/zápis stejným zámkem jako `close()`.

**6. Debug i release build type sdílí stejný produkční keystore**
- Soubor: `app/build.gradle.kts` (ř. 25–38, `buildTypes.debug` ř. 49–52)
- Oba `signingConfigs` míří na `release.jks`, důvod je `sharedUserId` (viz nález #2), ale i běžné debug buildy tak vyžadují produkční klíč.
- **Oprava:** Po odstranění `sharedUserId` (nález #2) vrátit debug buildu standardní auto-generovaný debug keystore. Pokud `sharedUserId` zůstane dočasně, alespoň přesunout produkční keystore mimo checkout vývojářů (jen CI) a lokální debug buildy nechat bez podpisu shodného s produkcí.

## STŘEDNÍ

**7. SMS/volání/kontakty spouštěné přímo tool-cally modelu bez potvrzení**
- Soubor: `app/src/main/java/com/kali/aiassistant/domain/tools/AndroidActions.kt`
- LLM výstup (možný cíl prompt injection) může rovnou odeslat SMS/vytočit číslo bez potvrzovacího UI.
- **Oprava:** Přidat explicitní potvrzovací dialog (uživatelský tap) před `sendTextMessage`/`ACTION_CALL` pro tool volání iniciovaná modelem; logovat a rate-limitovat tyto akce.

**8. Tichý fallback na nešifrované SharedPreferences pro API klíče/tokeny**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/prefs/SecureKeyStore.kt` (ř. 21–36)
- Při selhání `EncryptedSharedPreferences` se tajemství ukládají do prostého `ai_assistant_secrets_fallback` bez varování.
- **Oprava:** Fallback ponechat jen jako nouzový, ale zalogovat chybu (bez citlivého obsahu), zobrazit uživateli varování v UI a při příští úspěšné inicializaci Keystore automaticky migrovat/zašifrovat existující fallback data a smazat plaintext soubor.

**9. Historie chatu (včetně shell výstupů) ukládaná jako plaintext JSON**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/ChatHistoryStore.kt`
- `save()`/`load()` ukládají nešifrovaně do `filesDir/chat_history/<id>.json`, přitom obsahují výstupy shellu, recon data, případně credentials.
- **Oprava:** Šifrovat soubory stejným mechanismem jako `SecureKeyStore` (např. `EncryptedFile` z Jetpack Security) nebo alespoň AES-GCM s klíčem v Android Keystore.

**10. Chybí integritní kontrola stažených GGUF model souborů**
- Soubor: `app/src/main/java/com/kali/aiassistant/local/ModelDownloader.kt`
- `download()` nekontroluje checksum po stažení, jen HTTPS transport.
- **Oprava:** Po dokončení stahování ověřit SHA-256 proti očekávané hodnotě (z Hugging Face API/manifestu) před přejmenováním do finálního umístění; při neshodě soubor smazat a stahování zopakovat/selhat.

**11. Mrtvý kód a rozporná metadata pro Anthropic streaming**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/api/AiProviderClient.kt`
- `supportsStreaming` vrací `false` pro ANTHROPIC, takže `anthropicStream()` (~60 řádků) je nedosažitelný, zatímco `ProviderRegistry.getProviderCapabilities()` tvrdí opak.
- **Oprava:** Sjednotit do jednoho zdroje pravdy (např. `ProviderRegistry` jako jediný poskytovatel capability flagů), opravit `AiProviderClient` a buď zapnout streaming, nebo `anthropicStream()` odstranit.

**12. `anthropicStream()` nikdy neemituje `StreamChunk.Done`, pokud SSE skončí bez `message_stop`**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/api/AiProviderClient.kt` (ř. ~285)
- Na rozdíl od `openAiStream()` chybí unconditional emit Done po skončení read loopu.
- **Oprava:** Přidat `emit(StreamChunk.Done)` i po ukončení smyčky (mimo `if type == "message_stop"` větev), analogicky k `openAiStream()`.

**13. Race na StringSet bookkeeping v `SecureKeyStore`**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/prefs/SecureKeyStore.kt`
- `saveProvider`/`deleteProvider`/`addFavoriteModel`/`removeFavoriteModel` dělají neatomický read-modify-write nad `StringSet`.
- **Oprava:** Serializovat zápisy přes `Mutex`/`synchronized`, nebo místo setu ukládat každou položku jako samostatný klíč (`provider_<id>`), čímž zápisy přestanou kolidovat.

**14. GitHub login `pending` flag se po dokončení nikdy nevynuluje**
- Soubor: `bridge/pi-rpc-bridge.js` (`exit` handler ~ř. 1239–1242)
- `startedAt` se resetuje jen v `opGithubCancel`/`opGithubLogout`, ne po normálním dokončení.
- **Oprava:** V `exit` handleru procesu `gh auth login` nastavit `ghLogin.startedAt = null` vždy vedle `ghLogin.proc = null`.

**15. GitHub login WebView nikdy nenavigován; polling coroutine scope leak**
- Soubor: `app/src/main/java/com/kali/aiassistant/ui/chat/GitHubAutoLogin.kt`
- WebView se vytváří, ale `loadUrl()` se nevolá (mrtvá komponenta); `startPolling()` běží v nezávislém `CoroutineScope`, který se nikdy nezruší při opuštění obrazovky.
- **Oprava:** Odstranit nepoužívaný WebView, nebo ho skutečně použít. `startPolling` navázat na `rememberCoroutineScope()`/`viewModelScope`, aby se zrušil s composable lifecycle.

**16. Neošetřené výjimky u ne-2xx/malformovaných odpovědí v `GitHubAuth`**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/api/GitHubAuth.kt`
- `requestDeviceCode()`/`fetchUser()` volají `decodeFromString` bez kontroly `response.isSuccessful`.
- **Oprava:** Před deserializací zkontrolovat `response.isSuccessful`, jinak vrátit chybový `Result`/throw čitelnou výjimku, po vzoru `listRepos()` (`runCatching`).

**17. targetSdk 28 vs. compileSdk 36 – zastaralé cílení**
- Soubor: `app/build.gradle.kts`
- `minSdk == targetSdk == 28`, přitom `compileSdk = 36`; chybí bezpečnostní vylepšení novějších API a Google Play by build s tímto targetSdk odmítl.
- **Oprava:** Je to vědomý kompromis kvůli W^X exec restrikcím (viz nález č. 21), ale mělo by být dokumentováno jako trvalé riziko s plánem migrace (např. spouštět binárky přes `exec()` z jiné cesty povolené na vyšším API, nebo přesunout `boot-ai` bridge mimo app-private storage).

**18. CI pipeline neobsahuje lint/statickou analýzu ani instrumentované testy**
- Soubor: `.github/workflows/build.yml`
- Ktlint běží jen lokálně (`mbuild`), `checkReleaseBuilds=false`/`abortOnError=false` v `app/build.gradle.kts`, chybí `androidTest`.
- **Oprava:** Přidat do workflow krok `ktlintCheck` a `lintDebug`/`lintRelease` (bez potlačení chyb) jako povinný gate na PR; přidat alespoň minimální instrumentovaný smoke test.

## NÍZKÁ

**19. targetSdk 28 záměrně obchází W^X hardening**
- Soubor: `app/build.gradle.kts` / `PiGuest.kt` (ř. 16–19)
- **Oprava:** Dlouhodobě najít alternativu k `execve()` z app-private storage kompatibilní s vyšším targetSdk (např. spustitelný soubor v adresáři mimo `app_data_file` doménu, nebo delegace exec na privilegovanou komponentu).

**20. Bezpečnostní knihovna `androidx-security-crypto` pinnutá na alpha verzi**
- Soubor: `gradle/libs.versions.toml` (`1.1.0-alpha06`)
- **Oprava:** Sledovat stabilní release a migrovat, jakmile vyjde; do té doby zafixovat konkrétní ověřenou alpha verzi a sledovat changelog na breaking/security fixy.

**21. Root-privilegovaný migrační skript instaluje APK bez ověření**
- Soubor: `bridge/pi_migrate.sh`
- `pm install -r` z `/data/local/tmp/kali-ai-new.apk`/`kali-core-new.apk` bez kontroly podpisu/checksum.
- **Oprava:** Před instalací ověřit APK signature (`apksigner verify`) proti očekávanému certifikátu a/nebo SHA-256 checksum dodaný spolu s balíčkem.

**22. Široké oprávnění `QUERY_ALL_PACKAGES` řízené LLM tool-cally**
- Soubor: `app/src/main/AndroidManifest.xml`
- **Oprava:** Pokud je to možné, nahradit `<queries>` deklaracemi konkrétních balíčků/intent filtrů místo plošného `QUERY_ALL_PACKAGES`.

**23. Race condition v `LlamaServerProcess.start()`**
- Soubor: `app/src/main/java/com/kali/aiassistant/local/LlamaServerProcess.kt`
- **Oprava:** Chránit `start()` mutexem/`synchronized` blokem stejně jako u nálezu #4.

**24. Duplicitní/nekonzistentní klasifikace provider/model (překlep `KOLOCODE`)**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/api/ProviderRegistry.kt`
- **Oprava:** Sjednotit na jeden enum (opravit překlep `KOLOCODE`→`KILOCODE`, sloučit duplicitní `Source` enum z `ModelRegistry.ModelInfo` a `domain.model.ModelInfo`).

**25. Tiše polykané, nelogované chyby parsování v SSE streamech**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/api/AiProviderClient.kt` (ř. ~113, ~289)
- **Oprava:** Nahradit `catch (_: Exception) {}` alespoň `Log.w(TAG, "SSE parse failed", e)`.

**26. Poškozené emoji/mojibake v UI textech**
- Soubory: `StatusBar.kt`, `SettingsScreen.kt`
- **Oprava:** Nahradit `U+FFFD` znaky správným Unicode emoji (zkopírovat přímo z UTF-8 zdroje, ne přes lossy schránku).

**27. Neatomický zápis session souborů historie chatu**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/ChatHistoryStore.kt`
- **Oprava:** Použít vzor temp-file + rename jako `bridge/pi-rpc-bridge.js` (`atomicWriteJson`), aby pád procesu neponičil soubor.

**28. OkHttp streamovací odpovědi nikdy explicitně nezavřené**
- Soubor: `app/src/main/java/com/kali/aiassistant/data/api/AiProviderClient.kt`
- **Oprava:** Obalit `response`/`source()` do `.use { }`, aby se spojení uvolnilo i při zrušení collecting coroutine.

**29. Chybějící `androidTest` zdrojová sada pro deklarované závislosti**
- Soubor: `app/build.gradle.kts` (ř. 142–145)
- **Oprava:** Buď vytvořit `app/src/androidTest` s alespoň jedním UI testem, nebo závislosti dočasně odstranit, dokud testy nebudou existovat.

**30. Nevyužité položky ve version catalogu**
- Soubor: `gradle/libs.versions.toml` (`kotlin-android`, `robolectric`, `androidx-test-core`)
- **Oprava:** Odstranit nepoužívané záznamy, nebo je skutečně zapojit (Robolectric testy).

**31. Chybí automatizovaná správa aktualizací závislostí**
- Adresář: `.github/`
- **Oprava:** Přidat `dependabot.yml` (gradle + github-actions ecosystem) nebo Renovate konfiguraci.

**32. GitHub token vkládán přímo do URL při git clone/fetch**
- Soubor: `modal_build.py` (ř. 138–140)
- **Oprava:** Použít `GIT_ASKPASS`/credential helper místo `https://<token>@github.com/...` v URL, aby token nebyl vidět v `ps`/logách subprocessu.

## Ověřeno bez závad
- `settings.gradle.kts` vs. modul `app/` — konzistentní (`rootProject.name`, `namespace`, `applicationId`, centralizované repozitáře). Žádná akce není potřeba.

---

# Auditní zpráva: kali_core_emulator

**Datum:** 2026-09-30 | **Nálezů celkem:** 32 (5 kritických, 7 vysokých, 12 středních, 8 nízkých)

## KRITICKÁ ZÁVAŽNOST (5)

**1. Commitnutý podpisový keystore + hardcoded heslo** — `app/release.jks`, `app/build.gradle.kts`, `AGENTS.md`
Skutečný release/debug signing key `com.linux_core` je v git historii (`.gitignore` obsahuje `*.jks`, ale přidáno pozdě/force-add). Heslo `password123` a alias `releaseKey` jsou natvrdo jako fallback v `build.gradle.kts` a zdokumentované v `AGENTS.md`. Keystore byl ověřen jako funkční (`keytool` ho otevřel s tímto heslem).
**Oprava:** Vygenerovat nový signing key mimo repo, rotovat ho (i za cenu nutnosti nové instalace u uživatelů kvůli sharedUserId `cz.nethunter.agent`), odstranit `release.jks` z celé git historie (`git filter-repo`/BFG), načítat heslo výhradně z CI secretu bez hardcoded fallbacku (selhat buildem, když proměnná chybí), a keystore/heslo z `AGENTS.md` odstranit.

**2. AI agent démon (port 13338) – autentizace fail-open** — `app/src/main/assets/nethunter_agent.py`, `LocalApiServer.kt`, `assets/usr/bin/boot`
Token se zapisuje jen na hostitelskou cestu; bind do guest `/tmp` je podmíněn `NH_SHARED_TMP` (default `false`). Guest tak token nikdy nevidí, `check_auth()` to vyhodnotí jako „no token = allow“ → `/query` (spouští `run_shell_command`) je bez autentizace přístupný komukoliv.
**Oprava:** Změnit `check_auth()` na fail-closed (chybějící token = odepřít, ne povolit), zajistit bind tokenu do guestu nezávisle na `NH_SHARED_TMP`, případně token předávat jinou cestou (env proměnná při spuštění procesu).

**3. Bearer-token autentizace LocalApiServeru je mrtvý kód** — `LocalApiServer.kt` (pole `authToken`, funkce `isAuthenticated()`)
`getAuthToken()`/`fallbackToken()` se nikde nevolají, pole `authToken` zůstává `null`. `isAuthenticated()` čte pole přímo a porovnává `MessageDigest.isEqual(providedToken, "")` → prázdný Bearer token projde. Zároveň to shodí dokumentovaný `nh`/`vpn-cli` flow, protože token se nikdy nezapíše do `shared_prefs/api_security.xml`.
**Oprava:** Zavolat `getAuthToken(context)` při startu serveru (`start()`), aby se token vygeneroval a persistoval; `isAuthenticated()` upravit tak, aby při `authToken == null` odmítal *všechny* požadavky (ne porovnával proti prázdnému řetězci).

**4. LocalApiServer (port 1337) bez autentizace pro loopback spojení** — `LocalApiServer.kt::handleConnection()`
Kontrola tokenu se přeskakuje úplně, pokud `isLocalConnection == true`. Android nemá per-app network namespace, takže libovolná appka s `INTERNET` permission se připojí na `127.0.0.1:1337` a zavolá `/shell`, `/shelldaemon/exec` (UID 2000!), `/device/admin` bez tokenu.
**Oprava:** Vyžadovat Bearer token i pro loopback spojení u `sensitiveEndpoints`; případně ověřovat peer UID/PID (`SO_PEERCRED` / `/proc/net/tcp`), ne jen IP adresu, a povolit bez tokenu jen vlastní UID appky.

**5. Duplicitní nález stejného problému (build health pohled)** — `app/release.jks`, `app/build.gradle.kts`
Stejná příčina jako nález #1, jen z pohledu reprodukovatelnosti buildu. Netřeba řešit odděleně — pokryto opravou u nálezu #1.

## VYSOKÁ ZÁVAŽNOST (7)

**6. `network_security_config.xml` globálně povoluje cleartext HTTP** — `app/src/main/res/xml/network_security_config.xml`
`base-config` má `cleartextTrafficPermitted="true"` a důvěřuje user CA, navzdory `usesCleartextTraffic="false"` v manifestu. Pouze 2 domény (kali.org, parrot.sh) mají pinning; Docker registry, VPN peer, LLM API jedou bez ochrany.
**Oprava:** V `base-config` nastavit `cleartextTrafficPermitted="false"` a `trust-anchors` jen na `system`; cleartext povolit explicitně jen tam, kde je to nezbytné (per-domain výjimka), ne globálně.

**7. Kotlin precedence bug ničí HTTP hlavičky v `/vpn/mitm/logs`** — `LocalApiServer.kt::handleVpnMitmLogs()` (~ř. 2773–2780)
`if/else` bez závorek způsobí, že `Content-Length`/`Connection: close` spadnou do `else`-větve a při neprázdných záznamech se do odpovědi nedostanou → klient čeká na EOF.
**Oprava:** Přidat závorky kolem `if` výrazu a hlavičky `Content-Length`/`Connection: close` zřetězit vždy, mimo podmínku: `"..." + (if (...) "X-Mitm-Latest-Ts: ...\r\n" else "") + "Content-Length: ...\r\n" + "Connection: close\r\n\r\n"`.

**8. Chybějící `/vpn/mitm*` prefixy v `sensitiveEndpoints`** — `LocalApiServer.kt` (~ř. 442–449)
Je uveden jen `/vpn/mitm/selective`; `/vpn/mitm`, `/vpn/mitm/ca`, `/vpn/mitm/logs`, `/vpn/mitm/sni-fallback` tak pro non-local spojení projdou bez tokenu, ačkoli AGENTS.md §8 je deklaruje jako chráněné.
**Oprava:** Nahradit výčet jedním prefixem `"/vpn/mitm"` (pokryje i `/selective`, `/ca`, `/logs`, `/sni-fallback`) a doplnit testy ověřující auth gate pro každý sub-endpoint.

**9. Submodul `nethunter-store-data` bez gitlinku ve stromu** — `.gitmodules`
`git clone --recurse-submodules` submodul vůbec nestáhne (chybí gitlink v `git ls-tree`).
**Oprava:** Re-přidat submodul správně (`git submodule add <url> nethunter-store-data` a commitnout gitlink), nebo pokud už není potřeba, odstranit záznam z `.gitmodules` a dokumentace.

**10. CI/Modal instalují jen Android SDK Platform 36, ale `compileSdk = 37`** — `.github/workflows/build.yml`, `tools/modal_build.py`
Gradle za běhu potichu stáhne a auto-akceptuje licenci pro Platform 37 — nereprodukovatelné v network-restricted prostředí.
**Oprava:** Přidat `platforms;android-37` do `sdkmanager --install` v obou místech (CI i Modal base image) a licenci akceptovat explicitně (`yes | sdkmanager --licenses`).

**11–12. (duplicitní vůči #10, jiný dimension tag)** — netřeba oddělené opravy.

## STŘEDNÍ ZÁVAŽNOST (12)

**13. `shareLocalApi` exponuje API 1337 na celý VPN subnet** — `LocalApiServer.kt`
Bind na adresu VPN rozhraní místo `127.0.0.1`, ochrana jen tokenem, který je (viz nález #3) fakticky nefunkční.
**Oprava:** Po opravě #3 vynutit token i pro toto rozhraní; zvážit dodatečné omezení na whitelistované peer IP v rámci VPN subnetu.

**14. Nadměrná oprávnění + `sharedUserId="cz.nethunter.agent"`** — `app/src/main/AndroidManifest.xml`
`MANAGE_EXTERNAL_STORAGE`, `QUERY_ALL_PACKAGES`, kamera, mikrofon, poloha, `PACKAGE_USAGE_STATS` atd. v jedné appce se sdíleným UID.
**Oprava:** Zrevidovat, které permissions jsou skutečně nutné; `sharedUserId` odstranit (Google ho deprecatuje) a nahradit komunikaci mezi app přes standardní IPC/Content Provider s vlastním permission.

**15. `DESTRUCTIVE_PATTERNS` je obejitelný substring blocklist** — `app/src/main/java/com/linux_core/core/device/ExecCore.kt`
Stejné obchvaty jako v historickém `docs/SECURITY_AUDIT.md` (MED-1) stále fungují.
**Oprava:** Nahradit blacklist allowlistem povolených příkazů/binárek pro neautentizované volání, nebo endpoint zcela zpřístupnit jen po autentizaci (návazně na #4).

**16. Race condition v lazy-init `authToken`** — `LocalApiServer.kt::getAuthToken()` (ř. 236–253)
Neatomický check-then-act bez synchronizace ve víceřadém serveru.
**Oprava:** Inicializovat token jednou při startu serveru (synchronně, mimo request handling) nebo obalit `synchronized`/`AtomicReference`.

**17. Off-by-one stack buffer overflow v `parse_words()`** — `app/src/main/cpp/cpuctl.c` (~ř. 402–465)
`strncat` nechá jen 1 volný byte, následný neomezený `strcat(expanded, " ")` zapíše 1 byte za hranici 4096B bufferu.
**Oprava:** Zmenšit limit `strncat` o další byte (`sizeof(expanded) - strlen(expanded) - 3`) nebo použít `snprintf`/bezpečné append funkce s kontrolou zbývající kapacity před každým zápisem.

**18. Symlink tar entries bez validace proti path traversal** — `app/src/main/java/com/linux_core/core/rootfs/RootfsManager.kt` (~ř. 91–101, i `extractTarXz`/`extractTarGzip` ~ř. 1571, 1617)
Hardlink větev validuje cíl uvnitř rootfs, symlink větev ne — `Os.symlink(tarEntry.linkName, ...)` bez kontroly.
**Oprava:** Zkopírovat stejnou kontrolu jako u hardlinků (`if (!resolvedTarget.startsWith(base)) throw IOException(...)`) do všech tří symlink-extrakčních míst.

**19. CI přeskakuje nativní moduly `ashell`/`cpuctl`** — `.github/workflows/build.yml`
AGENTS.md §4 je vyžaduje vždy v APK, CI je nekompiluje.
**Oprava:** Doplnit `ashell.c` a `cpuctl.c` do cross-compile kroku ve workflow vedle ostatních `.c` souborů.

**20. `mbuild usrtools` je zdokumentovaný, ale mrtvý příkaz** — `tools/mbuild`
Case blok je zakomentovaný, spuštění padá do `*)` a vrací exit 1.
**Oprava:** Buď odkomentovat a opravit `usrtools)` blok, nebo ho odstranit z usage stringu a hlavičkového komentáře.

**21. `mbuild` ztrácí stderr a obsahuje mrtvou pipe** — `tools/mbuild`
`all`/`native`/`build`/`smart` přesměrují jen stdout (`> build.log`, ne `2>&1`); `modal run ... > build.log | cat` má `| cat` bez vstupu.
**Oprava:** Sjednotit na `... 2>&1 | tee build.log` napříč všemi cases.

**22. `kotlin-android` plugin zakomentován bez zdůvodnění** — `app/build.gradle.kts`
Build funguje jen díky tranzitivní závislosti Compose pluginu — křehké, nezdokumentované v AGENTS.md §5.
**Oprava:** Buď plugin odkomentovat zpět explicitně, nebo pokud je záměrně nepotřeba, zapsat rozhodnutí a důvod do AGENTS.md §5, ať budoucí bump verze Compose pluginu build nerozbije potichu.

**23. `build-shelldaemon.yml` auto-commituje a pushuje binárku přímo na triggering branch** — `.github/workflows/build-shelldaemon.yml`
Bez PR/review kroku, bez `concurrency` group, na dev/master.
**Oprava:** Push směrovat na vedlejší branch a otevřít PR místo přímého pushe; přidat `concurrency` group proti souběhu s manuálním pushem.

**24. Modal build (sankcionovaná cesta) nikdy nespouští testy/lint** — `tools/modal_build.py`
Pouze `assembleDebug`; testy běží jen v GitHub Actions při pushi na dev/master — regrese se v běžném dev loopu neodhalí.
**Oprava:** Přidat `testDebugUnitTest` (případně `lint`) do `build()`/`smart_build()` v `modal_build.py`, nebo alespoň volitelný flag `mbuild build --with-tests`.

## NÍZKÁ ZÁVAŽNOST (8)

**25. Hardcoded debug heslo `"nethunter-dev"`** — `app/src/main/java/com/linux_core/security/RootCaInstaller.kt` → Oprava: generovat náhodné heslo per-instalaci i pro debug build, ukládat v Keystore.

**26. Částečný Docker registry token v Logcatu** — `app/src/main/java/com/linux_core/core/docker/DockerRegistryClient.kt` → Oprava: odstranit/redukovat `Log.d` s tokenem, logovat jen hash nebo nic.

**27. `sensitiveEndpoints` je blacklist, ne allowlist** (`/toast`, `/git-agent/*`, `/ashell`, `/terminal/*` chybí) — `LocalApiServer.kt` → Oprava: invertovat model na „defaultně vyžaduj auth, explicitně povoluj veřejné endpointy" (`publicEndpoints` allowlist).

**28. Duplicitní mrtvá implementace `extractTarGzip`** — `app/src/main/java/com/linux_core/core/rootfs/RootfsManager.kt` (top-level ~ř. 242–262 vs. member ~ř. 1598+) → Oprava: smazat nedosažitelnou top-level verzi.

**29. Trojnásobně duplikovaná detekce lokálního spojení** — `LocalApiServer.kt` → Oprava: extrahovat do jedné privátní funkce `isLocalConnection(socket): Boolean`.

**30. Dvě CI workflow kompilují `shell_daemon.c` na různých NDK API (24 vs 28)** — `.github/workflows/build.yml`, `build-shelldaemon.yml` → Oprava: sjednotit na `aarch64-linux-android28-clang` (odpovídá minSdk=targetSdk=28) v obou workflow.

**31. Stale Git LFS pravidla pro odstraněný `linux-x11` modul** — `.gitattributes` → Oprava: smazat obě LFS řádky pro `linux-x11`.

**32. F-Droid metadata 16 verzí pozadu** (`versionCode: 4` vs. reálných `20`) — `com.linux_core.yml` → Oprava: aktualizovat `Builds:` sekci nebo automatizovat generování z `build.gradle.kts` v release procesu.

**33. Chybí instrumentované (androidTest) testy** — `app/src/androidTest/java/com/linux_core/ExampleInstrumentedTest.kt` → Oprava: doplnit alespoň základní testy pro `LocalApiServer` HTTP endpointy a PRoot session lifecycle.

**34. Duplicitní vendored kopie `libs.versions.toml`/`gradle-wrapper.properties`** — `tools/gradle/libs.versions.toml`, `tools/gradle/wrapper/gradle-wrapper.properties` → Oprava: nahradit symlinkem na kanonický soubor, nebo generovat skriptem při buildu, ne ručně udržovat dvě kopie.

## Priorita zásahu

Nejnaléhavější je dvojice **#1 (kompromitovaný signing key)** a **#2/#3/#4 (kompletně nefunkční autentizace LocalApiServeru i agent démona)** — v současném stavu je zařízení s touto aplikací fakticky bez ochrany proti libovolné jiné appce na stejném zařízení a podpisový klíč umožňuje distribuovat podvržený update. Doporučuji řešit v pořadí: rotace klíče → oprava auth flow (#3+#4) → zbytek kritických/vysokých nálezů → build-health položky mohou počkat na další sprint.

---

# Auditní zpráva: kali_GUI

Datum: 2026-09-30 | Zdroj: statická analýza + ověřené nálezy (viz JSON)

## KRITICKÁ ZÁVAŽNOST

**1. Podepisovací keystore (`app/release.jks`) committnutý do veřejného GitHub repozitáře + slabé zadrátované heslo**
- Soubor: `app/build.gradle`, `app/release.jks`
- Binární keystore `release.jks` je ve verzovacím systému od prvního commitu (914af89), není v `.gitignore`, remote `origin` je veřejný `github.com/zombiegirlcz/kali_GUI`. `app/build.gradle` navíc u `signingConfigs.release` i `signingConfigs.debug` padá na natvrdo zapsané `"password123"` (storePassword i keyPassword) a alias `"releaseKey"`, pokud nejsou nastaveny env proměnné `KEYSTORE_PASSWORD`/`KEY_ALIAS`/`KEY_PASSWORD`. Debug a release sdílí stejný klíč.
- Riziko: kdokoli s přístupem k repu (i historickému) má fakticky privátní podepisovací klíč aplikace a jeho výchozí heslo → možnost podvrhnout aktualizaci, kterou Android přijme jako legitimní.
- **Oprava**: Okamžitě klíč rotovat (starý považovat za kompromitovaný, i po smazání ze stromu zůstává v historii). Odstranit `app/release.jks` z gitu i historie (`git filter-repo`/BFG) a přidat do `.gitignore`. V `build.gradle` odstranit fallback na `"password123"`/`"releaseKey"` — build má selhat (`throw GradleException`), pokud env proměnné chybí, nikdy nedosazovat výchozí hodnotu. Nový keystore ukládat mimo repo (CI secret store / Modal secret), distribuovat vývojářům mimo git.

## VYSOKÁ ZÁVAŽNOST

**2. Kotlin Gradle plugin se nikdy neaplikuje na modul `:app`**
- Soubor: `app/build.gradle` (plugins blok obsahuje jen `alias(libs.plugins.android.application)`), katalog `gradle/libs.versions.toml` definuje `kotlin-android`, ale nikde se nepoužívá.
- Riziko: standardní `./gradlew assembleDebug` dle vlastní dokumentace projektu nemusí sestavit .kt zdroje (žádná explicitní Kotlin compile task).
- **Oprava**: Do `app/build.gradle` doplnit `alias(libs.plugins.kotlin.android)` do bloku `plugins {}` a ověřit build (`./gradlew assembleDebug`).

**3. XTEST major opcode je natvrdo `132` místo dynamického zjištění přes QueryExtension**
- Soubor: `app/src/main/java/com/linux_core/xlauncher/X11Client.kt` (řádky ~453, 510; `OP_QUERY_EXTENSION = 98` je definováno, ale nikdy použito)
- Riziko: na X serveru, kde XTEST dostane jiný opcode než 132, selže veškerý vstup (myš/klávesnice) tiše, protože `inject()` chyby jen loguje.
- **Oprava**: Po handshake odeslat `QueryExtension("XTEST")` a získaný `major_opcode` uložit a použít místo konstanty. Zpracovat i chybovou odpověď serveru namísto tichého polykání výjimek.

**4. Nulové pokrytí testy pro vlastní kód aplikace**
- Soubor: `app/src/main/java/com/linux_core/xlauncher/X11Client.kt`, `LauncherActivity.kt`
- Chybí `app/src/test` i `app/src/androidTest` (existující `testInstrumentationRunner` je mrtvá konfigurace). Netestovaný je ruční parser X11 protokolu i stavový automat gest.
- **Oprava**: Založit `app/src/test/java/...` s JVM unit testy pro `parseSetup()`/dekódování ZPixmap (lze testovat čistě na bajtových polích bez zařízení) a `app/src/androidTest` pro gesta v `LauncherActivity`. Minimálně pokrýt handshake parsing a keycode mapping jako regresní bariéru.

**5. V repozitáři chybí jakákoli CI konfigurace pro projekt samotný**
- Soubor: kořen repozitáře (žádný `.github/workflows`, `.gitlab-ci.yml` mimo vendorované třetí strany)
- Riziko: žádná automatická brána buildu/lintu/testů na push/PR; jediná cesta je ruční `tools/mbuild` → Modal.
- **Oprava**: Přidat `.github/workflows/build.yml` spouštějící `./gradlew assembleDebug lint` (a časem testy z bodu 4) na push/PR do main.

## STŘEDNÍ ZÁVAŽNOST

**6. Prekompilovaný, needitovatelný Magisk modul s root oprávněním v repu**
- Soubor: `magisk-modules/custom_usb_g2_setup-v2.1.zip`
- Binární blob bez zdrojových kódů/build skriptu, obsahuje binárky běžící po flashnutí s root právy — nelze auditovat, riziko supply-chain útoku a navíc nesouvisí s Android GUI aplikací.
- **Oprava**: Odstranit z repozitáře aplikace; pokud je modul potřeba, přesunout do samostatného auditovaného repa se zdrojovými skripty a build procesem, artefakt publikovat přes release/registry s checksummou.

**7. Sdílené proměnné mezi vlákny bez `@Volatile`/synchronizace**
- Soubor: `X11Client.kt` (`socket`/`input`/`output`), `LauncherActivity.kt` (`client`)
- Zápis probíhá na pozadí-vlákně, čtení na UI vlákně bez happens-before záruky → možné stale/null hodnoty, ztracené první taps/keys, race při `disconnect()`.
- **Oprava**: Označit sdílená pole `@Volatile` nebo přesunout na `AtomicReference`, případně synchronizovat přístup přes `Handler`/coroutine s jedním vláknem vlastnícím socket.

**8. Dvojitý pravý klik při přechodu z jednoprstého držení na dvouprsté gesto**
- Soubor: `app/src/main/java/com/linux_core/xlauncher/LauncherActivity.kt` (`onMouseTouch`/`onScrollTouch`, flagy `rightClicked`/`twoFingerRightClicked`)
- **Oprava**: Sdílet jeden stavový flag mezi oběma cestami (např. `rightClickFired: Boolean` na úrovni gesta) a `scheduleTwoFingerHold()` nechat kontrolovat, zda už proběhl, případně zrušit/reset flag i v `onDesktopTouch()` při přidání druhého prstu.

**9. IME proxy zachytává jen `KeyEvent`, ztrácí text vložený přes `commitText()`**
- Soubor: `LauncherActivity.kt` (spoléhá jen na `dispatchKeyEvent()` z 1x1 EditTextu)
- Riziko: autokorekce, swipe typing, predikce a diakritika/emoji se nikdy neodešlou na vzdálený server, bez chyby.
- **Oprava**: Implementovat vlastní `InputConnection` (přes `onCreateInputConnection`) a zpracovat `commitText()`/`setComposingText()`, převést commitovaný text na sekvenci X11 key eventů nebo použít XTEST s Unicode vstupem.

**10. Efektivní verze Kotlin kompilátoru není nikde deklarována ani kontrolovaná**
- Soubor: `gradle/libs.versions.toml` (deklarovaná verze 2.3.21 nikde neaplikovaná — viz bod 2)
- **Oprava**: Po opravě bodu 2 (aplikace pluginu) ověřit, že se skutečně použije verze z katalogu, a zadokumentovat ji v README/AGENT.md.

**11. Nekonzistentní verze `lifecycle-ktx` závislostí**
- Soubor: `app/build.gradle` (katalogová `2.10.0` pro runtime-ktx vs. natvrdo `"androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0"`)
- **Oprava**: Přidat `viewmodel-ktx` do `gradle/libs.versions.toml` se stejnou verzí jako runtime-ktx a odkazovat přes alias, odstranit natvrdo zapsaný řetězec.

**12. `targetSdk` 28 vs. `compileSdk` 36**
- Soubor: `app/build.gradle`
- **Oprava**: Postupně zvýšit `targetSdk` (ideálně na aktuální stabilní API), otestovat chování scoped storage / background restrictions / permission modelu; pokud existuje konkrétní důvod pro 28, zdokumentovat jej v `build.gradle` komentářem.

## NÍZKÁ ZÁVAŽNOST

**13. Vendorovaný, nezapojený strom zdrojů X serveru (termux-x11/Lorie)**
- Soubor: `app/src/main/linux-x11/` (vlastní `build.gradle` s odlišnými SDK/NDK/Kotlin verzemi, není zahrnut v `settings.gradle`)
- **Oprava**: Buď modul odstranit, dokud nebude aktivně používán (AGENT.md Fáze 2 = NOT STARTED), nebo jej přesunout mimo hlavní strom (submodule/branch) a sjednotit verze SDK/NDK/Kotlin/lifecycle před případným zapojením.

**14. Exportovaná `LauncherActivity` bez omezení (informativní)**
- Soubor: `app/src/main/AndroidManifest.xml`
- Standardní pro HOME/LAUNCHER aktivitu, ale připojuje se na pevný loopback `127.0.0.1:1337` bez auth. **Oprava**: zdokumentovat záměr komentářem; zvážit ověření volajícího balíčku, pokud aktivita začne přijímat extras.

**15. `tools/mbuild` — kombinace `>`/`>>` přesměrování a `| cat` tiše zahazuje výstup**
- Soubor: `tools/mbuild`
- **Oprava**: Použít `tee`: `modal run modal_build.py::build 2>&1 | tee -a build.log` místo `>> build.log | cat`.

**16. GitHub token krátce v plaintextu v remote URL / na disku**
- Soubor: `tools/modal_build.py`
- **Oprava**: Použít `git -c http.extraHeader="Authorization: Bearer $TOKEN"` nebo credential helper místo vkládání tokenu do URL a `.git/config`.

**17. Zastaralá dokumentace neodpovídá skutečné implementaci**
- Soubor: `docs/plans/kali_gui_foundation.md` (popisuje VNC/RFB namísto skutečného X11 klienta), `AGENT.md` (cesta `/root/core/kali_GUI` místo `/root/kali_combined/kali_GUI`, T3 označeno jako NOT STARTED ačkoli hotovo)
- **Oprava**: Aktualizovat oba dokumenty tak, aby odpovídaly aktuální architektuře (X11Client/X11Renderer, Xvfb:6000) a správné cestě checkoutu.

**18. Rozbitý symlink `ktlint` v kořeni repozitáře**
- Soubor: `ktlint` (ukazuje sám na sebe)
- **Oprava**: Opravit symlink na skutečný ktlint wrapper/binárku nebo jej nahradit gradle pluginem (`ktlint-gradle`) a odstranit mrtvý odkaz.

---

**Shrnutí**: 1 kritický nález (sdílený podepisovací klíč v public repu), 4 vysoké (Kotlin plugin chybí, hardcoded XTEST opcode, nulové testy, chybějící CI), 7 středních (Magisk blob, race condition, gesta, IME, verze závislostí, targetSdk) a 6 nízkých (dead code, dokumentace, drobné tooling chyby). Nejnaléhavější akce: okamžitá rotace signing klíče a jeho odstranění z gitu.
