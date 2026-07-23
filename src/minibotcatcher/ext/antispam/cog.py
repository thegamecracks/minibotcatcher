import datetime
import logging
from collections import defaultdict
from collections.abc import Iterable
from contextlib import suppress
from typing import assert_never

import discord
from discord.ext import commands

from minibotcatcher.bot import Bot, Context

from .audit import AuditMessagesDisabled, NoAuditChannel, create_audit_messages
from .env import (
    AUDIT_CHANNELS,
    AUDIT_MESSAGES,
    DEBUG_SKIP_ADMIN_CHECK,
    SPAM_FILTERS,
    SPAM_TIMEOUT_MINUTES,
    AuditMessageMode,
)
from .filters import (
    SpamContextCache,
    SpamDetection,
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
                administrator=True,
                kick_members=True,
                ban_members=True,
            )
        )
        and (role.mentionable or role.guild.me.guild_permissions.mention_everyone)
    )


async def _try_bulk_delete_messages(all_messages: Iterable[discord.Message], /) -> None:
    """Delete the given messages using the bulk delete endpoint if possible,
    and fallback to single delete otherwise.

    This does *not* check for permissions before deletion.

    :raises discord.HTTPException: An error occurred while deleting messages.

    """
    # Group messages by channel and de-duplicate them
    # (discord will return an HTTP 400 if we give any duplicates)
    channel_messages: dict[int, dict[int, discord.Message]] = defaultdict(dict)
    for m in all_messages:
        channel_messages[m.channel.id][m.id] = m

    supports_bulk_delete = (
        discord.StageChannel,
        discord.TextChannel,
        discord.Thread,
        discord.VoiceChannel,
    )

    for group in channel_messages.values():
        group = list(group.values())
        channel = group[0].channel

        # Ideally we'd bulk delete messages up to 2 weeks old, 100 at a time,
        # and fallback to regular delete for remaining messages...
        # But realistically, we only need to clean up a dozen messages at once
        if 2 <= len(group) <= 100 and isinstance(channel, supports_bulk_delete):
            try:
                await channel.delete_messages(group)
            except discord.Forbidden:
                raise  # expect single delete to fail as well
            except discord.HTTPException:
                # One or more messages were likely too old
                log.warning(
                    "Failed to bulk delete messages, falling back to slow delete. "
                    "Expect to be rate limited."
                )
            else:
                continue

        for m in group:
            with suppress(discord.NotFound):
                await m.delete()


