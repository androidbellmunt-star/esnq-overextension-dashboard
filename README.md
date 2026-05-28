# ES/NQ Overextension Dashboard

Free-stack deployment using:
- GitHub Pages for the frontend dashboard
- GitHub Actions for daily refresh
- Yahoo Finance via yfinance for daily data
- Telegram bot for alerts

## What the regime uses
- HYG / IEF ratio as a credit-risk proxy
- VIX and VXN as index volatility stress proxies
- USDJPY as a carry-stress proxy

## What the overextension model uses
- QQQ vs SPY relative performance (dispersion)
- XLK vs XLP leadership
- SMH vs SPY leadership concentration
- QQQ / SPY extension vs 5-day mean
- Realized vol and VXN-VIX spread

## Setup steps
1. Create a new GitHub repo, for example: `esnq-overextension-dashboard`
2. Upload all files in this folder to the repo root.
3. In GitHub, go to Settings -> Pages -> Build and deployment -> Deploy from a branch.
4. Select `main` branch and `/ (root)`.
5. In GitHub, go to Settings -> Secrets and variables -> Actions.
6. Add these repository secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
7. Run the workflow manually once from Actions -> Daily dashboard update.
8. Your site will publish at: `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/dashboard.html`

## Chat ID
You still need to provide your Telegram `chat_id`.
After messaging your bot once, open:
`https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates`
and find your numeric `chat.id`.

## Notes
This is v1 and uses free proxies rather than full institutional credit and options datasets.