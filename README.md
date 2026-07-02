# minibotcatcher

[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/publish.yml?style=flat-square&logo=uv&label=build)](https://docs.astral.sh/uv/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/type-check.yml?style=flat-square&logo=ty&label=types)](https://docs.astral.sh/ty/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/ruff-check.yml?style=flat-square&logo=ruff&label=lints)](https://docs.astral.sh/ruff/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/minibotcatcher/ruff-format.yml?style=flat-square&logo=ruff&label=style)](https://docs.astral.sh/ruff/)

A small Discord bot to catch specific spam bots.

## Installation

### Docker

To run the latest image:

```sh
$ docker pull ghcr.io/thegamecracks/minibotcatcher
$ docker run --rm -it -e BOT_TOKEN=abc123 minibotcatcher
```

Alternatively, to build images from source:

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
$ # optional: uv python install 3.14
$ uv run minibotcatcher
```

This method will also install development dependencies including
[jishaku](github.com/scarletcafe/jishaku), an extension that allows
the bot owner to run arbitrary Python code and other debugging utilities.

## Configuration

The following environment variables are used for configuration:

- `BOT_TOKEN`: the token used to start the bot.
- `AUDIT_CHANNELS`: a comma-separated list of channel IDs for reporting infractions (see [Actions](#actions)).

For manual setup, the bot can load environment variables from a `.env` file.
On Docker, the equivalent would be `docker run --env-file .env minibotcatcher`.

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

Three potentially dangerous permissions are suggested in the invite link:

- Moderate Members: allows timing out any bots that trigger a spam filter.
- Manage Messages: allows deleting any offending messages detected by a spam filter.
- Mention Everyone: better allows mentioning the first staff role that has kick or ban permissions.

Each permission can be turned off to disable its corresponding functionality.
With no dangerous permissions, the bot will only post a message indicating
when a spam filter is triggered.

### Exempted Users

Spam filters do not apply to anyone that has meets any of the following conditions:

- The author sent their message to the bot's DMs
- The author is marked as a bot, system, or webhook
- The author has any moderation permission (e.g. kick, ban, manage XYZ, mute/deafen/move members, bypass slowmode)
- The author's highest role exceeds the bot's highest role

The last point actually determines whether Discord will allow the bot to apply
moderation actions like timing out the member. As such, it is recommended to
move the bot's role above most member/vanity roles, but stay below staff roles.

### Filters

The following spam filters are implemented:

- Burst spam: the author must not quickly send messages across multiple channels.
- Mention spam: the author must not mention multiple

While these filters are designed only to catch user bots, it is possible that
a real user can trigger the filters. In case this happens, admins with the
Moderate Members permission can reverse a timeout by right-clicking or
long-tapping their username.

### Actions

The following actions can be performed when a bot triggers the spam filter:

1. The offender may be timed out for ten minutes.
2. The offender may have their offending messages deleted.
3. A message will be sent to the most recent channel indicating the offender,
   infraction reason, any timeout applied, and any mentionable staff role with
   kick or ban permissions.

   The `AUDIT_CHANNELS` envvar can be used to change where the message is sent to.
   If it specifies a channel ID matching the server where the infraction occured,
   the message will be sent there instead, along with the most recent offending
   message forwarded. If multiple channels match, the first available channel
   will be used.

For (1), this action is skipped if the bot does not have the Moderate Members permission.

For (2), only the specific messages that triggered the filter will be deleted.
If the bot is not able to delete one or more messages (for example, a channel
denies the Manage Messages permission), they will be ignored.

For (3), the lowest staff role that is permitted to kick or ban members is chosen.
The bot must either have the Mention Everyone permission, or the staff role
must allow anyone to mention. If no candidate role is found, the server owner
will be mentioned instead.

## License

This project is written under the [MIT License].

[MIT License]: /LICENSE
