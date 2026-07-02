from __future__ import annotations

import logging
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minibotcatcher.bot import Bot

log = logging.getLogger(__name__)


async def load_extensions(bot: Bot) -> None:
    for ext in list_extensions():
        log.info("Loading extension: %s", ext)
        await bot.load_extension(ext)


def list_extensions() -> list[str]:
    return [info.name for info in pkgutil.iter_modules(__path__, f"{__name__}.")]
