# Evidování spotřeby energií

Webová aplikace pro evidenci stavů měřičů energií (elektřina ve vysokém a nízkém tarifu, plyn, voda) a počítadla výroby FVE. Zobrazuje historii v tabulce s rozdíly, měsíční spotřebu a meziroční porovnání v grafech a doplňuje odhady pro měsíce bez odečtu.

Produkce: **https://spotreba.elvisek.cz**

![Screenshot aplikace](images/screen_spotreba.png)

## 📋 Popis

Aplikace je postavená na Python FastAPI se serverovým vykreslováním šablon Jinja2 a externí databází MySQL/MariaDB. Uživatel zapisuje ruční odečty měřičů, aplikace z nich počítá spotřebu po měsících a letech, hlídá návaznost odečtů (překlep, výměna měřiče) a pro kalendářní měsíce bez odečtu navrhuje odhady, které udržuje v souladu s okolními odečty.

Aplikace je určená pro domácnost, která chce mít přehled o vývoji spotřeby a výroby energie v čase.

## ✨ Funkce

- ✅ **Evidování odečtů** – stavy elektroměru (VT/NT), plynoměru, vodoměru a počítadla FVE s validací; výchozí datum je dnešek, poslední ruční odečet je v polích jen jako nápověda
- ✅ **Kontrola návaznosti** – když je stav nižší než předchozí ruční odečet (nebo vyšší než následující), aplikace se před uložením zeptá; pokles jde rovnou uložit jako výměnu měřiče
- ✅ **Přehled** – tabulka s rozdílem oproti předchozímu záznamu (i na konci stránky), stránkování po 15 záznamech, filtr „Zobrazit pouze odečty“, statistiky, upozornění na chybějící odečet v aktuálním měsíci a export do CSV
- ✅ **Výměna měřiče** – příznak u jednotlivých měřičů; skok stavu se nepočítá jako spotřeba v tabulce, grafech ani meziročním porovnání
- ✅ **Měsíční spotřeba** – rozpočet do kalendářních měsíců podle dní mezi ručními odečty, dvě osy (kWh a m³), odlišení dopočtených měsíců a upozornění na poklesy stavu bez označené výměny
- ✅ **Celkové stavy** – průběh stavů měřičů u všech záznamů, odhady jako duté body
- ✅ **Meziroční porovnání** – spotřeba po kalendářních letech; rozpracovaný rok se srovnává se stejným obdobím loňska, u FVE je vyšší výroba „lepší“
- ✅ **Chybějící data** – návrhy odhadů pro měsíce bez odečtu, přehled mezer, které automaticky doplnit nejde, a kontrola uložených odhadů s hromadným přepočtem
- ✅ **Automatický přepočet odhadů** – po přidání, opravě nebo smazání ručního odečtu se odhady v jeho okolí dopočítají znovu
- ✅ **Tmavý režim a mobil** – přepínač světlého/tmavého režimu, formuláře se na úzké obrazovce skládají pod sebe

## 📖 Použití

### Základní workflow

1. **Nový odečet** – v záložce „Evidovat“ vyplňte datum a stavy všech měřičů (FVE neevidujete = 0) a uložte tlačítkem nebo Ctrl+S / ⌘S. Když stav nenavazuje na okolní ruční odečty, aplikace ukáže varování s volbami *Zpět k úpravě*, *Uložit přesto* a *Uložit jako výměnu měřiče*.
2. **Přehled** – na hlavní stránce jsou záznamy od nejnovějšího s rozdíly. Filtr „Zobrazit pouze odečty“ skryje odhady a u rozdílu ukáže délku intervalu. Tlačítkem „Export CSV“ stáhnete všechny záznamy pro Excel.
3. **Oprava a výměna měřiče** – v editaci záznamu opravíte hodnoty nebo označíte měřič, který byl u odečtu vyměněn (příznak patří na první odečet nového měřiče).
4. **Grafy** – měsíční spotřeba, celkové stavy, volba období a meziroční porovnání.
5. **Chybějící data** – vytvořte odhady pro měsíce bez odečtu a zkontrolujte, že uložené odhady odpovídají odečtům.

## 🧮 Jak aplikace počítá

Výpočty jsou v jednom modulu `app/services/vypocty.py` (čisté funkce pokryté testy):

