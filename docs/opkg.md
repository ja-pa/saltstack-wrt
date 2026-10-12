# opkg – správa balíčků

Modul `opkg` propojuje správce balíčků OpenWrt a Turris OS se standardním
rozhraním Salt `pkg`. Umožňuje zjistit nainstalované balíčky, obnovit indexy
feedů, instalovat chybějící balíčky a odstraňovat je. Slouží zejména
pro deklarativní zajištění přítomnosti nebo nepřítomnosti balíčku.

V Salt kódu se volá **`pkg.installed` / `pkg.removed`** a v příkazech
**`pkg.install` / `pkg.remove`**. Název `opkg` označuje provider, který tato
volání na minionu provede; vlastní `opkg.installed` state zde není.

## Předpoklady

- Na minionu je doplněk `minion-opkg`. Je také součástí metabalíčku
  `minion-openwrt`; samotný základní `salt-minion` ho nevyžaduje.
- Program `opkg` je dostupný v `PATH`.
- Grain `os` nebo `os_family` odpovídá `OpenWrt`, `TurrisOS` nebo `Turris`
  (bez ohledu na velikost písmen).
- Minion má oprávnění zapisovat do systému a databáze opkg.
  Pro instalaci z feedů musí mít nakonfigurované feedy a přístup k nim.

