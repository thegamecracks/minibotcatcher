import datetime
import logging
from typing import Callable

import discord
from discord.ext import commands

from minibotcatcher.bot import Bot

from .filters import (
    SpamContext,
    SpamContextCache,
    SpamDetection,
    check_burst_spam,
    check_mention_spam,
)

ADMIN_PERMISSIONS = discord.Permissions(
    kick_members=True,
    ban_members=True,
    administrator=True,
    manage_channels=True,
    manage_guild=True,
    manage_messages=True,
    mute_members=True,
    deafen_members=True,
    move_members=True,
    manage_nicknames=True,
    manage_roles=True,
    manage_webhooks=True,
    manage_expressions=True,
    manage_events=True,
    manage_threads=True,
    moderate_members=True,
    bypass_slowmode=True,
)

log = logging.getLogger(__name__)


def _is_mod_role(role: discord.Role) -> bool:
    return (
        not role.is_default()
        and not role.is_integration()
        and not role.is_bot_managed()
        and bool(
            role.permissions
            & discord.Permissions(
                kick_members=True,
                ban_members=True,
            )
        )
        and (role.mentionable or role.guild.me.guild_permissions.mention_everyone)
    )


class AntiSpam(commands.Cog):
    filters: list[Callable[[SpamContext], SpamDetection | None]]

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.context_cache = SpamContextCache(
            message_period=datetime.timedelta(minutes=10),
        )
        self.filters = [
            check_burst_spam,
            check_mention_spam,
        ]

    @commands.Cog.listener("on_message")
    async def apply_spam_filters(self, message: discord.Message) -> None:
        if message.guild is None:
            return

        assert isinstance(message.author, discord.Member)
        if self.is_admin(message.author):
            return

        context = self.context_cache.get(message)
        if context is None:
            return

        for func in self.filters:
            detection = func(context)
            if detection is not None:
                await self.take_action_on_detection(detection)
                self.context_cache.pop(message)
                return

    def is_admin(self, author: discord.Member) -> bool:
        if author.top_role >= author.guild.me.top_role:
            return True
        elif author.guild_permissions & ADMIN_PERMISSIONS:
            return True
        elif author.bot:
            return True
        return False

    async def take_action_on_detection(self, detection: SpamDetection) -> None:
        timed_out_until = await self.timeout_offender(detection)
        await self.send_audit_message(detection, timed_out_until=timed_out_until)
        await self.delete_offending_messages(detection)

    async def timeout_offender(
        self, detection: SpamDetection
    ) -> datetime.datetime | None:
        if not detection.guild.me.guild_permissions.moderate_members:
            return

        duration = datetime.timedelta(minutes=10)
        timed_out_until = discord.utils.utcnow() + duration
        log.info("Timing out %s for %s", detection.author, duration)
        await detection.author.timeout(timed_out_until, reason=detection.reason)
        return timed_out_until

    async def send_audit_message(
        self,
        detection: SpamDetection,
        *,
        timed_out_until: datetime.datetime | None,
    ) -> None:
        channel = detection.audit_channel
        if channel is None:
            return

        content = []

        mention = detection.author.mention
        if timed_out_until is not None:
            timestamp_f = discord.utils.format_dt(timed_out_until, style="f")
            content.append(
                f"⚠️ {mention} has been timed out until {timestamp_f} "
                f"(reason: {detection.reason})."
            )
        else:
            content.append(
                f"⚠️ {mention} triggered a spam filter (reason: {detection.reason})."
            )

        mod_role = self.get_mod_role(detection.guild)
        if mod_role is not None:
            has = "has" if not mod_role.name.endswith("s") else "have"
            content.append("")
            content.append(f"The {mod_role.mention} {has} been alerted for review.")

        log.info("Sending audit message to %s", channel)
        await channel.send(
            "\n".join(content),
            allowed_mentions=discord.AllowedMentions(everyone=False, users=False),
        )

    async def delete_offending_messages(self, detection: SpamDetection) -> None:
        deleteable = [
            message
            for message in detection.messages
            if message.channel.permissions_for(detection.guild.me).manage_messages
        ]
        if not deleteable:
            return

        log.info("Deleting %d messages from %s", len(deleteable), detection.author)
        for message in deleteable:
            await message.delete(delay=0)

    def get_mod_role(self, guild: discord.Guild) -> discord.Role | None:
        return discord.utils.find(_is_mod_role, guild.roles)
