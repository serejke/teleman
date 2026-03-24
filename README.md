# teleman

CLI client for Telegram built on [Telethon](https://docs.telethon.dev/).

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Accounts

Each account is a pair of files in `accounts/`:

```
accounts/
  15551234567.json      # API credentials (app_id, app_hash, phone)
  15551234567.session   # Telethon session file
```

The JSON file needs at least these fields:

```json
{
  "app_id": 12345,
  "app_hash": "your_api_hash",
  "phone": "+15551234567"
}
```

On first run, Telethon will prompt for the login code to create the session file.

## Usage

```bash
# Run with a specific account
uv run python -m teleman --account 15551234567

# Run without args to pick from available accounts
uv run python -m teleman
```

## Commands

| Command                      | Description                                              |
| ---------------------------- | -------------------------------------------------------- |
| `/me`                        | Show current account info                                |
| `/chats`                     | List recent dialogs                                      |
| `/chat <user>`               | Open a chat with a user or group                         |
| `/add <user>`                | Add contact                                              |
| `/contacts`                  | List contacts                                            |
| `/nuke <user>`               | Delete all messages and remove chat                      |
| `/privacy`                   | Show privacy settings                                    |
| `/privacy_set <key> <level>` | Set a privacy key to `everyone`, `contacts`, or `nobody` |
| `/lockdown`                  | Set all privacy to `nobody`                              |
| `/settings`                  | Show security and privacy summary                        |
| `/report <user>`             | Report a user for abuse                                  |
| `/export <user>`             | Export chat history to JSON                              |
| `/export_list`               | List exported chats                                      |
| `/quit`                      | Exit                                                     |

`<user>` can be a numeric Telegram ID (e.g. `123456789`) or a username (e.g. `@alice`).

## Proxy

Create `accounts/proxies.json` to configure per-account proxies. Every account must have an entry — use `null` for direct connections.

```json
{
  "15551234567": {
    "type": "http",
    "addr": "proxy.example.com",
    "port": 8080,
    "username": "user",
    "password": "secret"
  },
  "15559876543": null
}
```

Supported types: `http`, `socks5`, `socks4`. `username` and `password` are optional.

## Configuration

Optionally create a `.env` to override the accounts directory:

```
ACCOUNTS_DIR=accounts
```
