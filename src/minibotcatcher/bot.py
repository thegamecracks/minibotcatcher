import logging
import sys

import discord
from discord.ext import commands

from . import __version__, ext

log = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            activity=discord.Game(f"v{__version__}"),
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
                "Missing privileged intents! Please check the Discord Developer Portal."
            )
            sys.exit(1)

    async def setup_hook(self) -> None:
        log.info("Running version: v%s", __version__)
        await ext.load_extensions(self)

        invite_link = self.get_standard_invite()
        log.info("Invite link:\n    %s", invite_link)

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
                add_reactions=True,
                # Dangerous permissions
                bypass_slowmode=True,
                manage_messages=True,
                mention_everyone=True,
                moderate_members=True,
            ),
        )


class Context(commands.Context[Bot]): ...
