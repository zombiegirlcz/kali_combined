# Prompt pro agenta — strukturální refaktor (kali_core_emulator + kali_ai_assistant)

> Zkopíruj celý text níže (od `====`) do nové agentní session, která má build
> prostředí (Android SDK 36 + NDK 28, JDK). Agent pracuje na už existující větvi
> `claude/refactor-structure-xy31gk` v obou repo.

====================================================================

Jsi zkušený Android/Kotlin inženýr. Provedeš **strukturální refaktor** dvou
repozitářů. Refaktor = **přeskupení kódu beze změny chování**. Žádné nové funkce,
žádné opravy bugů, žádná změna logiky. Cíl je čitelnost a struktura.

## Repozitáře a větve

Pracuj VÝHRADNĚ na této větvi (už existuje na originu, odvozená z uklizeného stavu):

- `kali_core_emulator` → větev `claude/refactor-structure-xy31gk`
- `kali_ai_assistant`  → větev `claude/refactor-structure-xy31gk`

Na začátku v každém repu: `git fetch origin && git checkout claude/refactor-structure-xy31gk`.
Nikdy nepushuj na jinou větev. Nepřepisuj historii (žádný rebase/force-push).

## 🔒 ZLATÁ PRAVIDLA (dodržuj bez výjimky)

1. **Po KAŽDÉM kroku** (rozdělení souboru, přesun balíčku) spusť:
   `./gradlew testDebugUnitTest assembleDebug --no-daemon --stacktrace`
   Když je build červený, **oprav to než budeš pokračovat**. Nikdy necommituj
   rozbitý build.
2. **Jeden logický krok = jeden commit.** Malé, ověřitelné dávky. Ne velký balík.
3. **Beze změny chování.** Přesun tříd/metod ano; přejmenování metod, změna
   signatur nebo logiky ne (jen když to přesun nutně vyžaduje, a pak minimálně).
4. **NESAHEJ na:** `app/release.jks` (záměrný sdílený debug keystore),
   balíček `com/adguard/**` (vendorovaný cizí kód — mimo rozsah), historii gitu.
5. **Před přesunem každé třídy** ji vyhledej v celém repu:
   `git grep -n "NazevTridy"` — kvůli referencím v `AndroidManifest.xml`,
   `Class.forName`, `ComponentName`, AIDL, reflection a stringových odkazech.
6. Commit zprávy v češtině, styl repa: `refactor(pi): ...`, `refactor(core): ...`.
7. Na konci každého repa: `git push origin claude/refactor-structure-xy31gk`.

## Pořadí práce (nejbezpečnější první)

### KROK 1 — kali_ai_assistant: rozbití PiViewModel.kt (2082 řádků)

Soubor `app/src/main/java/com/kali/aiassistant/ui/pi/PiViewModel.kt` dělá příliš
mnoho věcí. Nejdřív si ho přečti celý. Má tyto přirozené shluky odpovědností —
vytáhni každý do vlastní třídy (spolupracovník) ve `ui/pi/` (klidně podbalíček
`ui/pi/internal/`), a PiViewModel nech jako tenký orchestrátor držící `StateFlow`:

- **Připojení/reconnect:** `connect`, `disconnect`, `scheduleReconnect`,
  `observeClient`, `fail`, `loadDiagnostics`.
- **Streaming & sestavení zpráv:** `handleMessage`, `handleAgentEvent`,
  `handleMessageUpdate`, `handleMessageEnd`, `appendAssistant`, `appendThinking`,
  `closeStreamingBlocks`, `upsertTool`, `updateTool`, `addNotice`, `extractText`
  → např. `PiEventReducer` / `PiMessageAssembler`.
- **UI požadavky (confirm/select/input):** `handleUiRequest`, `respondConfirm`,
  `respondSelect`, `respondInput`, `removeUiRequest` → `PiUiRequestHandler`.
- **Projekty (CRUD):** `loadProjects`, `parseProject`, `createProject`,
  `cloneProject`, `moveProject`, `deleteProject`, `openProject`, `closeProject`
  → `PiProjectController`.
- **Sessions (CRUD):** `loadSessions`, `parseSession`, `newSession`,
  `openSession` → `PiSessionController`.

