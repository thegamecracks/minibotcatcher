# minibotcatcher

[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/publish.yml?style=flat-square&logo=uv&label=build)](https://docs.astral.sh/uv/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/docker.yml?style=flat-square&logo=docker&label=docker)](https://docs.astral.sh/uv/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/type-check.yml?style=flat-square&logo=ty&label=types)](https://docs.astral.sh/ty/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/ruff-check.yml?style=flat-square&logo=ruff&label=lints)](https://docs.astral.sh/ruff/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/ruff-format.yml?style=flat-square&logo=ruff&label=style)](https://docs.astral.sh/ruff/)

A small Discord bot to catch specific spam bots.

## Table of Contents

- [minibotcatcher](#minibotcatcher)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
    - [Docker](#docker)
    - [Manual setup (python+pip)](#manual-setup-pythonpip)
    - [Manual setup (uv)](#manual-setup-uv)
  - [Configuration](#configuration)
  - [Intents](#intents)
  - [Usage](#usage)
    - [Permissions](#permissions)
    - [Exemptions](#exemptions)
    - [Filters](#filters)
    - [Actions](#actions)
  - [License](#license)

## Installation

### Docker

To run the latest versioned image:

```sh
$ docker pull ghcr.io/thegamecracks/minibotcatcher
$ docker run --rm -it -e BOT_TOKEN=abc123 minibotcatcher
```

To run the latest development image from main branch:

```sh
$ docker run --rm -it -e BOT_TOKEN=abc123 ghcr.io/thegamecracks/minibotcatcher:main
```

To build and run from source directly:

```sh
$ git clone https://github.com/thegamecracks/minibotcatcher
$ cd minibotcatcher
$ docker build -t minibotcatcher .
$ docker run --rm -it -e BOT_TOKEN=abc123 minibotcatcher
```

### Manual setup (python+pip)

The minimum required [Python](https://www.python.org/) version is **3.14**.
It is highly recommended to install the project and its dependencies
inside a [virtual environment](https://docs.python.org/3/library/venv.html):

```sh
$ git clone https://github.com/thegamecracks/minibotcatcher
$ cd minibotcatcher
$ python -m venv .venv
$ source .venv/bin/activate  # Windows: .venv\Scripts\activate
(.venv) $ pip install --editable .
(.venv) $ echo 'BOT_TOKEN=abc123' > .env  # on Windows, add this file by hand
(.venv) $ minibotcatcher
```

### Manual setup (uv)

If you have Astral [uv](https://docs.astral.sh/uv/) installed,
the setup becomes a bit simpler:

```sh
$ git clone https://github.com/thegamecracks/minibotcatcher
$ cd minibotcatcher
$ echo 'BOT_TOKEN=abc123' > .env  # on Windows, add this file by hand
$ uv run minibotcatcher
```

This method will also install development dependencies including
[jishaku](https://github.com/scarletcafe/jishaku), an extension that allows
the bot owner to run arbitrary Python code and other debugging utilities.

## Configuration

The following environment variables are supported:

- `BOT_TOKEN`:
  the bot token used to login, retrieved from the
  [Discord Developer Portal](https://discord.com/developers/applications).
- `AUDIT_CHANNELS`:
  a comma-separated list of channel IDs for reporting infractions
  (see [Actions](#actions)).
- `SPAM_FILTERS`:
  a comma-separated list of filter names
  (see [Filters](#filters)).
- `SPAM_TIMEOUT_MINUTES`:
  the duration that offenders can be timed out in minutes
  (see [Actions](#actions)).

With manual setup, the bot can automatically load environment variables from a `.env` file.
On Docker, the equivalent would be `docker run --env-file .env minibotcatcher`.

> [!WARNING]
>
> The above configuration options are not yet stable,
> and are subject to change in a future release.

## Intents

Before you start the bot, make sure to enable the **Message Content** intent
for your bot in the [Discord Developer Portal](https://discord.com/developers/applications).
This intent is required for the bot to run and to apply certain spam filters, such as mention spam.

## Usage

When the bot is started, it will print an invite link requesting the relevant
permissions. After using the link to invite the bot to a server, no further action
is required, and the bot will begin watching messages and checking them against
the spam filters.

### Permissions

Four potentially dangerous permissions are suggested in the invite link:

- Moderate Members: allows timing out any bots that trigger a spam filter.
- Manage Messages: allows deleting any offending messages detected by a spam filter.
- Mention Everyone: better allows mentioning the first staff role that has kick or ban permissions.
- Bypass Slowmode: prevents audit messages from being interrupted in slowmode channels.

Each permission can be turned off to disable its corresponding functionality.
For example, if the bot lacks the permissions to timeout or manage messages,
the bot will only post the audit message when a spam filter is triggered.

### Exemptions

Spam filters do not apply to any message that meets any of the following conditions:

- The message was sent to the bot's DMs
- The author is marked as a bot, system, or webhook
- The author has at least one moderation permission (e.g. kick, ban, manage XYZ, mute/deafen/move members, bypass slowmode)
- The author's highest role exceeds the bot's highest role

The last point determines whether the bot is permitted by Discord to apply
moderation actions, like timing out the member. As such, it is recommended to
move the bot's role above member/vanity roles, but stay below staff roles.

### Filters

The following spam filters are implemented:

- Burst spam (`burst`):
  the author must not excessively send messages in a short period.
- Channel spam (`channel`):
  the author must not quickly send messages across multiple channels.
- Mention spam (`mention`):
  the author must not quickly mention other users/roles across multiple messages.

By default, all spam filters are enabled. To select specific filters, the
`SPAM_FILTERS` envvar can be set to a comma-separated list of filter names,
for example, `SPAM_FILTERS=channel,mention`.
This setting applies globally to all servers.

While these filters are currently designed to catch user bots, it is possible that
a real user can trigger the filters. In case this happens, admins with the
Moderate Members permission can reverse a timeout by right-clicking or
long-tapping their username.

### Actions

The following actions can be performed when a bot triggers the spam filter:

1. The offender may be timed out for ten minutes.

   This action is skipped if the bot does not have the Moderate Members permission.

   The `SPAM_TIMEOUT_MINUTES` envvar can be used to change how.
   By default, the timeout is 10 minutes.
   If set to 0, offenders will never be timed out.

2. The offender may have their offending messages deleted.

   Only the specific messages that triggered the filter will be deleted.
   If the bot is not able to delete one or more messages (for example, a channel
   denies the Manage Messages permission), those messages will be left unaffected.

3. A message will be sent to the most recent channel indicating the offender,
   infraction reason, any timeout applied, and any mentionable staff role with
   kick or ban permissions.

   The role mention is determined by the lowest staff role that is permitted
   to kick or ban members. The bot must either have the Mention Everyone permission,
   or the staff role must allow anyone to mention it.
   If no candidate role is found, the server owner will be mentioned instead.

   The `AUDIT_CHANNELS` envvar can be used to change where the message is sent to.
   If it specifies a channel ID matching the server where the infraction occured,
   the message will be sent there instead, along with the most recent offending
   message forwarded. If multiple channels match, the first available channel
   will be used.

## License

This project is written under the [MIT License].

[MIT License]: /LICENSE