Provider se při splnění podmínek načte automaticky jako `pkg`; není potřeba
ručně nastavovat `providers`. Master používá běžné Salt states bez vlastního
opkg doplňku. Balení a načtení doplňků popisuje [návod k doplňkům](https://github.com/ja-pa/saltstack-wrt-tests/blob/codex/documentation-cleanup/docs/package-addons.md).

Dokumentace odpovídá zdejší implementaci pro Salt 3008.3.

## Co modul umí

| Operace | Salt rozhraní | Chování |
| --- | --- | --- |
| Inventář | `pkg.list_pkgs` | Vrátí názvy a verze nainstalovaných balíčků. |
| Verze balíčku | `pkg.version` | Vrátí nainstalovanou verzi; pro chybějící balíček prázdný řetězec. |
| Obnova indexů | `pkg.refresh_db` | Spustí `opkg update` nad nakonfigurovanými feedy. |
| Instalace z feedů | `pkg.install`, `pkg.installed` | Instaluje chybějící balíčky podle názvu, včetně závislostí řešených opkg. |
| Instalace IPK | `pkg.install` / `pkg.installed` s `sources` | Přijímá absolutní cestu na minionu nebo `salt://` soubor. Rozdíl v práci s verzí je popsán níže. |
| Odstranění | `pkg.remove`, `pkg.removed` | Odstraní přítomné balíčky podle přesného názvu. |
| Dostupná novější verze | `pkg.latest_version` | Čte indexy feedů; balíček neaktualizuje. |
| Porovnání verzí | `pkg.version_cmp` | Používá `opkg compare-versions` a vrací `-1`, `0` nebo `1`. |

Instalace podle názvu je idempotentní: již přítomný balíček se přeskočí.
Odstranění nepřítomného balíčku také nic nemění. Opakované execution volání
v těchto případech vrací `{}`; splněný state má prázdné `changes`.

## Příklady Salt states

Následující ukázky jsou samostatné soubory SLS. Předpokládají výchozí
`file_roots` masteru s adresářem `/srv/salt` a minion s ID `openwrt-test`.
Vlastní ID a cesty uprav podle konfigurace. Balíčky `curl` a `jq` musí být
dostupné v nakonfigurovaných feedech pro daný systém.

### Jeden balíček z feedu

Soubor `/srv/salt/balicky.sls`:

```yaml
curl:
  pkg.installed: []
```

Salt použije ID stavu `curl` jako název balíčku. Chceš-li popisnější ID,
uveď název výslovně:

```yaml
nastroj-pro-http:
  pkg.installed:
    - name: curl
```

Obě varianty zajišťují přítomnost `curl`. Existující starší verzi ponechají.

### Více balíčků a obnova indexů

```yaml
diagnosticke-nastroje:
  pkg.installed:
    - pkgs:
      - curl
      - jq
    - refresh: true
```

`refresh: true` vyžádá před instalací obnovu indexů. `refresh: false` ji
pro dané volání vypne. Bez uvedení parametru používá standardní
`pkg.installed` mechanismus Salt refresh markeru: úspěšná obnova se sdílí
s dalšími package states ve stejném běhu. Neúspěšná obnova marker nesmaže.
Přímé execution volání `pkg.install` má naopak výchozí `refresh=False`.

### Balíček ze Salt fileserveru

Umísti vlastní IPK například do
`/srv/salt/packages/moje-aplikace_1.0-r1_all.ipk` a vytvoř SLS:

```yaml
moje-aplikace:
  pkg.installed:
    - sources:
      - moje-aplikace: salt://packages/moje-aplikace_1.0-r1_all.ipk
    - refresh: false
```

Soubor se stáhne do cache minionu. Klíč `moje-aplikace` musí být skutečný název
z pole `Package` v IPK, nikoli název souboru. `salt://` používá prostředí
`saltenv` (výchozí `base`). IPK a jeho závislosti musí odpovídat cílovému systému.
Parametr `refresh: false` je vhodný, pokud má minion potřebné indexy nebo
již nainstalované všechny závislosti; jinak lze použít `refresh: true`.

**Tento state zajišťuje přítomnost, ne shodu verze s IPK.** Pokud je
`moje-aplikace` už nainstalovaná, nahrazení souboru na masteru novější verzí
nevyvolá automatickou aktualizaci. Provider neposkytuje `lowpkg.bin_pkg_info`,
které obecný state potřebuje pro porovnání nainstalované verze s IPK.

### IPK uložené na minionu

Pokud už soubor leží na routeru:

```yaml
moje-aplikace:
  pkg.installed:
    - sources:
      - moje-aplikace: /tmp/moje-aplikace_1.0-r1_all.ipk
    - refresh: false
```

Cesta musí být absolutní a vztahuje se k **minionu**. Soubor musí existovat
před spuštěním stavu. Platí stejné omezení porovnávání verzí jako pro `salt://`.

### Odstranění balíčku

```yaml
odstranit-jq:
  pkg.removed:
    - name: jq
```

Více balíčků lze odebrat pomocí `pkgs`:

```yaml
odstranit-diagnostiku:
  pkg.removed:
    - pkgs:
      - curl
      - jq
```

Opkg zachovává kontroly závislostí. Balíček, který potřebuje jiný
nainstalovaný balíček, nemusí dovolit odstranit. Provider nepřidává automatické
odstranění nepotřebných závislostí ani vynucené odebrání.

### Soubor spravovaný až po instalaci balíčku

Standardní Salt requisites lze použít i s tímto providerem:

```yaml
curl:
  pkg.installed: []

/root/.curlrc:
  file.managed:
    - mode: '0600'
    - contents: |
        connect-timeout = 10
        max-time = 60
    - require:
      - pkg: curl
```

`require` zajistí pořadí: Salt spravuje soubor až po úspěšném zajištění balíčku.
Ukázka spravuje celý obsah `/root/.curlrc`.

### Náhled a aplikování

Pro soubor `/srv/salt/balicky.sls` spusť na masteru:

```sh
salt openwrt-test state.apply balicky test=True
salt openwrt-test state.apply balicky
```

`test=True` neinstaluje ani neodstraňuje balíčky; zobrazí plánované změny.
Náhled nepotvrzuje úspěch budoucí instalace ani použitelnost závislostí.
Pro instalaci podle názvu čte dostupné verze z existujících indexů;
samotný náhled běžných ukázek výše je neobnovuje ani s `refresh: true`.
Potřebuješ-li čerstvé indexy, před náhledem výslovně spusť `pkg.refresh_db`.

Na routeru lze stejný SLS spustit přes `salt-call state.apply balicky`.
Varianta `salt-call --local state.apply balicky` potřebuje SLS i případné
`salt://` IPK v lokálních `file_roots`; nepoužívá fileserver masteru.

## Přímé volání funkcí

Execution funkce slouží pro jednorázové operace a diagnostiku. Pro trvale
požadovaný stav používej SLS ukázky výše.

```sh
salt openwrt-test pkg.list_pkgs
salt openwrt-test pkg.list_pkgs versions_as_list=True
salt openwrt-test pkg.list_pkgs use_context=False
salt openwrt-test pkg.version curl
salt openwrt-test pkg.version curl jq
salt openwrt-test pkg.refresh_db
salt openwrt-test pkg.install curl refresh=True
salt openwrt-test pkg.install 'pkgs=["curl", "jq"]'
salt openwrt-test pkg.remove jq
salt openwrt-test pkg.latest_version curl refresh=False
salt openwrt-test pkg.version_cmp '1.0-r2' '1.0-r10'
```

Stejné funkce lze volat lokálně, například `salt-call --local pkg.list_pkgs`.
Inventář má tvar `{název: verze}`; `versions_as_list=True` vrací hodnoty
jako seznamy. `use_context=False` vynutí nové čtení databáze místo cache
aktuálního Salt kontextu. `pkg.version` vrací pro jeden název řetězec,
pro více názvů slovník.

`pkg.latest_version` vrací nejvyšší dostupnou verzi, pokud je novější než
nainstalovaná nebo balíček dosud chybí. Pro neznámý balíček i pro již aktuální
balíček vrátí `''`. Více názvů vrací slovník. Jde pouze o čtení, nikoli upgrade.
Porovnávání respektuje opkg pořadí včetně release a prerelease suffixů.

Přímá instalace vlastního IPK:

```sh
salt openwrt-test pkg.install 'sources=[{"moje-aplikace":"/tmp/moje-aplikace_1.0-r1_all.ipk"}]'
salt openwrt-test pkg.install 'sources=[{"moje-aplikace":"salt://packages/moje-aplikace_1.0-r1_all.ipk"}]' saltenv=base
```

Na rozdíl od `pkg.installed` přímé `pkg.install sources=...` čte metadata IPK
a porovnává jeho verzi s nainstalovanou. Stejnou verzi přeskočí, odlišnou
předá opkg. Úspěch aktualizace závisí na opkg; downgrade se nevynucuje.
Zdroje se kontrolují před zahájením instalace.

## Co modul neumí

| Požadavek | Omezení |
| --- | --- |
| Automaticky udržovat nejnovější verzi | `pkg.latest` není podporovaný state pro tento provider, i když existuje čtecí `pkg.latest_version`. |
| Hromadný nebo systémový upgrade | `pkg.upgrade` není implementované. Instalace podle názvu již přítomný balíček přeskočí. |
| Vybrat konkrétní verzi z feedu | `version` ani verze v položkách `pkgs` nejsou podporované. |
| Vynutit reinstall / downgrade | `reinstall=True` a force přepínače nejsou podporované. |
| Purge a hold | `pkg.purge`, `pkg.purged` ani držení verzí nejsou podporované. |
| Vybrat feed pro jedno volání | `fromrepo` není podporované; používá se konfigurace opkg na minionu. |
| Vypnout kontrolu podpisů | `skip_verify=True` není podporované; platí konfigurace ověřování opkg. |
| Obecné URL jako zdroj IPK | `sources` přijímá pouze absolutní cestu nebo `salt://`, nikoli `http://` / `https://`. |
| Libovolný formát balíčku | Podporované je OpenWrt IPK s vnějším tar archivem a `control.tar.gz`, nikoli Debian ar archiv. |
| Wildcardy a odebrání konkrétní verze | Odstranění používá přesné názvy bez globů a bez specifikace verze. |
| Alternativní root a libovolné volby opkg | Například `root` ani obecné předávání CLI přepínačů nejsou podporované. |
| Transakce s rollbackem | Operace s více balíčky není atomická; částečné změny se automaticky nevracejí. |
| Správa politiky Turris Updateru | Instalace a odstranění přes opkg nemění jeho trvalá pravidla. |

`pkgs` a `sources` nelze kombinovat v jednom volání. Názvy musí začínat
písmenem nebo číslicí a smí dále obsahovat pouze ASCII písmena, číslice, `+`, `_`,
`.` a `-`. Modul spouští opkg bez shellu.

Nepodporované parametry provider odmítá. Obecný Salt state však může už
splněný požadavek vyhodnotit bez jeho volání; takový úspěch neznamená,
že zdejší provider danou funkci podporuje.

## Změny a chyby

Po instalaci nebo odstranění modul znovu načte inventář a vrací skutečný
rozdíl. Změny mohou obsahovat také závislosti, například:

```yaml
jq:
  old: ''
  new: 1.7.1-r1
```

Verze je pouze ilustrační a závisí na cílovém feedu. Při odstranění bude
`old` obsahovat původní verzi a `new` prázdný řetězec.

Chyba opkg obsahuje návratový kód, standardní i chybový výstup a zjištěné
částečné změny. Pokud například instalace prvního balíčku uspěje a druhý
chybí ve feedu, první může zůstat nainstalovaný i při neúspěchu celé operace.
Neplatný IPK nebo nesoulad pole `Package` skončí chybou před instalací.

## Ověření implementace

Dokumentace vychází z provideru
`openwrt/feed/python-salt/files/opkg.py` v tomto balíčkovém repozitáři.
Unit testy `tests/test-opkg-unit.py`, runtime scénář `tests/opkg-local-omnia.py`
a stavy `tests/states/pkg-installed.sls` / `pkg-removed.sls` jsou v doprovodném
[repozitáři saltstack-wrt-tests](https://github.com/ja-pa/saltstack-wrt-tests/tree/codex/documentation-cleanup/tests).
Obecné package states Saltu zůstávají beze změny.

Postup ověřování a historické výsledky ARM testů jsou v
[původní dokumentaci testovacího repozitáře](https://github.com/ja-pa/saltstack-wrt-tests/blob/codex/documentation-cleanup/docs/opkg.md#opakovatelné-ověření). Jejich rozsah neznamená
ověření fyzické Omnie ani chování Turris Updateru.
