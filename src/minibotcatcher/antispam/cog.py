import discord
from discord.ext import commands

from minibotcatcher.bot import Bot


class AntiSpam(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
