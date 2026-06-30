from minibotcatcher.bot import Bot

from .cog import AntiSpam


async def setup(bot: Bot) -> None:
    await bot.add_cog(AntiSpam(bot))
