"""
Tests for web view entity support.

:copyright: (c) 2026 by Unfolded Circle ApS.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import json
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch

from ucapi import Button, Entities, EntityTypes, Events, IntegrationAPI, WebView
from ucapi.api import sanitize_json_message
from ucapi.webview import Attributes, AuthType, Options, States, UserAgent


class TestWebView(unittest.IsolatedAsyncioTestCase):
    """Exercise web views through the public API and entity store."""

    def test_secrets_are_redacted_in_logs(self):
        """Redact web view credentials without modifying the actual wire payload."""
        for auth in (
            {"type": "basic", "username": "viewer", "password": "basic-secret"},
            {"type": "bearer", "token": "bearer-secret"},
            {
                "type": "header",
                "header_name": "X-API-Key",
                "header_value": "header-secret",
            },
        ):
            with self.subTest(auth_type=auth["type"]):
                definition = {
                    "entity_type": "webview",
                    "options": {
                        "url": "https://example.com",
                        "auth": auth,
                        "cookies": [
                            {"name": "session", "value": "cookie-secret", "path": "/"}
                        ],
                    },
                }
                for data in (
                    {
                        "msg": "available_entities",
                        "msg_data": {"available_entities": [definition]},
                    },
                    {"msg": "entity_available", "msg_data": definition},
                ):
                    original = deepcopy(data)
                    logged = json.dumps(sanitize_json_message(data))
                    self.assertNotIn("-secret", logged)
                    self.assertIn('"name": "session"', logged)
                    self.assertIn('"url": "https://example.com"', logged)
                    self.assertEqual(data, original)

    def test_minimal_entity(self):
        """Leave state unspecified so Core can determine availability."""
        entity = WebView(
            "dashboard", "Dashboard", options={Options.URL: "https://example.com"}
        )
        self.assertEqual(entity.entity_type, EntityTypes("webview"))
        self.assertEqual(entity.name, {"en": "Dashboard"})
        self.assertEqual(entity.features, [])
        self.assertEqual(entity.attributes, {})
        self.assertIsNone(entity.device_class)

        other = WebView("other", "Other", options={"url": "http://example.com"})
        entity.attributes[Attributes.STATE] = States.UNAVAILABLE
        self.assertEqual(other.attributes, {})

    async def test_definition_serialization(self):
        """Preserve nested options and secrets needed by Core, without UI-only fields."""
        options = {
            Options.URL: "https://dashboard.example.com/energy?kiosk=1",
            Options.AUTH: {"type": AuthType.BEARER, "token": "example-token"},
            Options.TLS: {"certificate_sha256": "ab" * 32},
            Options.COOKIES: [
                {
                    "name": "session",
                    "value": "example-cookie",
                    "domain": "dashboard.example.com",
                    "path": "/",
                    "secure": True,
                    "http_only": True,
                    "expires": "2027-01-01T00:00:00Z",
                }
            ],
            Options.USER_AGENT: UserAgent.DESKTOP,
            Options.ZOOM: 70,
            Options.BACKGROUND_COLOR: "#112233",
            Options.SHOW_NAVIGATION: True,
            Options.RELOAD_INTERVAL: 60,
            Options.BUTTONS: {
                "BACK": {"action": "function", "function": "back_or_close"},
                "VOLUME_UP": {"action": "pass"},
                "CHANNEL_UP": {"action": "key", "key": "ChannelUp"},
            },
        }
        entity = WebView(
            "dashboard",
            {"en": "Dashboard", "de": "Übersicht"},
            options=options,
            attributes={Attributes.STATE: States.ON},
            icon="uc:globe",
            description="Energy dashboard",
            area="Living room",
        )
        entities = Entities("available", asyncio.get_running_loop())
        entities.add(entity)

        self.assertEqual(
            json.loads(json.dumps(entities.get_all())),
            [
                {
                    "entity_id": "dashboard",
                    "entity_type": "webview",
                    "device_id": None,
                    "features": [],
                    "name": {"en": "Dashboard", "de": "Übersicht"},
                    "options": json.loads(json.dumps(options)),
                    "icon": "uc:globe",
                    "description": {"en": "Energy dashboard"},
                    "area": "Living room",
                }
            ],
        )
        serialized = json.loads(json.dumps(entities.get_all()))[0]["options"]
        self.assertEqual(
            serialized["auth"], {"type": "bearer", "token": "example-token"}
        )
        self.assertEqual(serialized["cookies"][0]["value"], "example-cookie")
        self.assertNotIn("editable", serialized)
        self.assertNotIn("user", serialized)

    async def test_authentication_options(self):
        """Pass each supported authentication method through to Core."""
        for auth in (
            {"type": AuthType.NONE},
            {"type": AuthType.BASIC, "username": "viewer", "password": "secret"},
            {"type": AuthType.BEARER, "token": "secret"},
            {
                "type": AuthType.HEADER,
                "header_name": "X-API-Key",
                "header_value": "secret",
            },
        ):
            with self.subTest(auth_type=auth["type"]):
                entity = WebView(
                    "dashboard",
                    "Dashboard",
                    options={Options.URL: "https://example.com", Options.AUTH: auth},
                )
                entities = Entities("available", asyncio.get_running_loop())
                entities.add(entity)
                serialized = json.loads(json.dumps(entities.get_all()))[0]
                self.assertEqual(serialized["options"]["auth"], auth)

    async def test_state_updates(self):
        """Report optional server availability changes using normal entity events."""
        api = IntegrationAPI(asyncio.get_running_loop())
        entity = WebView(
            "dashboard", "Dashboard", options={"url": "https://example.com"}
        )
        api.configured_entities.add(entity)
        # Register the event forwarding normally installed by IntegrationAPI.init.
        api.configured_entities.add_listener(
            Events.ENTITY_ATTRIBUTES_UPDATED, api._on_entity_attributes_updated
        )
        updates = []
        api.configured_entities.add_listener(
            Events.ENTITY_ATTRIBUTES_UPDATED, lambda *args: updates.append(args)
        )

        with patch.object(
            api, "_broadcast_ws_event", new_callable=AsyncMock
        ) as broadcast:
            for state in (States.UNAVAILABLE, States.UNKNOWN, States.ON):
                attributes = {Attributes.STATE: state}
                self.assertTrue(
                    api.configured_entities.update_attributes(entity.id, attributes)
                )
                await asyncio.sleep(0)
                broadcast.assert_awaited_with(
                    "entity_change",
                    {
                        "entity_id": "dashboard",
                        "entity_type": "webview",
                        "attributes": {"state": state.value},
                    },
                    "ENTITY",
                )
                self.assertEqual(
                    updates[-1], ("dashboard", EntityTypes.WEBVIEW, attributes)
                )

        states = json.loads(json.dumps(await api.configured_entities.get_states()))
        self.assertEqual(states[0]["attributes"], {"state": "ON"})

    async def test_discovery_requires_explicit_webview_support(self):
        """Protect old firmware, including empty, missing and timed-out capabilities."""
        for supported, error, expected_ids in (
            (["webview", "button"], None, ["dashboard", "button"]),
            (["button"], None, ["button"]),
            ([], None, ["button"]),
            (None, None, ["button"]),
            (None, TimeoutError(), ["button"]),
        ):
            with self.subTest(supported=supported, error=error):
                api = IntegrationAPI(asyncio.get_running_loop())
                api.available_entities.add(
                    WebView(
                        "dashboard", "Dashboard", options={"url": "https://example.com"}
                    )
                )
                api.available_entities.add(Button("button", "Button"))
                websocket = Mock()
                with (
                    patch.object(
                        api,
                        "get_supported_entity_types",
                        new_callable=AsyncMock,
                        return_value=supported,
                        side_effect=error,
                    ),
                    patch.object(
                        api, "_enqueue_ws_payload", new_callable=AsyncMock
                    ) as send,
                ):
                    await api._process_ws_message(
                        websocket,
                        {"kind": "req", "id": 1, "msg": "get_available_entities"},
                    )
                response = json.loads(json.dumps(send.await_args.args[1]))
                self.assertEqual(response["code"], 200)
                self.assertEqual(response["msg"], "available_entities")
                self.assertEqual(
                    [
                        item["entity_id"]
                        for item in response["msg_data"]["available_entities"]
                    ],
                    expected_ids,
                )

    async def test_capabilities_are_scoped_to_connection(self):
        """Keep an old Remote isolated and rediscover support after disconnecting."""
        api = IntegrationAPI(asyncio.get_running_loop())
        api.available_entities.add(
            WebView("dashboard", "Dashboard", options={"url": "https://example.com"})
        )
        modern, legacy = Mock(), Mock()
        with (
            patch.object(
                api,
                "get_supported_entity_types",
                new_callable=AsyncMock,
                side_effect=[["webview"], ["button"], ["button"]],
            ) as capabilities,
            patch.object(api, "_enqueue_ws_payload", new_callable=AsyncMock) as send,
        ):
            for websocket, expected_ids in (
                (modern, ["dashboard"]),
                (legacy, []),
                (modern, ["dashboard"]),
            ):
                await api._get_available_entities(websocket, 1)
                response = send.await_args.args[1]
                self.assertEqual(
                    [
                        item["entity_id"]
                        for item in response["msg_data"]["available_entities"]
                    ],
                    expected_ids,
                )
            self.assertEqual(capabilities.await_count, 2)

            await api._cleanup_ws(modern)
            await api._get_available_entities(modern, 2)
            capabilities.assert_awaited_with(modern, timeout=5.0)
            self.assertEqual(capabilities.await_count, 3)
            self.assertEqual(
                send.await_args.args[1]["msg_data"]["available_entities"], []
            )


if __name__ == "__main__":
    unittest.main()
