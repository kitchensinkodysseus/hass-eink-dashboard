# Copyright 2026 Andreas Schneider
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Weather wall widget context builder.

A full-panel weather layout for a wall-mounted colour e-ink display.
Unlike the stock weather widget this one owns the whole canvas: it
paints its own ground, chooses one of three layouts by time of day,
and reads both the daily and hourly forecasts.

Stub implementation — geometry to follow.
"""

from __future__ import annotations

from ._helpers import _color_context, _widget_dim

# Local hour at which the panel switches between layouts.  Hard-coded
# rather than configurable: the board wakes at fixed times and the
# layout follows the sun, not the user's preference.
_EVENING_FROM = 17
_NIGHT_FROM = 21


def _build_weather_wall_context(
    widget: dict,
    config: dict,
) -> dict[str, object]:
    """Build the Jinja2 template context for the weather wall widget.

    Args:
        widget: Widget config dict.
        config: Display config with ``width``, ``height`` and
            ``states``.

    Returns:
        Template context dict consumed by ``weather_wall.svg.j2``.
    """
    from homeassistant.util import dt as dt_util

    x = widget.get("x", 0)
    y = widget.get("y", 0)
    svg_w = _widget_dim(widget, "w", config["width"] - x)
    svg_h = _widget_dim(widget, "h", config["height"] - y)

    now = dt_util.now()
    if now.hour >= _NIGHT_FROM:
        state = "night"
    elif now.hour >= _EVENING_FROM:
        state = "evening"
    else:
        state = "morning"

    entity_id = widget.get("entity", "")
    states = config.get("states", {})
    entity = states.get(entity_id)

    return {
        "w": svg_w,
        "h": svg_h,
        "state": state,
        "has_state": entity is not None,
        "entity_id": entity_id,
        "stamp": now.strftime("%H:%M"),
        **_color_context(),
    }