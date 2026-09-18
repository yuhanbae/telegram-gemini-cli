# Telegram Gemini CLI

A lightweight, Termux-friendly Telegram wrapper around the **local [Gemini CLI](https://geminicli.com)**.
Send a message in Telegram and it is passed to `gemini` on your device;
the answer is sent back, chunked to fit Telegram's limits.

[![⚡ Buy Me a Coffee — Speed Wallet (Lightning)](https://img.shields.io/badge/⚡%20Buy%20Me%20a%20Coffee-Speed%20Wallet%20%28Lightning%29-lightningblue)
](#donations)

## Architecture

```
Telegram Bot API
      │  (long polling)
      ▼
Python bot (python-telegram-bot)
      │  async subprocess, per-chat session UUID
      ▼
local Gemini CLI (gemini -p … non-interactive)
      │
      ▼
Gemini API → stdout → chunked reply in Telegram
```

No database, no extra services: per-chat session state is kept in
`chat_data` (in-memory, keyed by Telegram chat id) and maps to a
UUID used with the CLI's `--session-id` / `--resume` flags.

## Prerequisites

- Python 3.10+
- [Gemini CLI](https://geminicli.com/docs/installation/) installed and
  authenticated (`gemini` on PATH, e.g. via `npm i -g @google/gemini-cli`)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

> **Termux note:** headless runs outside a trusted directory need
> `--skip-trust`. The easiest way is setting `GEMINI_EXTRA_ARGS=--skip-trust`
> in `.env` (supported by this wrapper).

## Installation

```bash
git clone https://github.com/yuhanbae/telegram-gemini-cli
cd telegram-gemini-cli

python3 -m venv .venv          # optional, works fine without on Termux
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env
```

## Configuration (.env)

| Variable | Default | Meaning |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — (required) | Bot token from @BotFather |
| `GEMINI_COMMAND` | `gemini` | Command used to launch Gemini CLI |
| `GEMINI_MODEL` | *(empty = CLI default)* | e.g. `gemini-2.5-flash` |
| `GEMINI_TIMEOUT` | `300` | Seconds before a Gemini call is killed |
| `GEMINI_EXTRA_ARGS` | *(empty)* | Extra CLI args, e.g. `--skip-trust` |
| `TELEGRAM_ALLOWED_USER_IDS` | *(empty = everyone)* | Comma-separated user ids; others are ignored |

Never commit `.env` — it is git-ignored.

## Running

Linux / Termux:

```bash
cd ~/telegram-gemini-cli
python3 -m src.main            # starts long polling
```

Run it persistently on Termux:

```bash
python3 -m src.main &
# or: nohup python3 -m src.main > gemini-bot.log 2>&1 &
```

## Telegram commands

| Command | Effect |
|---|---|
| `/start`, `/help` | Usage + donate button |
| `/new` | Creates a fresh session UUID for this chat |
| `/resume [uuid\|index]` | Map this chat to an existing Gemini CLI session (`latest` works too, but note it refers to the newest session of *this project directory*, shared across chats) |
| `/sessions` | Lists sessions saved for the project directory the bot runs in |
| `/status` | Shows CLI, model, timeout and this chat's session |
| `/donate` | PayPal donation button |

Any other text message is sent to Gemini CLI with that chat's session,
giving you multi-turn context per chat.

## Donations

☕ **Buy Me a Coffee — Speed Wallet (Lightning):**

The bot's `/donate`, `/start` and `/help` menus show a
**⚡ Buy Me a Coffee (Speed Wallet)** button — a static Lightning invoice
(`lightning:lnbc...`). Open it in any Lightning wallet app (Speed Wallet,
Phoenix, Alby, Bitcoin Core …) by tapping the button in Telegram.

(We previously linked PayPal, but PayPal does not support donations in this
region, so the Speed Wallet invoice is the primary donation route.)

Note: `.github/FUNDING.yml` only supports a fixed set of platforms and cannot
carry a `lightning:` URI, so it points to this page instead.

## Troubleshooting

- **"Gemini CLI is not running in a trusted directory"** — set
  `GEMINI_EXTRA_ARGS=--skip-trust` in `.env` (or set
  `GEMINI_CLI_TRUST_WORKSPACE=true` in the environment).
- **node-pty MODULE_NOT_FOUND warnings** on Termux — harmless; they are
  filtered out of error messages automatically.
- **Daily quota exhausted** — the free Gemini CLI tier has a daily
  limit; the CLI reports `TerminalQuotaError`. Wait for the next day or
  use a paid API key / different model.
- **`/sessions` shows sessions of the wrong project** — Gemini CLI stores
  sessions per project directory; the bot always runs the CLI in its own
  working directory (`~/telegram-gemini-cli`).
- **Bot does not reply** — check `TELEGRAM_BOT_TOKEN`, that the process
  is running (`python3 -m src.main`), and that your user id is in
  `TELEGRAM_ALLOWED_USER_IDS` if that variable is set.

## License

[MIT](LICENSE)

## tegegm shortcut (Termux)

For convenience on Termux, a `tegem` launcher lives at
`/data/data/com.termux/files/usr/bin/tegem` (a copy is kept in `bin/tegem`).
It:

- on first run, asks for the bot token (hidden) and optionally your user id(s),
  verifies the token via `getMe`, and saves everything to `.env` (chmod 600)
- refuses to start a second instance (flock) to avoid Telegram 409 Conflict
- then starts the bot in the foreground

```
tegem                      # start (asks for token on first run)
nohup tegegm > ~/telegram-gemini-cli/logs/bot.log 2>&1 &   # background
```

To reinstall the shortcut after cloning elsewhere:

```
cp bin/tegem /data/data/com.termux/files/usr/bin/tegem
chmod +x /data/data/com.termux/files/usr/bin/tegem
```
