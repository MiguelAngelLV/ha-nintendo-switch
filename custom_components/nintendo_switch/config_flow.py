"""Config flow for Nintendo Switch integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nso_api.imink import IMink
from nso_api.nso_api import NSO_API
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_GLOBAL_DATA,
    CONF_USER_DATA,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nintendo Switch."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize values."""
        self._errors = None
        imink = IMink(f"Home Assistant {NSO_API.get_version()}")
        self.nso = NSO_API(imink, "config")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Config flow for Nintendo Switch Online."""
        self._errors = {}

        if user_input is not None:
            await self.hass.async_add_executor_job(
                self.nso.complete_login_challenge, user_input["address"]
            )
            user_input[CONF_USER_DATA] = self.nso.get_user_data()
            user_input[CONF_GLOBAL_DATA] = self.nso.get_global_data()
            account = await self.hass.async_add_executor_job(
                self.nso.account.get_user_self
            )
            await self.async_set_unique_id(f"nintendo-online-{account['nsaId']}")
            return self.async_create_entry(title=account["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("address"): str,
                }
            ),
            errors=self._errors,
            description_placeholders={"url": self.nso.get_login_challenge_url()},
        )