- **Ruční odečty vs. odhady** – statistiky (měsíce, roky, anomálie) vycházejí jen z ručních odečtů. Odhady (`source = true`) slouží tabulce a z výpočtů přebírají jen příznak výměny měřiče.
- **Rozpočet podle dní** – spotřeba mezi dvěma ručními odečty se rozloží rovnoměrně na dny intervalu `[od, do)` a sečte do kalendářních měsíců a let. Interval 1. 12. → 1. 1. tak patří do prosince.
- **Úplné měsíce** – v měsíčním grafu je hodnota jen u měsíce, který je pro daný měřič pokrytý celý. Probíhající měsíc se ukáže až po dalším odečtu, období grafu (3 měsíce až 3 roky) se počítá v úplných měsících.
- **Dopočtené měsíce** – když mezi dvěma ručními odečty leží celý měsíc bez odečtu, je hodnota označená jako odhad (světlejší sloupec, v tabulce let „≈“).
- **Výměna měřiče** – interval končící odečtem s příznakem výměny není spotřeba. Měsíc, do kterého zasahuje, je u daného měřiče prázdný, a rok s výměnou nejde meziročně srovnat.
- **FVE** – počítadlo je kumulativní; hodnota 0 znamená „neevidováno“. Ve statistikách se nula přemostí k další nenulové hodnotě, v tabulce rozdíl zůstane prázdný.
- **Anomálie** – pokles stavu mezi ručními odečty bez příznaku výměny se ze součtů nevyhazuje (překlep se vyruší s dalším nafouknutým intervalem), jen se na něj upozorní pod grafem.
- **Meziroční porovnání** – rok Y se srovnává se stejným obdobím roku Y−1 (u rozpracovaného roku do stejného dne; 29. 2. se posune na 1. 3.). Srovnání se ukáže jen tehdy, když má měřič pokrytá obě období celá.
- **Odhady chybějících měsíců** – návrh se zakládá k 1. dni měsíce bez odečtu, hodnoty jsou lineární odhad podle dní mezi okolními ručními odečty. Mezeru s výměnou měřiče (nebo bez navazujícího ručního odečtu) aplikace přeskočí a vypíše s důvodem.
- **Přepočet odhadů** – po změně ručního odečtu se v jedné transakci přepočítají odhady mezi předchozím a následujícím ručním odečtem. Úprava samotného odhadu přepočet nespouští; při další změně okolních odečtů se ale přepíše. Starší nesrovnalosti ukáže a opraví „Kontrola uložených odhadů“.

## 🚀 Deployment

### Předpoklady

- Docker a Docker Compose
- Externí MySQL/MariaDB databáze
- Síť `proxy_network` pro reverse proxy (v produkci openresty)

### Docker Compose

```bash
docker compose up -d --build
```

Aplikace poběží na `http://localhost:8080` (port 8080 na hostu → 8000 v kontejneru). Kontejner běží pod uživatelem `appuser` (UID 1000), má healthcheck na `/health` a časovou zónu `Europe/Prague`.

Místo lokálního buildu lze v `docker-compose.yml` použít hotový image z GHCR – zakomentujte `build` a odkomentujte `image: ghcr.io/elvisek2020/web-evidence_spotreby_energii:latest`.

### Konfigurace

Proměnné prostředí se čtou ze souboru `.env` (šablona je v `.env.example`, `.env` se necommituje a do image se nedostane díky `.dockerignore`):

| Proměnná | Povinná | Výchozí | Popis |
|----------|---------|---------|-------|
| `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USER`, `DB_PASSWORD` | ano | – | Připojení k MySQL/MariaDB |
| `TZ` | ne | `Europe/Prague` | Časová zóna – určuje „dnešní“ datum pro validaci odečtů |
| `LOG_LEVEL` | ne | `INFO` | Úroveň logování (`DEBUG`, `INFO`, `WARNING`, …) |
| `ALLOWED_ORIGINS` | ne | prázdné | Čárkou oddělené originy pro CORS; prázdné = CORS vypnutý |

### Databáze a migrace

Schéma se upravuje automaticky při startu aplikace (`app/migrations.py`), ručně se nic nespouští:

