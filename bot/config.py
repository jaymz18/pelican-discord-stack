"""Static bot configuration (values that are not egg variables)."""
from __future__ import annotations

import os

# Fallback welcome channel – used when no channel was configured with /setup welcome.
# Only used for joins on the server this channel belongs to.
# Can be overridden with the environment variable WELCOME_CHANNEL_ID.
DEFAULT_WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID") or 1572602823185670176)