Cíl: `PiViewModel.kt` pod ~600 řádků, každý spolupracovník soustředěný na jednu
věc. Commituj po jednotlivých extrakcích (jeden shluk = jeden commit + build).

Volitelně stejným způsobem: `PiScreen.kt` (1268 ř.) a `PiSettingsScreen.kt`
(1038 ř.) — rozdělit velké `@Composable` do menších souborů ve `ui/pi/`.

### KROK 2 — kali_ai_assistant: deduplikace bridge skriptů

Teď jsou stejné soubory na dvou místech (ručně kopírované):
`bridge/*` a `app/src/main/assets/bridge/*` (pi-rpc-bridge.js, pi-app-bridge.ts,
bridge-supervisor.sh, setup-ai-user.sh, boot-ai, test-client.js — momentálně
bajt-identické).

Udělej `bridge/` jediným zdrojem pravdy:
1. V `app/build.gradle.kts` přidej Gradle `Copy`/`Sync` task, který zkopíruje
   `../bridge/` (jen runtime soubory, ne testy) do `src/main/assets/bridge/`
   a naváž ho jako závislost `preBuild` (aby proběhl před `mergeDebugAssets`).
2. `git rm` commitované kopie v `app/src/main/assets/bridge/` a přidej je do
   `.gitignore` (jsou nově generované).
3. V `.github/workflows/build.yml` nahraď/odstraň krok „Verify bridge scripts
   are in sync" (po deduplikaci je zbytečný — generuje se to).
4. Ověř `./gradlew assembleDebug` a **rozbal výsledné APK** (`unzip -l`), že
   `assets/bridge/pi-rpc-bridge.js` v něm je. Teprve pak commit.

### KROK 3 — kali_core_emulator: rozbití God-souborů

Stejnou technikou jako Krok 1 rozděl (každý = série commitů, build po každém):
- `app/src/main/java/com/linux_core/core/LocalApiServer.kt` (3398 ř.) —
  vytáhni skupiny route/endpoint handlerů a pomocné funkce do samostatných tříd.
- `app/src/main/java/com/linux_core/ui/terminal/TerminalActivity.kt` (2944 ř.).
- Volitelně: `MainActivity.kt` (2445), `RootfsManager.kt` (1883),
  `VpnSecurityTab.kt` (1768), `ProotManager.kt` (1697).

### KROK 4 — kali_core_emulator: rozdělení balíčku core/ (NEJRIZIKOVĚJŠÍ)

Balíček `com/linux_core/core/` má 64 tříd v jedné složce. Rozděl do domén:
`core/vpn/`, `core/mitm/`, `core/terminal/`, `core/usb/`, `core/rootfs/`,
`core/docker/`, `core/ai/`, `core/net/` (názvy dolaď podle skutečných tříd).

**Dělej to PO JEDNÉ DOMÉNĚ**, každou samostatný commit + build. Pro každý přesun:
1. `git grep -n "NazevTridy"` napříč repem.
2. Přesuň soubor, uprav `package` deklaraci + všechny `import`.
3. **KRITICKÉ pro Android:** třídy odkazované v `AndroidManifest.xml`
   (`android:name` u `<service>`, `<activity>`, `<receiver>`, `<provider>`) mají
   plně kvalifikované jméno — po přesunu balíčku uprav i manifest. Totéž pro
   `ComponentName`, `Class.forName`, AIDL a stringové odkazy.
4. `./gradlew testDebugUnitTest assembleDebug` → zeleno → commit.

Pokud narazíš na obousměrnou závislost, kterou přesun rozbije nad rámec
mechanického refaktoru, **zastav se u té domény, nech ji jak je, a napiš to do
souhrnu** — nevymýšlej změny chování.

## Definice hotového (per repo)

- `./gradlew testDebugUnitTest assembleDebug` je zelené.
- APK jde nainstalovat a klíčové obrazovky fungují (Pi chat, terminál) — smoke
  test na zařízení.
- Vše commitnuté v malých dávkách, pushnuto na `claude/refactor-structure-xy31gk`.
- Na konci napiš krátký souhrn: které soubory/domény rozděleny, co (pokud něco)
  bylo vynecháno a proč.

Pracuj metodicky, build drž zelený, a když si nejsi jistý, že je něco čistý
přesun beze změny chování — raději menší krok.

====================================================================
