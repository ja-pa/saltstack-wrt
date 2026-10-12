# saltstack-wrt

Dokumentace Salt minionu a jeho doplňků pro OpenWrt a Turris OS.
Popisuje chování zdejší implementace, její omezení a použití v Salt states.

Začni modulem [opkg – správa balíčků](opkg.md): instalace z feedů,
vlastních IPK a odstraňování balíčků pomocí standardních `pkg` states.
Další návody a testovací protokoly jsou v doprovodném repozitáři
[saltstack-wrt-tests](https://github.com/ja-pa/saltstack-wrt-tests/tree/codex/documentation-cleanup/docs).

## Práce s dokumentací

Zdrojem jsou Markdown soubory v `docs/`; navigaci určuje `mkdocs.yml`
v kořeni repozitáře. Novou stránku přidej také do jeho položky `nav`.

Příkazy spouštěj z kořene balíčkového repozitáře `saltstack-wrt`.
Je-li připojen jako submodule v testovacím repozitáři, nejprve spusť
`cd saltstack-wrt`. Potom vytvoř prostředí:

```sh
python -m venv .venv-docs
```

Aktivace v Linuxu / WSL:

```sh
. .venv-docs/bin/activate
```

Aktivace v PowerShellu:

```powershell
.\.venv-docs\Scripts\Activate.ps1
```

Potom nainstaluj závislosti a spusť náhled:

```sh
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

Lokální náhled je na `http://127.0.0.1:8000/` a průběžně reaguje na úpravy.
Statické HTML vytvoříš příkazem:

```sh
python -m mkdocs build --strict
```

Výchozí výstup je v ignorovaném adresáři `site/`. Jiné umístění lze zadat
pomocí `--site-dir /cesta/k/vystupu`. Publikování zatím není nastavené.
Podrobnosti jsou v [oficiálním návodu MkDocs](https://www.mkdocs.org/getting-started/)
a [referenci konfigurace](https://www.mkdocs.org/user-guide/configuration/).