1. **Nová instalace** – tabulka `spotreba` vznikne z modelu (sloupce `DOUBLE`, unikátní index na `datum`).
2. **Starší instalace** – doplní se chybějící sloupce (`fve`, `vymena_*`).
3. **Unikátní index na `datum`** – přidá se, jen když v tabulce nejsou duplicitní data. Jinak se do logu zapíše ERROR se seznamem duplicit a index se doplní při dalším startu po jejich odstranění.

### Update aplikace

```bash
docker compose pull      # při použití image z GHCR
docker compose up -d --build
```

Před vydáním zvyšte verzi v `app/static/version.json`. Aplikace ji čte při startu, zobrazuje v zápatí a přidává k adresám CSS a JS (`?v=`), takže prohlížeče po nasazení načtou nové soubory.

### Rollback na konkrétní verzi

V `docker-compose.yml` nastavte konkrétní tag image, např. `ghcr.io/elvisek2020/web-evidence_spotreby_energii:sha-<commit-sha>`.

### GitHub a CI/CD

Po pushi do větve `main` spustí GitHub Actions (`.github/workflows/docker.yml`):

1. **test** – unit testy (`pytest`) v kontejneru `python:3.13-slim`,
2. **build** – jen po úspěšných testech sestaví image pro `linux/amd64` a `linux/arm64` a nahraje ho do GHCR s tagy `latest`, `main` a `sha-<commit-sha>`.

Image je veřejný: `ghcr.io/elvisek2020/web-evidence_spotreby_energii`.

---

## 🔧 Technická dokumentace

### 🏗️ Architektura

- **Backend** – FastAPI; HTML stránky v `routers/pages.py`, JSON API v `routers/spotreba.py`, `grafy.py` a `missing_data.py`. Routery jsou tenké vrstvy nad službami.
- **Služby** – `services/vypocty.py` obsahuje čisté výpočty bez DB, `services/zaznamy.py` operace nad databází (načtení, přepočet odhadů v transakci).
- **Měřiče** – jediná definice v `app/meters.py` (`METERS`: klíč, popisek, jednotka, barva, osa, chování FVE). Šablony, grafy i výpočty je procházejí v cyklu.
- **Frontend** – serverové vykreslení Jinja2 (přehled, formuláře, chybějící data), vanilla JS v `static/js/app.js` (API volání, modální dialogy, toasty), Chart.js pro grafy, Tailwind CSS přes Play CDN.
- **Databáze** – externí MySQL/MariaDB přes SQLAlchemy ORM; schéma spravují migrace při startu.

**Tabulka `spotreba`:**

| Sloupec | Typ | Popis |
|---------|-----|-------|
| `id` | INT | Primární klíč |
| `datum` | DATE, unikátní | Datum odečtu |
| `elektromer_vysoky`, `elektromer_nizky` | DOUBLE | Stav elektroměru VT/NT (kWh) |
| `plynomer`, `vodomer` | DOUBLE | Stav plynoměru a vodoměru (m³) |
| `fve` | DOUBLE, NULL | Kumulativní počítadlo výroby FVE (kWh), 0 = neevidováno |
| `source` | BOOL | `false` = ruční odečet, `true` = automaticky doplněný odhad |
| `vymena_elektromer_vysoky`, `vymena_elektromer_nizky`, `vymena_plynomer`, `vymena_vodomer`, `vymena_fve` | BOOL | U odečtu byl nasazen nový měřič |

Starší instalace mohou mít sloupce měřičů typu `FLOAT` (jednoduchá přesnost); migrace je nemění.

### Technický stack

- **Backend:** Python 3.13, FastAPI 0.141, Starlette 1.7, Pydantic 2.13, SQLAlchemy 2.1, PyMySQL, Uvicorn
- **Frontend:** Jinja2, vanilla JavaScript, Tailwind CSS (Play CDN 3.4), Chart.js 4.5
- **Testy:** pytest
- **Deployment:** Docker, Docker Compose, GitHub Actions, GHCR

### 📁 Struktura projektu

