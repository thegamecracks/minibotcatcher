import importlib.metadata
import logging
import sys
from contextlib import suppress

import discord
from discord.ext import commands

log = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            help_command=None,
            intents=discord.Intents(
                guilds=True,
                messages=True,
            ),
            max_messages=None,
            strip_after_prefix=True,
        )

    async def login(self, token: str) -> None:
        try:
            return await super().login(token)
        except discord.LoginFailure:
            log.critical("Discord refused our login! Please check BOT_TOKEN.")
            sys.exit(1)
        except discord.PrivilegedIntentsRequired:
            log.critical(
                "Missing privileged intents! "
                "You must enable the Message Content intent."
            )
            sys.exit(1)

    async def setup_hook(self) -> None:
        await self.load_extension("minibotcatcher.antispam")
        await self._maybe_load_jishaku()

        invite_link = self.get_standard_invite()
        log.info("Invite link:\n    %s", invite_link)

    async def _maybe_load_jishaku(self) -> None:
        with suppress(importlib.metadata.PackageNotFoundError):
            version = importlib.metadata.version("jishaku")
            await self.load_extension("jishaku")
            log.info("Loaded jishaku extension (v%s)", version)

    def get_standard_invite(self) -> str:
        assert self.application is not None
        return discord.utils.oauth_url(
            self.application.id,
            scopes=("bot",),
            permissions=discord.Permissions(
                read_messages=True,
                send_messages=True,
                send_messages_in_threads=True,
                embed_links=True,
                attach_files=True,
                # Dangerous permissions
                manage_messages=True,
                mention_everyone=True,
                moderate_members=True,
            ),
        )


class Context(commands.Context[Bot]): ...
