from __future__ import annotations

import importlib.metadata
import logging
import pkgutil
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minibotcatcher.bot import Bot

log = logging.getLogger(__name__)


async def load_extensions(bot: Bot) -> None:
    for ext in list_extensions():
        log.info("Loading extension: %s", ext)
        await bot.load_extension(ext)
    await _maybe_load_jishaku(bot)


def list_extensions() -> list[str]:
    return [info.name for info in pkgutil.iter_modules(__path__, f"{__name__}.")]


async def _maybe_load_jishaku(bot: Bot) -> None:
    with suppress(importlib.metadata.PackageNotFoundError):
        version = importlib.metadata.version("jishaku")
        log.info("Loading extension: jishaku (v%s)", version)
        await bot.load_extension("jishaku")
