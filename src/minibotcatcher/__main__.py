import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Self

from dotenv import load_dotenv

from . import __version__
from .logging import setup_logging


def main() -> None:
    load_dotenv()
    args = Args.parse_args()

    setup_logging(verbose=args.verbose)

    token = read_token()
    start_bot(token)


@dataclass(kw_only=True)
class Args:
    verbose: int

    @classmethod
    def parse_args(cls) -> Self:
        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=f"{__package__} v{__version__}",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
        )

        args = parser.parse_args()

        return cls(
            verbose=args.verbose,
        )


def start_bot(token: str) -> None:
    from minibotcatcher.bot import Bot  # defer discord.py import

    bot = Bot()
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
