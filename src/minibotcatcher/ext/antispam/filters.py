from __future__ import annotations

import asyncio
import bisect
import datetime
import logging
import re
from collections import deque
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

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
    period: datetime.timedelta = datetime.timedelta(seconds=20),
) -> SpamDetection | None:
    """Check if an author has sent too many messages across different channels
    in the given period.
    """
    after = discord.utils.utcnow() - period
    messages = context.query_messages(after=after)
    unique_channels = {m.channel.id for m in messages}
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

    type Key = tuple[int, int]
    _contexts: dict[Key, SpamContext]
    _acquired_contexts: set[Key]

    def __init__(self, *, message_period: datetime.timedelta) -> None:
        self.message_period = message_period

        self._contexts = {}
        self._acquired_contexts = set()
        self._cond = asyncio.Condition()

    @asynccontextmanager
    async def acquire(self, message: discord.Message) -> AsyncIterator[SpamContext]:
        """Acquire the SpamContext for a given message.

        If held by another task, wait until the context is released.

        If there is a cached context, any expired messages
        are removed. The passed message is then added to the context.

        :raises ValueError: the message is not associated with a guild.

        """

        def is_context_free() -> bool:
            return key not in self._acquired_contexts

        key = self._get_message_key(message)

        async with self._cond:
            await self._cond.wait_for(is_context_free)
            context = self._get(message)
            self._acquired_contexts.add(key)

        try:
            yield context
        finally:
            async with self._cond:
                self._acquired_contexts.discard(key)
                self._cond.notify_all()

    def _get(self, message: discord.Message) -> SpamContext:
        self._prune_contexts()  # is this expensive?

        key = self._get_message_key(message)
        context = self._contexts.get(key)
        if context is None:
            assert isinstance(message.author, discord.Member)
            context = SpamContext(author=message.author)
            self._contexts[key] = context

        context.add_message(message)
        return context

    def _get_message_key(self, message: discord.Message) -> Key:
        if message.guild is None:
            raise ValueError("Cannot get context for message without guild")

        return (message.guild.id, message.author.id)

    def remove(self, context: SpamContext) -> None:
        """Remove the given SpamContext from cache."""
        key = (context.guild.id, context.author.id)
        self._contexts.pop(key, None)

    def _prune_contexts(self) -> None:
        to_remove: list[SpamContext] = []
        expires_at = discord.utils.utcnow() - self.message_period

        for context in self._contexts.values():
            context.remove_messages_before(expires_at)
            if not context.messages:
                to_remove.append(context)

        for context in to_remove:
            self.remove(context)


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
