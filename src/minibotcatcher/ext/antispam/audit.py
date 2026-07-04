from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from contextlib import suppress
from dataclasses import dataclass
from typing import assert_never

import discord

from .env import AuditMessageMode
from .filters import SpamDetection


def create_audit_messages(
    *,
    mode: AuditMessageMode,
    detection: SpamDetection,
    timed_out_until: datetime.datetime | None,
    mod_mention: str,
    audit_channel: discord.abc.MessageableChannel | None,
) -> list[AuditMessage]:
    """Build a list of audit messages to be sent for a spam detection.

    Each message should be sent off in order::
        messages = create_audit_messages(...)
        for m in messages:
            await m.send()

    :raises NoAuditChannel: there are no channels available to send messages.

    """
    params = _AuditMessageParams(
        detection=detection,
        timed_out_until=timed_out_until,
        mod_mention=mod_mention,
        audit_channel=audit_channel,
    )
    if mode == AuditMessageMode.DISABLED:
        raise AuditMessagesDisabled
    elif mode == AuditMessageMode.PREFER_AUDIT_CHANNEL:
        return _create_prefer_audit_channel_messages(params)
    elif mode == AuditMessageMode.AUDIT_AND_RECENT:
        return _create_audit_and_recent_messages(params)
    else:
        assert_never(mode)


def _create_prefer_audit_channel_messages(
    params: _AuditMessageParams,
) -> list[AuditMessage]:
    """Create audit messages according to ``AuditMessageMode.PREFER_AUDIT_CHANNEL``."""
    if params.audit_channel is not None:
        return [
            ContentAuditMessage(
                channel=params.audit_channel,
                allowed_mentions=params.create_allowed_mentions(),
                content=params.create_content(include_mention=True),
            ),
            ForwardAuditMessage(
                channel=params.audit_channel,
                message=params.last_offending_message,
            ),
        ]
    elif params.recent_channel is not None:
        return [
            ContentAuditMessage(
                channel=params.recent_channel,
                allowed_mentions=params.create_allowed_mentions(),
                content=params.create_content(include_mention=True),
            ),
        ]
    else:
        raise NoAuditChannel


def _create_audit_and_recent_messages(
    params: _AuditMessageParams,
) -> list[AuditMessage]:
    """Create audit messages according to ``AuditMessageMode.AUDIT_AND_RECENT``."""
    if params.audit_channel is None or params.recent_channel is None:
        return _create_prefer_audit_channel_messages(params)

    return [
        ContentAuditMessage(
            channel=params.recent_channel,
            allowed_mentions=params.create_allowed_mentions(),
            content=params.create_content(include_mention=True),
        ),
        ContentAuditMessage(
            channel=params.audit_channel,
            allowed_mentions=discord.AllowedMentions.none(),
            content=params.create_content(include_mention=False),
        ),
        ForwardAuditMessage(
            channel=params.audit_channel,
            message=params.last_offending_message,
        ),
    ]


class AuditMessage(ABC):
    @abstractmethod
    async def send(self) -> discord.Message | None:
        raise NotImplementedError


@dataclass(kw_only=True)
class ContentAuditMessage(AuditMessage):
    channel: discord.abc.MessageableChannel
    allowed_mentions: discord.AllowedMentions
    content: str

    async def send(self) -> discord.Message | None:
        return await self.channel.send(
            self.content,
            allowed_mentions=self.allowed_mentions,
        )


@dataclass(kw_only=True)
class ForwardAuditMessage(AuditMessage):
    channel: discord.abc.MessageableChannel
    message: discord.Message

    async def send(self) -> discord.Message | None:
        # Ignore messages being deleted before we can forward them
        with suppress(discord.HTTPException):
            return await self.message.forward(self.channel)


@dataclass(kw_only=True)
class _AuditMessageParams:  # FIXME: is there a better name for this?
    detection: SpamDetection
    timed_out_until: datetime.datetime | None
    mod_mention: str
    audit_channel: discord.abc.MessageableChannel | None

    @property
    def last_offending_message(self) -> discord.Message:
        return self.detection.messages[-1]

    @property
    def recent_channel(self) -> discord.abc.MessageableChannel | None:
        return self.detection.recent_channel

    def create_allowed_mentions(self) -> discord.AllowedMentions:
        return discord.AllowedMentions(
            everyone=False,
            users=not self.mod_mention.startswith("<@&"),
        )

    def create_content(self, *, include_mention: bool) -> str:
        lines: list[str] = []
        detection = self.detection
        mention = detection.author.mention
        timed_out_until = self.timed_out_until

        if timed_out_until is not None:
            timestamp_f = discord.utils.format_dt(timed_out_until, style="f")
            lines.append(
                f"⚠️ {mention} has been timed out until {timestamp_f} "
                f"(reason: {detection.reason})."
            )
        else:
            lines.append(
                f"⚠️ {mention} triggered a spam filter (reason: {detection.reason})."
            )

        if include_mention and self.mod_mention is not None:
            lines.append("")
            lines.append(f"Alerting {self.mod_mention} for review.")

        return "\n".join(lines)


class AuditMessageException(Exception):
    """The base exception raised by ``create_audit_messages()``."""


class AuditMessagesDisabled(AuditMessageException):
    """Raised when audit messages are disabled."""


class NoAuditChannel(AuditMessageException):
    """Raised when there are no suitable channels to send audit messages."""