class AntiSpam(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.context_cache = SpamContextCache(
            message_period=datetime.timedelta(minutes=1),
        )

    @commands.Cog.listener("on_message")
    async def apply_spam_filters(self, message: discord.Message) -> None:
        if not self.can_moderate_message(message):
            return

        async with self.context_cache.acquire(message) as context:
            detection: SpamDetection | None = None
            for check_spam in SPAM_FILTERS.values():
                detection = check_spam(context)
                if detection is not None:
                    break

            if detection is None:
                return

            self.context_cache.remove(context)
            await self.take_action_on_detection(detection)

    def can_moderate_message(self, message: discord.Message) -> bool:
        if message.guild is None:
            return False
        elif message.webhook_id is not None:
            return False  # came from a webhook

        assert isinstance(message.author, discord.Member)
        author = message.author

        if author.bot or author.system:
            return False

        if DEBUG_SKIP_ADMIN_CHECK:
            pass
        elif author.top_role >= author.guild.me.top_role:  # noqa: SIM114
            return False
        elif author.guild_permissions & ADMIN_PERMISSIONS:
            return False

        return True

    async def take_action_on_detection(self, detection: SpamDetection) -> None:
        log.info("Spam filter triggered - %s - %s", detection.author, detection.reason)
        timed_out_until = await self.timeout_offender(detection)
        await self.send_audit_messages(detection, timed_out_until=timed_out_until)
        await self.delete_offending_messages(detection)

    async def timeout_offender(
        self,
        detection: SpamDetection,
    ) -> datetime.datetime | None:
        if SPAM_TIMEOUT_MINUTES < 1:
            return
        elif not detection.guild.me.guild_permissions.moderate_members:
            log.info("Cannot timeout %s, insufficient permissions", detection.author)
            return
        elif detection.author.top_role >= detection.guild.me.top_role:
            log.info("Cannot timeout %s, insufficient role order", detection.author)
            return

        duration = datetime.timedelta(minutes=SPAM_TIMEOUT_MINUTES)
        timed_out_until = discord.utils.utcnow() + duration
        log.info("Timing out %s for %s", detection.author, duration)
        await detection.author.timeout(timed_out_until, reason=detection.reason)
        return timed_out_until

    async def send_audit_messages(
        self,
        detection: SpamDetection,
        *,
        timed_out_until: datetime.datetime | None,
    ) -> None:
        try:
            pending_messages = create_audit_messages(
                mode=AUDIT_MESSAGES,
                detection=detection,
                timed_out_until=timed_out_until,
                mod_mention=self.get_mod_mention(detection.guild),
                audit_channel=self.get_audit_channel(detection.guild),
            )
        except AuditMessagesDisabled:
            return
        except NoAuditChannel:
            log.warning("Cannot send audit messages, no suitable channel found")
            return

        sent = [s for m in pending_messages if (s := await m.send()) is not None]
        channel_names = {f"'{m.channel}'" for m in sent}
        log.info("Sent audit messages to %s", " and ".join(channel_names))

    async def delete_offending_messages(self, detection: SpamDetection) -> None:
        deleteable = [
            message
            for message in detection.messages
            if message.channel.permissions_for(detection.guild.me).manage_messages
        ]
        if not deleteable:
            return

        log.info("Deleting %d messages from %s", len(deleteable), detection.author)
        await _try_bulk_delete_messages(deleteable)

    def get_mod_mention(self, guild: discord.Guild) -> str:
        role = discord.utils.find(_is_mod_role, guild.roles)
        if role is not None:
            return role.mention
        return f"<@{guild.owner_id}>"

    def get_audit_channel(
        self,
        guild: discord.Guild,
    ) -> discord.abc.MessageableChannel | None:
        for channel_id in AUDIT_CHANNELS:
            channel = guild.get_channel_or_thread(channel_id)
            if channel is None:
                continue
            elif isinstance(channel, (discord.CategoryChannel, discord.ForumChannel)):
                log.warning(
                    "Invalid audit channel, messages not supported: %s (%d)",
                    channel,
                    channel.id,
                )
                continue
            elif not channel.permissions_for(guild.me).send_messages:
                log.warning(
                    "Invalid audit channel, missing Send Messages permission: %s (%d)",
                    channel,
                    channel.id,
                )
                continue
            return channel

    @commands.group("antispam")
    @commands.has_guild_permissions(manage_guild=True)
    async def antispam(self, ctx: Context) -> None:
        pass

    @antispam.command("audit")  # ty: ignore[invalid-argument-type]
    async def show_audit_channel(self, ctx: Context) -> None:
        """Show the configured audit channel, if any."""
        if AUDIT_MESSAGES == AuditMessageMode.DISABLED:
            await ctx.reply("The bot owner has disabled audit messages.")
            return

        assert ctx.guild is not None
        channel = self.get_audit_channel(ctx.guild)
        if channel is None:
            await ctx.reply(
                "No dedicated audit channel is set.\n"
                "Ask the bot owner to set the channel, or if already set, "
                "double check the channel's permissions."
            )
        elif AUDIT_MESSAGES == AuditMessageMode.PREFER_AUDIT_CHANNEL:
            await ctx.reply(
                f"The current audit channel is {channel}.\n"
                f"Messages will only be sent to this channel."
            )
        elif AUDIT_MESSAGES == AuditMessageMode.AUDIT_AND_RECENT:
            await ctx.reply(
                f"The current audit channel is {channel}.\n"
                f"Messages will be sent to both this channel and wherever "
                f"a detection takes place."
            )
        else:
            assert_never(AUDIT_MESSAGES)

    @antispam.command("staff")  # ty: ignore[invalid-argument-type]
    async def show_mod_mention(self, ctx: Context) -> None:
        """Show the staff role to be mentioned on spam detections."""
        assert ctx.guild is not None
        mod_mention = self.get_mod_mention(ctx.guild)

        await ctx.reply(
            f"The current staff mention is {mod_mention}.",
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                users=False,
                roles=False,
                replied_user=True,
            ),
        )
