import os
import re
import sys

from dotenv import load_dotenv

from .logging import setup_logging


def main() -> None:
    load_dotenv()
    token = read_token()

    from minibotcatcher.bot import Bot  # defer discord.py import

    bot = Bot()
    setup_logging()
    bot.run(token, log_handler=None)


def read_token() -> str:
    token = os.environ.pop("BOT_TOKEN", "").strip()
    if not token:
        sys.exit("BOT_TOKEN environment variable must be set")
    elif not re.fullmatch(r"\w+\.\w+\.\S+", token):
        sys.exit("BOT_TOKEN appears to be invalid, double check bot token")
    return token


if __name__ == "__main__":
    main()
