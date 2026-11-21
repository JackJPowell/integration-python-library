"""
Web view entity definitions.

:copyright: (c) 2026 by Unfolded Circle ApS.
:license: MPL-2.0, see LICENSE for more details.
"""

from enum import StrEnum
from typing import Any

from .entity import Entity, EntityTypes


class States(StrEnum):
    """Web view entity states."""

    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"
    ON = "ON"
    """The web view can be shown. Core determines availability if state is omitted."""


class Attributes(StrEnum):
    """Web view entity attributes."""

    STATE = "state"
    """Optional entity state; the current page URL and title are not attributes."""


class Commands(StrEnum):
    """Commands executed by the Remote UI, never sent to integration drivers."""

    OPEN = "open"
    """Wake the display and open the start page fullscreen."""
    RELOAD = "reload"
    """Reload the page if the web view is shown."""
    CLEAR_CACHE = "clear_cache"
    """Clear the shared HTTP cache of all web views and reload the shown page."""
    CLEAR_DATA = "clear_data"
    """Clear shared website data of all web views and reload the shown page."""


class Options(StrEnum):
    """Web view definition options supplied by an integration driver."""

    URL = "url"
    """Required absolute HTTP(S) start URL, at most 2048 characters, without credentials."""
    AUTH = "auth"
    """Origin-scoped authentication dict: type and credentials. See AuthType."""
    TLS = "tls"
    """Host certificate exception dict: certificate_sha256 or allow_invalid_certificate."""
    COOKIES = "cookies"
    """Up to 20 cookie dicts, each with name and secret value; scoped to the URL host."""
    USER_AGENT = "user_agent"
    """UserAgent preset or custom visible ASCII string, at most 256 characters."""
    ZOOM = "zoom"
    """Page zoom in percent, 25..400. Defaults to 100."""
    BACKGROUND_COLOR = "background_color"
    """Loading background as #RRGGBB. Defaults to white (#FFFFFF)."""
    SHOW_NAVIGATION = "show_navigation"
    """Show fullscreen navigation controls. Defaults to False."""
    RELOAD_INTERVAL = "reload_interval"
    """Reload interval in seconds: 0 (off, default) or 10..86400."""
    BUTTONS = "buttons"
    """Physical button mappings to action dicts: pass, function or key."""


class AuthType(StrEnum):
    """Authentication methods for the origin of the start URL."""

    NONE = "none"
    BASIC = "basic"
    """Requires username; password is secret. Also answers Digest challenges."""
    BEARER = "bearer"
    """Send the secret token as an Authorization: Bearer header."""
    HEADER = "header"
    """Send header_name with the secret header_value."""


class UserAgent(StrEnum):
    """User agent presets; a custom string can also be supplied."""

    DEFAULT = "default"
    MOBILE = "mobile"
    DESKTOP = "desktop"


class WebView(Entity):
    """
    Web page rendered by the Remote UI, supported since firmware 2.14.0.

    The driver supplies the definition and optional state updates. Commands are
    executed by the Remote UI, so no command handler is required. Core validates
    the options. Features and device classes are not supported.

    See https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_webview.md
    for option details and button mappings.
    """

    def __init__(
        self,
        identifier: str,
        name: str | dict[str, str],
        *,
        options: dict[str, Any],
        attributes: dict[str, Any] | None = None,
        icon: str | None = None,
        description: str | dict[str, str] | None = None,
        area: str | None = None,
    ):
        """
        Create a web view entity.

        :param identifier: entity identifier
        :param name: friendly name, either a string or a language dictionary
        :param options: web view options, including the required url
        :param attributes: optional state; omit to let Core determine availability
        :param icon: optional icon
        :param description: optional description, either a string or a language dictionary
        :param area: optional area name
        """
        super().__init__(
            identifier,
            name,
            EntityTypes.WEBVIEW,
            [],
            attributes if attributes is not None else {},
            options=options,
            icon=icon,
            description=description,
            area=area,
        )
