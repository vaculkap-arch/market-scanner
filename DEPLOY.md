# Online deploy — GitHub + Streamlit Community Cloud

Tento návod nasadí Market Scanner **zadarmo**:
- **GitHub Actions** = automatický scan + Gmail alerty
- **Streamlit Community Cloud** = webový dashboard

Lokálny PC nie je potrebný na alerty. Dashboard bude na `https://….streamlit.app`.

---

## 0. Bezpečnosť (urob pred pushom)

V `.env` / chate už boli citlivé údaje. Pred online deployom:

1. **Gmail App Password** — v Google Account vytvor nový App Password a starý zruš.
2. **Telegram bot token** — v @BotFather `/revoke` a vytvor nový token (aj keď chat ID nepoužívaš).

Do gitu **nikdy** nedávaj `.env`.

---

## 1. Vytvor GitHub repo

1. Choď na [https://github.com/new](https://github.com/new).
2. Názov: `market-scanner`.
3. Visibility: **Private** (odporúčané).
4. **Nevytváraj** README / .gitignore (projekt už má svoje súbory).
5. Create repository.

### Push z PC (PowerShell)

Ak ešte nemáš Git nainštalovaný: [https://git-scm.com/download/win](https://git-scm.com/download/win).

```powershell
cd C:\Users\VACA\Projects\market-scanner

# ak ešte nie je git init (už môže byť hotový):
git init
git branch -M main
git add .
git status
# Skontroluj, že .env NIE JE v zozname!
git commit -m "Initial commit: market scanner + online deploy"

git remote add origin https://github.com/TVOJ_USERNAME/market-scanner.git
git push -u origin main
```

Nahraď `TVOJ_USERNAME` svojím GitHub menom.

---

## 2. GitHub Secrets (pre Actions / Gmail)

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Príklad / poznámka |
|--------|---------------------|
| `GMAIL_ADDRESS` | `tvoj.email@gmail.com` |
| `GMAIL_APP_PASSWORD` | 16-znakový App Password (medzery môžeš nechať) |
| `GMAIL_TO` | kam majú chodiť alerty (často rovnaký email) |

Voliteľné: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DISCORD_WEBHOOK_URL`, `ALPHA_VANTAGE_API_KEY`.

### Predvolené nastavenia scanu (v workflow)

V [`.github/workflows/scan.yml`](.github/workflows/scan.yml) je prednastavené:

- `WATCHLIST_SOURCE=sp500` (rýchlejší scan, šetrí free minúty)
- `GMAIL_MIN_SCORE=80`, `GMAIL_MIN_TIER=A`
- Cron: každú hodinu Po–Pi 14:00–21:00 UTC

Ak chceš Russell 2000, zmeň v `scan.yml` riadok `WATCHLIST_SOURCE: sp500` na `russell2000` a commitni.

### Manuálny test scanu

Repo → **Actions** → **Market Scan** → **Run workflow**.

Po úspechu by sa mali commitnúť `config/leaderboard.json` a `config/last_scan.json`.

---

## 3. Streamlit Community Cloud (dashboard)

1. Choď na [https://share.streamlit.io](https://share.streamlit.io) a prihlás sa cez GitHub.
2. **New app**:
   - Repository: `TVOJ_USERNAME/market-scanner`
   - Branch: `main`
   - Main file: `app.py`
3. **Advanced settings → Secrets** — vlož TOML (rovnaké hodnoty ako Secrets, bez úvodzoviek okolo hesla ak nie sú potrebné):

```toml
WATCHLIST_SOURCE = "sp500"
SCAN_MODE = "bullish"
BULLISH_MIN_SCORE = "60"
GMAIL_MIN_SCORE = "80"
GMAIL_MIN_TIER = "A"
GMAIL_COOLDOWN_HOURS = "24"
GMAIL_ADDRESS = "tvoj.email@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
GMAIL_TO = "tvoj.email@gmail.com"
MARKET_HOURS_ONLY = "true"
REGIME_FILTER = "true"
FILTER_EXTENDED = "true"
ENABLE_SENTIMENT = "true"
```

4. **Deploy**.

Dashboard URL bude typu: `https://market-scanner-xxxx.streamlit.app`.

Po každom Actions scane (commit leaderboardu) Streamlit Cloud zvyčajne znova načítá repo — v tabuľke uvidíš nové tickery.

---

## 4. Checklist

- [ ] Nový Gmail App Password + Telegram revoke
- [ ] Repo na GitHub (private)
- [ ] `.env` nie je v gite (`git status` to potvrdí)
- [ ] Actions Secrets nastavené
- [ ] Workflow **Market Scan** prebehol OK
- [ ] Streamlit app beží a Secrets sú vyplnené
- [ ] (Voliteľné) vypnúť Windows autostart: `scripts\uninstall_autostart.ps1`

---

## Obmedzenia free tieru

- GitHub Actions majú mesačný limit minút — `sp500` je bezpečnejší než `russell2000`.
- Tlačidlo „Spustiť scan“ v dashboarde na Cloude môže timeoutnúť; hlavný scan je Actions.
- Súbory zapísané len v Streamlit runtime zmiznú — trvalé výsledky idú cez commit z Actions.