```
web-evidence_spotreby_energii/
├── app/
│   ├── main.py              # FastAPI aplikace, lifespan, chybové stránky, /health
│   ├── database.py          # Připojení k databázi
│   ├── models.py            # SQLAlchemy model Spotreba
│   ├── schemas.py           # Pydantic schémata API
│   ├── meters.py            # Definice měřičů (METERS)
│   ├── migrations.py        # Úpravy schématu při startu
│   ├── templating.py        # Jinja2: verze, globální proměnné, filtry
│   ├── formatovani.py       # České formátování čísel a dat
│   ├── services/
│   │   ├── vypocty.py       # Čisté výpočty (rozdíly, měsíce, roky, odhady, kontroly)
│   │   └── zaznamy.py       # Operace nad DB (načtení, přepočet odhadů)
│   ├── routers/
│   │   ├── pages.py         # HTML stránky
│   │   ├── spotreba.py      # API záznamů, kontrola návaznosti, CSV export
│   │   ├── grafy.py         # API grafů a meziročního porovnání
│   │   └── missing_data.py  # API návrhů a přepočtu odhadů
│   ├── templates/           # Jinja2 šablony (_makra.html = sdílená makra)
│   └── static/              # style.css, app.js, version.json
├── tests/test_vypocty.py    # Unit testy výpočetní vrstvy
├── scripts/testovaci_data.py  # Naplnění lokální testovací instance
├── docker-compose.yml       # Produkční compose
├── docker-compose.test.yml  # Lokální test: aplikace + MariaDB
├── Dockerfile
├── requirements.txt / requirements-dev.txt
└── README.md
```

### 🔧 API dokumentace

**HTML stránky:**

- `GET /` – přehled (parametry `strana`, `jen_odecty=1`)
- `GET /evidovat` – nový odečet
- `GET /edit/{id}` – editace záznamu
- `GET /grafy` – grafy a meziroční porovnání
- `GET /missing-data` – chybějící data a kontrola odhadů

**Záznamy:**

- `GET /api/spotreba` – seznam s rozdíly, nejnovější první (parametry `limit` 1–100, výchozí 12; `offset`; `source_filter` – `false` = jen ruční odečty, `true` = jen odhady)
- `GET /api/spotreba/count` – počet záznamů (parametr `source_filter`)
- `GET /api/spotreba/{id}` – jeden záznam
- `POST /api/spotreba` – nový záznam; odpověď obsahuje `prepocteno_odhadu`
- `PUT /api/spotreba/{id}` – úprava (posílají se jen měněná pole, `null` není povolený)
- `DELETE /api/spotreba/{id}` – smazání; odpověď obsahuje `prepocteno_odhadu`
- `POST /api/spotreba/kontrola` – varování k odečtu před uložením (`{varovani: [{meric, typ, zprava, …}]}`), nic neukládá
- `GET /api/spotreba/export.csv` – všechny záznamy jako CSV (středník, desetinná čárka, UTF-8 s BOM)

**Grafy:**

- `GET /api/grafy/monthly-diff?period=…` – spotřeba po kalendářních měsících
- `GET /api/grafy/data?period=…` – stavy měřičů u jednotlivých záznamů
- `GET /api/grafy/yoy` – roky od nejnovějšího s pokrytím a srovnáním se stejným obdobím loňska
- `GET /api/grafy/summary` – počty záznamů a rozsah dat

Oba grafové endpointy vracejí stejný tvar `{popisky, popisky_dlouhe, rady: {meric: {label, jednotka, barva, osa, hodnoty, odhad, poznamka}}, anomalie}`. `null` v hodnotách přerušuje řadu, důvod je v `poznamka`. Parametr `period` přijímá `3months`, `6months`, `year`, `2years`, `3years` a `all` (výchozí). U měsíčního grafu znamená počet posledních úplných měsíců, u stavů počet dní zpět.

**Chybějící data:**

- `GET /api/missing-data/suggestions` – návrhy odhadů, nejnovější první
- `POST /api/missing-data/create` – vytvoří všechny návrhy
- `POST /api/missing-data/create-single` – vytvoří návrh k danému datu (`{datum}`, hodnoty dopočítá server)
- `GET /api/missing-data/prepocet` – náhled odhadů, které neodpovídají ručním odečtům (změny a konflikty)
- `POST /api/missing-data/prepocet` – přepočítá všechny uložené odhady

**Ostatní:** `GET /health` – stav aplikace a připojení k DB, včetně verze.

Chyby API vracejí `{"detail": "…"}` s českou hláškou, u validace (422) např. `Datum: nesmí být v budoucnosti; Počítadlo FVE: pole je povinné`.

### 💻 Vývoj

**Unit testy** (bez databáze):

```bash
uv run --no-project --python 3.13 --with-requirements requirements-dev.txt pytest -q
```

**Lokální testovací instance** – aplikace s prázdnou MariaDB, bez vazby na produkční databázi:

```bash
docker compose -f docker-compose.test.yml up -d --build
python3 scripts/testovaci_data.py
```

Aplikace poběží na `http://localhost:18080`. Skript `testovaci_data.py` zapisuje jen na localhost a jen do prázdné databáze; data obsahují mezeru bez odečtu, výměnu vodoměru, zahájení evidence FVE, překlep a zastaralý odhad. Úklid:

```bash
docker compose -f docker-compose.test.yml down -v
```

**Přidání měřiče** – doplnit sloupce do `models.py`, `schemas.py` a migrace do `migrations.py`, záznam do `METERS` v `meters.py`. Šablony, grafy a výpočty ho převezmou samy.

**Debugging** – `LOG_LEVEL=DEBUG` v `.env`, logy kontejneru přes `docker compose logs -f`.

### 🎨 UI/UX

- Karty s bílým (v tmavém režimu šedým) pozadím, stínem a zaoblenými rohy, Tailwind utility třídy přímo v šablonách
- Pattern titulku „Evidování spotřeby - Záložka“
- Potvrzení akcí přes modální dialog (`showConfirm` v `app.js`), výsledky akcí jako toasty, i po přesměrování
- Opakované části šablon jsou v `templates/_makra.html` (pole měřiče, buňka tabulky, stránkování)
- `static/css/style.css` obsahuje jen doplňková obyčejná pravidla – Tailwind Play CDN nezpracovává `@apply` v externích souborech
- Přístupnost: skip link, `aria-current` v navigaci, focus trap v dialogu, respektování `prefers-reduced-motion`

### 🔒 Bezpečnost

- **Aplikace nemá přihlášení.** Produkce na `spotreba.elvisek.cz` je záměrně veřejná, a to včetně API pro zápis a mazání záznamů. Kdo zná adresu, může data číst i měnit. Pokud by to přestalo vyhovovat, nabízí se ochrana na reverse proxy (Access List / basic auth) nebo přihlášení podle standardu `web-app-auth`.
- Port 8080 je v `docker-compose.yml` publikovaný na všech rozhraních hostu, aplikace je tedy dostupná i mimo reverse proxy.
- SQL přes SQLAlchemy ORM (parametrizované dotazy), validace vstupů Pydantic schématy, autoescaping Jinja2
- Bezpečnostní hlavičky: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`
- Kontejner běží pod non-root uživatelem; `.dockerignore` drží `.env` a `.git` mimo image

### 🐛 Známá omezení a plánovaná vylepšení

- Tailwind CSS se načítá z Play CDN (kompilace v prohlížeči, závislost na internetu); do budoucna build CSS při sestavení image nebo přechod na `app.css` a HTMX podle standardu `web-app-stack` / `web-app-ui`
- Starší instalace mohou mít sloupce měřičů `FLOAT` s jednoduchou přesností (u stavů nad ~130 000 šum v setinách); případná změna na `DOUBLE` je ruční `ALTER TABLE`
- Ručně upravený odhad se při další změně okolních ručních odečtů přepíše – skutečný odečet je potřeba převést na ruční (zrušit „Automaticky doplněný záznam“)
- Mezeru s výměnou měřiče je potřeba doplnit ručně, automatický návrh ji přeskočí
- Probíhající měsíc se v měsíčním grafu ukáže až po dalším odečtu

### 📚 Další zdroje

- [FastAPI dokumentace](https://fastapi.tiangolo.com/)
- [SQLAlchemy dokumentace](https://docs.sqlalchemy.org/)
- [Tailwind CSS dokumentace](https://tailwindcss.com/docs)
- [Chart.js dokumentace](https://www.chartjs.org/docs/)
- [Docker dokumentace](https://docs.docker.com/)
- [GitHub Actions dokumentace](https://docs.github.com/en/actions)

## 📄 Licence

Tento projekt je vytvořen pro vzdělávací účely.
