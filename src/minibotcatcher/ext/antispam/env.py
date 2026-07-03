import logging
import os
import re

from .filters import ALL_SPAM_FILTERS

AUDIT_CHANNELS = [
    int(channel_id)
    for channel_id in re.findall(r"\d+", os.getenv("AUDIT_CHANNELS", ""))
]

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
log.info(
    "SPAM_FILTERS: %d filters enabled (%s)",
    len(SPAM_FILTERS),
    ",".join(SPAM_FILTERS),
)
log.info("SPAM_TIMEOUT_MINUTES: %d minute timeout", SPAM_TIMEOUT_MINUTES)
