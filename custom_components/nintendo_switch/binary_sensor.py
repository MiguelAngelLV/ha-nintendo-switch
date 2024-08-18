"""Create and add sensors to Home Assistant."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from nso_api.imink import IMink
from nso_api.nso_api import NSO_API
from typing_extensions import override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    _DataT,
)

from .const import (
    CONF_GLOBAL_DATA,
    CONF_USER_DATA,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialise sensors and add to Home Assistant."""
    imink = IMink(f"Home Assistant {NSO_API.get_version()}")
    nso = NSO_API(imink, "config")
    nso.load_global_data(entry.data[CONF_GLOBAL_DATA])
    nso.load_user_data(entry.data[CONF_USER_DATA])
    coordinator = NintendoSwitchCoordinator(hass, entry, nso)

    await coordinator.async_config_entry_first_refresh()
    friends = coordinator.data
    async_add_entities(
        FriendSensor(nsa_id=f["nsaId"], name=f["name"], coordinator=coordinator)
        for f in friends
    )


class NintendoSwitchCoordinator(DataUpdateCoordinator):
    """Nintendo Switch API Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, nso: NSO_API) -> None:
        """Initialize Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Nintendo Switch Online",
            update_interval=timedelta(seconds=30),
        )
        self._nso = nso
        self._entry = entry
        self._user_data = {}
        self._global_data = {}
        self._need_update_entry = True

        self._nso.on_user_data_update(lambda _, __: self._mark_need_update())
        self._nso.on_global_data_update(lambda _: self._mark_need_update())

    @override
    async def _async_update_data(self) -> _DataT:
        friends = await self.hass.async_add_executor_job(
            self._nso.account.get_friends_list
        )

        if self._need_update_entry:
            await self._update_entry()

        return friends.get("friends", [])

    def _mark_need_update(self) -> None:
        self._need_update_entry = True

    async def _update_entry(self) -> None:
        self._need_update_entry = False
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                CONF_USER_DATA: self._nso.get_user_data(),
                CONF_GLOBAL_DATA: self._nso.get_global_data(),
            },
        )


class FriendSensor(BinarySensorEntity, CoordinatorEntity):
    """Nintendo Switch Sensor."""

    def __init__(
        self, nsa_id: str, name: str, coordinator: NintendoSwitchCoordinator
    ) -> None:
        """Initialize all values."""
        super().__init__(coordinator=coordinator)
        self._state = False
        self._nsa_id = nsa_id
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"nintendo_switch_{nsa_id}"
        self.entity_description = BinarySensorEntityDescription(
            name=f"Nintendo Switch {name}",
            key=f"nintendo_switch_{nsa_id}",
            has_entity_name=True,
            icon="mdi:controller-classic",
        )

    @property
    @override
    def is_on(self) -> bool | None:
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        friend = next(
            (x for x in self.coordinator.data if x["nsaId"] == self._nsa_id), None
        )
        self._state = friend["presence"]["state"] == "ONLINE"
        self._attr_extra_state_attributes["game"] = (
            friend["presence"].get("game", {}).get("name", "---")
        )
        self.async_write_ha_state()
