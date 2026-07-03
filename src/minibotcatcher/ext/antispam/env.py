import logging
import os
import re
from enum import Enum

from .filters import ALL_SPAM_FILTERS


class AuditMessageMode(Enum):
    DISABLED = 0
    PREFER_AUDIT_CHANNEL = 1
    AUDIT_AND_RECENT = 2


AUDIT_CHANNELS = [
    int(channel_id)
    for channel_id in re.findall(r"\d+", os.getenv("AUDIT_CHANNELS", ""))
]
AUDIT_MESSAGES = AuditMessageMode(int(os.getenv("AUDIT_MESSAGES", "1")))

_selected_filters = re.findall(r"\w+", os.getenv("SPAM_FILTERS", ""))
SPAM_FILTERS = {
    name: check
    for name, check in ALL_SPAM_FILTERS.items()
    if not _selected_filters or name in _selected_filters
}
SPAM_TIMEOUT_MINUTES = int(os.getenv("SPAM_TIMEOUT_MINUTES", "5"))

DEBUG_SKIP_ADMIN_CHECK = os.getenv("DEBUG_SKIP_ADMIN_CHECK") == "1"

log = logging.getLogger(__name__)
log.info("AUDIT_CHANNELS: %d channels set", len(AUDIT_CHANNELS))
log.info("AUDIT_MESSAGES: %r", AUDIT_MESSAGES)
log.info(
    "SPAM_FILTERS: %d filters enabled (%s)",
    len(SPAM_FILTERS),
    ",".join(SPAM_FILTERS),
)
log.info("SPAM_TIMEOUT_MINUTES: %d minute timeout", SPAM_TIMEOUT_MINUTES)
