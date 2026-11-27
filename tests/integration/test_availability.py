"""Availability: retain logical state independently of transmitter connectivity."""

from __future__ import annotations

import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import (
    TRANSMITTER,
    code_dict,
    command_dict,
    entity_id_for,
    p8_timings,
    receive,
    setup_device,
)

POWER = "0xF0F0F0"
OFF = "0xC3C3C3"


@pytest.mark.parametrize("platform", ["light", "switch"])
async def test_state_is_retained_and_send_is_rejected_while_transmitter_is_unavailable(
    hass: HomeAssistant, hass_storage, transmitter, sent, platform: str
) -> None:
    """Received codes still update state, but commands cannot change it offline."""
    await setup_device(
        hass,
        hass_storage,
        {
            "power": code_dict(
                "power",
                "Power",
                platform,
                {
                    "on": [command_dict(p8_timings(POWER))],
                    "off": [command_dict(p8_timings(OFF))],
                },
            )
        },
    )
    entity_id = entity_id_for(hass, platform, "power")
    assert hass.states.get(entity_id).state == STATE_OFF

    hass.states.async_set(TRANSMITTER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    # Receiving remains independent of the transmitter and can still update
    # the last-known state while HA cannot send commands.
    receive(hass, p8_timings(POWER))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # A requested state change must fail before applying an optimistic update.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            platform,
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
    assert hass.states.get(entity_id).state == STATE_ON
    assert sent == []

    receive(hass, p8_timings(OFF))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF
