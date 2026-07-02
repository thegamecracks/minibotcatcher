from __future__ import annotations

import bisect
import datetime
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Sequence

import discord

URL_PATTERN = re.compile(r"https?://\w+\.\w+\S*")  # close enough :)

log = logging.getLogger(__name__)


def check_burst_spam(
    context: SpamContext,
    *,
    message_threshold: int = 8,
    period: datetime.timedelta = datetime.timedelta(seconds=10),
) -> SpamDetection | None:
    """Check if an author has sent too many messages in the given period."""
    after = discord.utils.utcnow() - period
    messages = context.query_messages(after=after)
    if len(messages) < message_threshold:
        return

    return SpamDetection(
        author=context.author,
        messages=messages,
        reason=f"burst spam - sent {len(messages)} messages",
    )


def check_channel_spam(
    context: SpamContext,
    *,
    channel_threshold: int = 4,
    period: datetime.timedelta = datetime.timedelta(seconds=10),
) -> SpamDetection | None:
    """Check if an author has sent too many messages across different channels
    in the given period.
    """
    after = discord.utils.utcnow() - period
    messages = context.query_messages(after=after)
    unique_channels = set(m.channel.id for m in messages)
    if len(unique_channels) < channel_threshold:
        return

    return SpamDetection(
        author=context.author,
        messages=messages,
        reason=f"channel spam - sent {len(messages)} messages",
    )


def check_mention_spam(
    context: SpamContext,
    *,
    message_threshold: int = 3,
    period: datetime.timedelta = datetime.timedelta(seconds=30),
) -> SpamDetection | None:
    """Check if an author has used a mention across too many messages
    in the given period.

    Multiple mentions in a single message only counts as one against the threshold.
    Discord AutoMod can be used to limit the total number of mentions in a single message.

    """
    after = discord.utils.utcnow() - period
    messages = context.query_messages(after=after)
    messages = [m for m in messages if _message_contains_any_mention(m)]
    if len(messages) < message_threshold:
        return

    return SpamDetection(
        author=context.author,
        messages=messages,
        reason=f"mention spam - sent {len(messages)} messages",
    )


def _message_contains_any_mention(message: discord.Message) -> int:
    return (
        any(
            user for user in message.mentions if not user.bot and user != message.author
        )
        or any(role for role in message.role_mentions if role.mentionable)
        or "@everyone" in message.content
        or "@here" in message.content
    )


ALL_SPAM_FILTERS: dict[str, Callable[[SpamContext], SpamDetection | None]] = {
    "burst": check_burst_spam,
    "channel": check_channel_spam,
    "mention": check_mention_spam,
}


class SpamContextCache:
    """Create and manage SpamContext instances from messages.

    :param message_period: The period for which messages are stored.

    """

    type KEY = tuple[int, int]
    contexts: dict[KEY, SpamContext]

    def __init__(self, *, message_period: datetime.timedelta) -> None:
        self.contexts = {}
        self.message_period = message_period

    def get(self, message: discord.Message) -> SpamContext | None:
        """Get the current SpamContext for a given message.

        If there is a cached context, any expired messages
        are removed. The passed message is then added to the context.

        If the message is not associated with a guild,
        this will always return None.

        """
        if message.guild is None:
            return

        self._prune_contexts()  # is this expensive?

        key = (message.guild.id, message.author.id)
        context = self.contexts.get(key)
        if context is None:
            assert isinstance(message.author, discord.Member)
            context = SpamContext(author=message.author)
            self.contexts[key] = context

        context.add_message(message)
        return context

    def pop(self, message: discord.Message) -> SpamContext | None:
        """Remove and return any SpamContext corresponding to the given message."""
        if message.guild is None:
            return

        key = (message.guild.id, message.author.id)
        return self.contexts.pop(key, None)

    def _prune_contexts(self) -> None:
        to_remove: list[SpamContextCache.KEY] = []
        expires_at = discord.utils.utcnow() - self.message_period
        for key, context in self.contexts.items():
            context.remove_messages_before(expires_at)
            if not context.messages:
                to_remove.append(key)


@dataclass(kw_only=True)
class SpamContext:
    """The context related to a member for purposes of spam detection."""

    author: discord.Member
    """The member to make a ruling on."""
    _messages: deque[discord.Message] = field(default_factory=deque, init=False)

    @property
    def messages(self) -> Sequence[discord.Message]:
        """All recent messages sorted from oldest to newest."""
        return self._messages

    @property
    def guild(self) -> discord.Guild:
        """The guild that the author is in."""
        return self.author.guild

    def add_message(self, message: discord.Message) -> None:
        """Add a message to this context."""
        if message.author != self.author:
            raise ValueError("Cannot add message from a different author")

        bisect.insort_right(
            self._messages,
            message,
            key=lambda m: m.created_at,
        )

    def query_messages(self, *, after: datetime.datetime) -> list[discord.Message]:
        """Filter messages based on the given parameters."""
        return [m for m in self.messages if m.created_at >= after]

    def remove_messages_before(self, expires_at: datetime.datetime) -> None:
        """Remove messages older than the given datetime."""
        messages = self._messages
        while messages and messages[0].created_at < expires_at:
            messages.popleft()


@dataclass(kw_only=True)
class SpamDetection:
    """The result of a spam filter determining an author to have one or more
    offending messages.
    """

    author: discord.Member
    """The member to take action on."""
    messages: list[discord.Message]
    """A list of messages from the author."""
    reason: str
    """The reason why the messages were determined as spam."""

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("Must have at least one message")
        elif any(m.author != self.author for m in self.messages):
            raise ValueError("Cannot include messages from another author")
        self.messages.sort(key=lambda m: m.created_at)

    @property
    def guild(self) -> discord.Guild:
        """The guild that the author is in."""
        return self.author.guild

    @property
    def recent_channel(self) -> discord.abc.MessageableChannel | None:
        """The channel of the most recent offending message that the bot can send to."""
        return discord.utils.find(
            _can_send_in_channel,
            reversed([m.channel for m in self.messages]),
        )


def _can_send_in_channel(channel: discord.abc.MessageableChannel) -> bool:
    assert channel.guild is not None
    return channel.permissions_for(channel.guild.me).send_messages
