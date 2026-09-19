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

A full-panel weather layout for a wall-mounted six-colour e-ink
display.  Unlike the stock weather widget this one owns the entire
canvas: it paints its own ground, selects one of three layouts by
time of day, and reads both the daily and the hourly forecast.

Geometry is fixed to an 800 x 480 panel.  Every dimension below is a
real panel pixel, so the numbers here and the numbers in the design
drawings are the same numbers.

Three layouts:

* **morning** — today's maximum as the headline, today's remaining
  hours on the right, the following days below.
* **evening** — tonight's minimum as the headline, tomorrow's hours
  on the right, the days from the day after tomorrow below.
* **night** — as evening, with the tonight block on a black ground.

Icons are named here and drawn in the template.  The integration's
``_build_inline_svg()`` flattens every path to a single colour, which
would lose the yellow sun and the black rain-bearing cloud, so this
widget does not use the shared icon loader.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Any

from ._helpers import _color_context, _widget_dim

_LOGGER = logging.getLogger(__name__)

# Climatological percentile thresholds, keyed by "MM-DD".  Built by
# tools/build_climatology.py; see that script for the sources and
# the baseline periods.  Loaded once at import rather than per
# render: it never changes between restarts.  A missing file
# degrades to no remarkable line rather than breaking the panel,
# which matters because it is not in the upstream repository and a
# future merge could lose it.
_CLIMATOLOGY_PATH = Path(__file__).parent.parent / "climatology.json"

try:
    _CLIMATOLOGY: dict = json.loads(
        _CLIMATOLOGY_PATH.read_text()
    ).get("days", {})
except Exception as exc:  # noqa: BLE001
    _LOGGER.warning(
        "weather_wall: no climatology table (%s); the remarkable "
        "line will be suppressed", exc
    )
    _CLIMATOLOGY = {}

# ---------------------------------------------------------------
# Layout constants.  All values are 800 x 480 panel pixels.
# ---------------------------------------------------------------

MARGIN = 28
CANVAS_W = 800
CANVAS_H = 480

# Type scale, four sizes on a root-two progression.
FONT_XL = 80  # headline temperature
FONT_L = 40  # ultraviolet figure
FONT_M = 28  # any temperature sitting in a column
FONT_S = 20  # everything else

# Reduced-width minus sign, and the gap after it.  A full-width
# minus makes negative values collide with their neighbours; 0.7 is
# the conventional proportion for a tabular sign.
MINUS_SCALE = 0.7
MINUS_DX = 0.10  # as a fraction of the font size

# Left block: the headline.
LEFT_X = MARGIN
LEFT_RIGHT = 320
HERO_CX = 72
HERO_CY = 126
HERO_SCALE = 3.51  # icons are drawn in a 24-unit box
TEMP_X = 128
Y_DATE = 44
Y_UV_LABEL = 110
UV_BADGE_W = 56
UV_BADGE_H = 80
Y_UV_BADGE = 88
Y_HEADLINE = 154  # shared by the headline and the UV figure
Y_LINE2 = 190  # shared with the hourly temperatures
Y_METRICS = 264  # shared with the rain caption
LINE2_ICON_X = 142
LINE2_TEXT_X = 164
WIND_ICON_X = 40
WIND_TEXT_X = 64
SOLAR_ICON_X = 242

# Right block: the two-hourly strip.
RIGHT_X = 370
RIGHT_RIGHT = 772
HOUR_SLOTS = 7
HOUR_W = (RIGHT_RIGHT - RIGHT_X) / HOUR_SLOTS
Y_HOUR_LABEL = 92
HOUR_ICON_CY = 130
HOUR_SCALE = 1.58
Y_HOUR_TEMP = Y_LINE2
BAND_BOTTOM = 242
BAND_H = 46
Y_CAPTION = Y_METRICS

# The rule, and the day strip below it.
Y_RULE = 284
DAY_COLS = 7
DAY_GUTTER = 12
Y_DAY_LABEL = 316
DAY_ICON_CY = 348
DAY_SCALE = 1.89
Y_DAY_TEMP = 400
Y_DAY_PROB = 426
Y_DAY_REMARK = 450

# Night block.
NIGHT_W = 358
NIGHT_H = Y_RULE

# ---------------------------------------------------------------
# Behaviour constants.
# ---------------------------------------------------------------

# Local hour at which the layout changes.  Hard-coded rather than
# configurable: the board wakes at fixed times and the layout should
# follow the day, not a preference.
EVENING_FROM = 17
NIGHT_FROM = 21

# Hours shown in the evening and night strips.
EVENING_HOURS = (7, 9, 11, 13, 15, 17, 19)

# Ultraviolet index thresholds.
UV_HIDE_BELOW = 4
UV_WARN_ABOVE = 5.5

# Frost and ice derivation, applied to the overnight hourly slice.
FROST_AIR = 0.0  # air frost at or below, degrees Celsius
FROST_SEVERE = -3.0
FROST_GROUND = 4.0  # with clear skies and light wind
FROST_GROUND_CLOUD = 30  # per cent cloud cover
FROST_GROUND_WIND = 10  # km/h
ICE_PRECIP_MM = 0.2  # antecedent rainfall needed to freeze

# Cloud cover at or above which the moon is not drawn, and at or
# above which a cloud is drawn black rather than white.
CLOUD_OBSCURES_MOON = 70
CLOUD_IS_DARK = 80

# Precipitation intensity bands, millimetres per hour, giving one,
# two or three marks.
PRECIP_LIGHT = 0.5
PRECIP_HEAVY = 2.0

# Probability bands used where no amount is forecast.
PROB_LIGHT = 40
PROB_HEAVY = 70

# Lowest precipitation probability worth printing.
PROB_MIN = 15
# The hero icon needs a higher bar than the columns.  A drop under
# the largest glyph on the panel reads as a forecast of rain, so it
# should not appear for a day that is merely not certainly dry.
HERO_PROB_MIN = 25
# A day's measure is remarked on when it falls outside these
# percentiles for the calendar date.  Any value stored by
# build_climatology.py may be used: 1, 2, 5, 10, 20, 30, 40, 50,
# 60, 70, 80, 90, 95, 98, 99.  Raise p90 toward p98 to quieten the
# line; lower it toward p80 to make it chattier.
REMARK_HIGH = "p90"
REMARK_LOW = "p10"

# Absolute floors, applied as well as the percentile.  Without them
# a December ultraviolet index of 1.2 counts as high for December,
# which is true and useless.
REMARK_UV_MIN = 5.0
REMARK_GUST_MIN = 45.0

_COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

# HA moon phase states to the key used by the template.
_MOON_PHASES = {
    "new_moon": "new",
    "waxing_crescent": "wax_crescent",
    "first_quarter": "first_quarter",
    "waxing_gibbous": "wax_gibbous",
    "full_moon": "full",
    "waning_gibbous": "wane_gibbous",
    "last_quarter": "last_quarter",
    "waning_crescent": "wane_crescent",
}


def _num(value: Any) -> float | None:
    """Return ``value`` as a float, or ``None`` when not numeric."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _temp(value: Any) -> dict[str, object]:
    """Format a temperature for display as whole degrees.

    Returns a dict rather than a string so the template can set the
    minus sign at a reduced size; a full-width minus would push
    negative values into their neighbouring columns.

    Args:
        value: Temperature in degrees Celsius, or ``None``.

    Returns:
        ``{"show": bool, "neg": bool, "text": str}`` where ``text``
        carries the digits and degree sign without any sign.
    """
    n = _num(value)
    if n is None:
        return {"show": False, "neg": False, "text": ""}
    r = round(n)
    return {"show": True, "neg": r < 0, "text": f"{abs(r)}\u00b0"}


def _signed(t: dict[str, object]) -> str:
    """Return a formatted temperature as a plain string with sign."""
    if not t["show"]:
        return ""
    return f"{'\u2212' if t['neg'] else ''}{t['text']}"


def _compass(bearing: Any) -> str:
    """Return an eight-point compass abbreviation for a bearing."""
    n = _num(bearing)
    if n is None:
        return ""
    return _COMPASS[int((n % 360) / 45.0 + 0.5) % 8]


def _local(hass_dt: Any, raw: str | None):
    """Parse an ISO timestamp into local time, or return ``None``."""
    if not raw:
        return None
    parsed = hass_dt.parse_datetime(raw)
    return hass_dt.as_local(parsed) if parsed else None


def _drop_count(entry: dict[str, Any], prob_min: float = PROB_MIN) -> int:
    """Return 0-3 precipitation marks for a forecast entry.

    Prefers a forecast amount where the provider gives one and falls
    back to probability otherwise.  The Met Office daily forecast
    reports ``precipitation`` as ``None`` on every day and carries
    the information in ``precipitation_probability``.
    """
    amount = _num(entry.get("precipitation"))
    if amount is not None and amount > 0:
        if amount >= PRECIP_HEAVY:
            return 3
        if amount >= PRECIP_LIGHT:
            return 2
        return 1
    prob = _num(entry.get("precipitation_probability"))
    if prob is None or prob < prob_min:
        return 0
    if prob >= PROB_HEAVY:
        return 3
    if prob >= PROB_LIGHT:
        return 2
    return 1


def _is_dark_cloud(entry: dict[str, Any]) -> bool:
    """True when the cloud in this entry should be drawn black.

    Home Assistant's condition strings distinguish only cloudy from
    partlycloudy, which is not enough, so darkness is derived from
    cloud cover with precipitation as a secondary trigger: a shower
    cloud is dark regardless of how much sky it covers.
    """
    if _drop_count(entry) >= 2:
        return True
    cover = _num(entry.get("cloud_coverage"))
    return cover is not None and cover >= CLOUD_IS_DARK


def _icon_name(
    entry: dict[str, Any],
    night: bool = False,
    prob_min: float = PROB_MIN,
) -> str:
    """Return the icon key for a forecast entry.

    Args:
        entry: A forecast entry.
        night: True to prefer the night variant of clear or partly
            clear skies.  The day strip always passes False, since
            those columns describe daytime whatever the hour.
        prob_min: Lowest precipitation probability that earns a
            drop.  The hero passes a higher value than the columns.

    Returns:
        A key matching a ``<g id="wx-...">`` in the template.
    """
    cond = str(entry.get("condition", ""))
    drops = _drop_count(entry, prob_min)

    if cond in ("lightning", "lightning-rainy"):
        return "wx-storm"
    if cond == "fog":
        return "wx-fog"
    if cond in ("snowy", "snowy-rainy", "hail"):
        return f"wx-snow{drops}" if drops else "wx-cloud-dark"
    if drops:
        return f"wx-rain{drops}"
    if cond in ("rainy", "pouring"):
        return "wx-cloud-dark"
    if cond == "cloudy":
        return "wx-cloud-dark" if _is_dark_cloud(entry) else "wx-cloud"
    if cond == "partlycloudy":
        return "wx-moon-cloud" if night else "wx-sun-cloud"
    # A clear night gets stars rather than a moon.  The moon's phase
    # is drawn properly on the hero, where there is room for it; in
    # a 42 px column a fixed gibbous would be wrong most nights, and
    # tracking the phase at that size would not read.
    if cond == "clear-night" or night:
        return "wx-stars"
    if cond in ("windy", "windy-variant"):
        return "wx-cloud"
    return "wx-sun"


def _precip_word(entries: list[dict[str, Any]]) -> str:
    """Return rain, snow or sleet for the caption under the strip.

    Chosen by the predominant condition across the hours shown, not
    by any single hour, so one snowy hour at the far end of the day
    does not relabel the whole strip.
    """
    snow = sleet = 0
    for e in entries:
        cond = str(e.get("condition", ""))
        if cond == "snowy":
            snow += 1
        elif cond in ("snowy-rainy", "hail"):
            sleet += 1
    if snow > sleet and snow:
        return "snow"
    if sleet:
        return "sleet"
    return "rain"


def _overnight_slice(
    hourly: list[dict[str, Any]],
    hass_dt: Any,
    now: Any,
) -> list[dict[str, Any]]:
    """Return the hourly entries covering tonight, 22:00 to 08:00."""
    out: list[dict[str, Any]] = []
    for e in hourly:
        when = _local(hass_dt, e.get("datetime"))
        if when is None or when < now:
            continue
        if when.hour >= 22 or when.hour <= 8:
            out.append(e)
        if len(out) >= 12:
            break
    return out


def _frost_warning(
    overnight: list[dict[str, Any]],
    preceding: list[dict[str, Any]],
) -> str:
    """Derive a short frost or ice warning, or an empty string.

    Home Assistant's Met Office integration exposes no warnings, and
    a National Severe Weather Warning would be the wrong instrument
    anyway: it is issued regionally at an impact threshold, whereas
    what a kitchen panel should answer is whether the car will need
    scraping.

    Args:
        overnight: Hourly entries covering tonight.
        preceding: Hourly entries for the six hours before, used to
            decide whether there is any water about to freeze.

    Returns:
        One of ``"Icy"``, ``"Severe frost"``, ``"Frost"``,
        ``"Ground frost"`` or ``""``.
    """
    temps = [
        t for e in overnight
        if (t := _num(e.get("temperature"))) is not None
    ]
    if not temps:
        return ""
    low = min(temps)

    wet = sum(
        _num(e.get("precipitation")) or 0.0 for e in preceding
    ) >= ICE_PRECIP_MM

    if low <= FROST_AIR and wet:
        return "Icy"
    if low <= FROST_SEVERE:
        return "Severe frost"
    if low <= FROST_AIR:
        return "Frost"

    if low <= FROST_GROUND:
        clouds = [
            c for e in overnight
            if (c := _num(e.get("cloud_coverage"))) is not None
        ]
        winds = [
            w for e in overnight
            if (w := _num(e.get("wind_speed"))) is not None
        ]
        clear = not clouds or min(clouds) < FROST_GROUND_CLOUD
        calm = not winds or max(winds) < FROST_GROUND_WIND
        if clear and calm:
            return "Ground frost"
    return ""


def _remarkable(day: dict[str, Any], when: Any) -> str:
    """Return a short note when one measure is unusual, else "".

    Each candidate is compared against a percentile for the calendar
    date, computed from thirty years of reanalysis over a fifteen-day
    window.  An earlier version compared each day against the spread
    of the days on screen, which measured "unusual for this week"
    rather than "unusual for September" and rested on a sample of
    five.

    Whichever measure exceeds its threshold by the largest relative
    margin wins, which keeps three quantities in different units
    roughly comparable.

    Args:
        day: A daily forecast entry.
        when: The local datetime of that day, or None.

    Returns:
        A short phrase, or an empty string when nothing stands out.
    """
    if when is None or not _CLIMATOLOGY:
        return ""
    bands = _CLIMATOLOGY.get(f"{when.month:02d}-{when.day:02d}")
    if not bands:
        return ""

    candidates: list[tuple[float, str]] = []

    def over(measure: str, value: float | None, floor: float):
        """Relative margin above the upper percentile, or None."""
        limit = bands.get(measure, {}).get(REMARK_HIGH)
        if value is None or limit is None or value < floor:
            return None
        if limit <= 0 or value <= limit:
            return None
        return (value - limit) / limit

    uv = _num(day.get("uv_index"))
    margin = over("uv", uv, REMARK_UV_MIN)
    if margin is not None:
        candidates.append((margin, f"UV {round(uv)}"))

    gust = _num(day.get("wind_gust_speed"))
    margin = over("gust", gust, REMARK_GUST_MIN)
    if margin is not None:
        candidates.append((margin, f"gust {round(gust)}"))

    # Overnight minimum, two-tailed: a mild night in February and a
    # cold one in July are both worth saying.  Measured against the
    # width of the band rather than against the value itself, since
    # a minimum near zero would otherwise give an enormous margin.
    low = _num(day.get("templow"))
    band = bands.get("tmin", {})
    cold = band.get(REMARK_LOW)
    warm = band.get(REMARK_HIGH)
    if low is not None and cold is not None and warm is not None:
        width = max(1.0, warm - cold)
        if low < cold:
            candidates.append(
                ((cold - low) / width, f"min {_signed(_temp(low))}")
            )
        elif low > warm:
            candidates.append(
                ((low - warm) / width, f"min {_signed(_temp(low))}")
            )

    if not candidates:
        return ""
    return max(candidates, key=lambda c: c[0])[1]

def _rain_path(entries: list[dict[str, Any]]) -> tuple[str, float]:
    """Build the stepped rain-probability profile.

    A continuous profile reads as the shape of the day, which is the
    question actually being asked, and the fifty per cent rule gives
    the eye a reference so the shape is not merely decorative.

    Returns:
        ``(path_d, mid_y)`` where ``mid_y`` is the fifty per cent
        rule's vertical position.  ``path_d`` is empty when there is
        nothing to draw.
    """
    if not entries:
        return "", BAND_BOTTOM - BAND_H / 2
    parts = [f"M {RIGHT_X} {BAND_BOTTOM}"]
    for i, e in enumerate(entries):
        prob = _num(e.get("precipitation_probability")) or 0.0
        top = BAND_BOTTOM - BAND_H * max(0.0, min(100.0, prob)) / 100.0
        x1 = RIGHT_X + HOUR_W * i
        x2 = RIGHT_X + HOUR_W * (i + 1)
        parts.append(f"L {x1:.1f} {top:.1f} L {x2:.1f} {top:.1f}")
    parts.append(f"L {RIGHT_RIGHT} {BAND_BOTTOM} Z")
    return " ".join(parts), BAND_BOTTOM - BAND_H / 2


def _pick_hours(
    hourly: list[dict[str, Any]],
    hass_dt: Any,
    now: Any,
    state: str,
) -> list[dict[str, Any]]:
    """Choose the seven two-hourly entries for the right-hand strip.

    In the morning this is the next seven even hours from now; in the
    evening and at night it is tomorrow's seven fixed slots, so the
    panel always frames the following day the same way.
    """
    parsed = []
    for e in hourly:
        when = _local(hass_dt, e.get("datetime"))
        if when is not None:
            parsed.append((when, e))
    if not parsed:
        return []

    if state == "morning":
        out = []
        for when, e in parsed:
            if when <= now or when.hour % 2:
                continue
            out.append(dict(e, _label=f"{when.hour:02d}"))
            if len(out) == HOUR_SLOTS:
                break
        return out

    tomorrow = (now + _dt.timedelta(days=1)).date()
    out = []
    for hour in EVENING_HOURS:
        for when, e in parsed:
            if when.date() == tomorrow and when.hour == hour:
                out.append(dict(e, _label=f"{hour:02d}"))
                break
    return out


def _build_weather_wall_context(
    widget: dict,
    config: dict,
) -> dict[str, object]:
    """Build the Jinja2 template context for the weather wall widget.

    Args:
        widget: Widget config dict.  Recognised keys: ``entity``,
            ``moon_entity``, ``temperature_entity``,
            ``forecast_days``, ``uv_hide_below``, ``uv_warn_above``,
            ``force_state``, ``x``, ``y``, ``w``, ``h``.
        config: Display config with ``width``, ``height`` and
            ``states``.

    Returns:
        Template context dict consumed by ``weather_wall.svg.j2``.
    """
    from homeassistant.util import dt as hass_dt

    x = widget.get("x", 0)
    y = widget.get("y", 0)
    svg_w = _widget_dim(widget, "w", config["width"] - x)
    svg_h = _widget_dim(widget, "h", config["height"] - y)

    states = config.get("states", {})
    entity_id = widget.get("entity", "")
    entity = states.get(entity_id)

    now = hass_dt.now()

    # Provisional layout, decided on the clock alone.  This has to
    # happen before `base` is built, because `base` carries it into
    # the template and into the early returns below.  It is refined
    # once the states snapshot is available, further down.
    forced = widget.get("force_state", "auto")
    if forced in ("morning", "evening", "night"):
        state = forced
    elif now.hour >= EVENING_FROM:
        state = "evening"
    else:
        state = "morning"

    base: dict[str, object] = {
        "w": svg_w,
        "h": svg_h,
        "state": state,
        "is_night": state == "night",
        "night_w": NIGHT_W,
        "night_h": NIGHT_H,
        "margin": MARGIN,
        "font_xl": FONT_XL,
        "font_l": FONT_L,
        "font_m": FONT_M,
        "font_s": FONT_S,
        "minus_xl": round(FONT_XL * MINUS_SCALE),
        "minus_m": round(FONT_M * MINUS_SCALE),
        "dx_xl": round(FONT_XL * MINUS_DX),
        "dx_m": round(FONT_M * MINUS_DX),
        "left_x": LEFT_X,
        "left_right": LEFT_RIGHT,
        "right_x": RIGHT_X,
        "right_right": RIGHT_RIGHT,
        "hero_cx": HERO_CX,
        "hero_cy": HERO_CY,
        "hero_scale": HERO_SCALE,
        "hour_scale": HOUR_SCALE,
        "day_scale": DAY_SCALE,
        "temp_x": TEMP_X,
        "y_date": Y_DATE,
        "y_uv_label": Y_UV_LABEL,
        "uv_badge_w": UV_BADGE_W,
        "uv_badge_h": UV_BADGE_H,
        "y_uv_badge": Y_UV_BADGE,
        "y_headline": Y_HEADLINE,
        "y_line2": Y_LINE2,
        "y_metrics": Y_METRICS,
        "line2_icon_x": LINE2_ICON_X,
        "line2_text_x": LINE2_TEXT_X,
        "wind_icon_x": WIND_ICON_X,
        "wind_text_x": WIND_TEXT_X,
        "solar_icon_x": SOLAR_ICON_X,
        "y_hour_label": Y_HOUR_LABEL,
        "hour_icon_cy": HOUR_ICON_CY,
        "y_hour_temp": Y_HOUR_TEMP,
        "y_caption": Y_CAPTION,
        "y_rule": Y_RULE,
        "y_day_label": Y_DAY_LABEL,
        "day_icon_cy": DAY_ICON_CY,
        "y_day_temp": Y_DAY_TEMP,
        "y_day_prob": Y_DAY_PROB,
        "y_day_remark": Y_DAY_REMARK,
        "header_max": "",
        **_color_context(),
    }

    if entity is None:
        return {**base, "has_state": False, "date_text": ""}

    attrs = entity.get("attributes", {})
    daily: list[dict[str, Any]] = attrs.get("forecast", []) or []
    hourly: list[dict[str, Any]] = attrs.get("forecast_hourly", []) or []

    if not daily:
        return {**base, "has_state": False, "date_text": ""}

    today = daily[0]
    tomorrow = daily[1] if len(daily) > 1 else {}

    # Sunrise and sunset come from sun.sun, which is always loaded.
    sun_state = states.get("sun.sun", {})
    sun = sun_state.get("attributes", {})
    sunset = _local(hass_dt, sun.get("next_setting"))
    sunrise = _local(hass_dt, sun.get("next_rising"))
    # sun.sun reports only the *next* rising and the *next* setting,
    # so after sunset next_setting is tomorrow's, and comparing it
    # against now says the sun has not gone down.  The entity's own
    # state answers the question directly.
    sun_up = sun_state.get("state") == "above_horizon"
    sunset_ahead = sun_up

    # Night is defined by the sun rather than the clock: in December
    # the panel should go dark at six, in June not until ten.  This
    # is decided here rather than above because it needs the states
    # snapshot, so `base` has to be corrected after the fact.
    if forced == "auto" and state == "evening" and not sun_up:
        state = "night"
    base["state"] = state
    base["is_night"] = state == "night"

    night = state != "morning"

    # ---- headline --------------------------------------------
    if state == "morning":
        headline = _temp(today.get("temperature"))
    else:
        headline = _temp(today.get("templow"))

    # A temperature sensor override applies only to the morning
    # headline, where the number is a live reading rather than a
    # forecast maximum.
    temp_entity = widget.get("temperature_entity", "")
    if state == "morning" and temp_entity:
        override = states.get(temp_entity)
        if override is not None:
            headline = _temp(override.get("state"))

 
    # ---- the second line -------------------------------------
    line2_kind = ""
    line2_text = ""
    if state == "morning":
        low = _temp(today.get("templow"))
        if low["show"]:
            line2_kind = "plain"
            line2_text = f"{_signed(low)} overnight"
    elif sunset_ahead and sunset and sunrise:
        line2_kind = "solar"
        line2_text = (
            f"{sunset.strftime('%H:%M')} \u2013 "
            f"{sunrise.strftime('%H:%M')}"
        )
    else:
        overnight = _overnight_slice(hourly, hass_dt, now)
        preceding = [
            e for e in hourly
            if (when := _local(hass_dt, e.get("datetime"))) is not None
            and now - _dt.timedelta(hours=6) <= when <= now
        ]
        warn = _frost_warning(overnight, preceding)
        if warn:
            line2_kind = "warn"
            line2_text = warn

    # ---- the bottom metrics line -----------------------------
    gust = _num(today.get("wind_gust_speed"))
    speed = _num(today.get("wind_speed"))
    unit = attrs.get("wind_speed_unit", "km/h")
    bearing = _compass(today.get("wind_bearing"))
    if speed is not None and gust is not None:
        wind_text = f"{bearing} {round(speed)}\u2013{round(gust)} {unit}"
    elif speed is not None:
        wind_text = f"{bearing} {round(speed)} {unit}"
    else:
        wind_text = ""

    if state == "morning":
        solar_text = sunset.strftime("%H:%M") if sunset else ""
    elif line2_kind == "solar":
        # Both times are already on the line above.
        solar_text = ""
    else:
        solar_text = sunrise.strftime("%H:%M") if sunrise else ""

    # ---- ultraviolet -----------------------------------------
        # Morning only.  The index is a daily maximum, so in the evening
        # it describes a day that is over, and next to tonight's low or
        # tomorrow's hours it reads as though it applied now.
    hide_below = _num(widget.get("uv_hide_below"))
    hide_below = UV_HIDE_BELOW if hide_below is None else hide_below
    warn_above = _num(widget.get("uv_warn_above"))
    warn_above = UV_WARN_ABOVE if warn_above is None else warn_above
    uv = _num(today.get("uv_index"))
    uv_show = state == "morning" and uv is not None and uv >= hide_below
    uv_warn = uv_show and uv > warn_above

    # ---- the right-hand strip --------------------------------
    hours_raw = _pick_hours(hourly, hass_dt, now, state)
    hours = []
    for i, e in enumerate(hours_raw):
        when = _local(hass_dt, e.get("datetime"))
        # sun.sun gives only the next rising and the next setting,
        # so comparing an arbitrary forecast hour against them gives
        # the wrong answer as soon as either has passed.  Shift both
        # onto the hour's own date and compare within that day.
        # Sunrise and sunset drift a minute or two per day, so for
        # an hour several days out this is approximate; well within
        # tolerance for a two-hourly strip.
        dark = False
        if when is not None and sunset is not None and sunrise is not None:
            up = sunrise.replace(
                year=when.year, month=when.month, day=when.day
            )
            down = sunset.replace(
                year=when.year, month=when.month, day=when.day
            )
            dark = when < up or when >= down
        hours.append({
            "cx": round(RIGHT_X + HOUR_W * (i + 0.5), 1),
            "icon": _icon_name(e, dark),
            "label": e.get("_label", ""),
            "temp": _temp(e.get("temperature")),
        })
    rain_d, rain_mid = _rain_path(hours_raw)
    caption = f"Chance of {_precip_word(hours_raw)}"
    # The daily figure for whichever day the strip covers, not the
    # peak across its hours: a maximum overstates, since fifteen per
    # cent for one hour is not fifteen per cent all day.
    rain_day = today if state == "morning" else tomorrow
    rain_prob = _num(rain_day.get("precipitation_probability"))
    rain_peak = (
        f"{round(rain_prob)}%"
        if rain_prob is not None and rain_prob >= PROB_MIN
        else ""
    )

   # ---- the hero icon, moon or weather ----------------------
    moon_phase = ""
    hero_icon = ""
    if night:
        cover = _num(today.get("cloud_coverage"))
        obscured = cover is not None and cover >= CLOUD_OBSCURES_MOON
        if not obscured and _drop_count(today) == 0:
            moon_state = states.get(
                widget.get("moon_entity", "sensor.moon_phase"), {}
            ).get("state", "")
            moon_phase = _MOON_PHASES.get(str(moon_state), "")
    if not moon_phase:
        # From the daily entry rather than the worst of the hours
        # ahead: a peak overstates the day, since fifteen per cent
        # for one hour is not the same proposition as fifteen per
        # cent all day, and the hero is a summary rather than a
        # warning.
        hero_icon = _icon_name(today, night, HERO_PROB_MIN)

    # ---- the day strip ---------------------------------------
    try:
        want = max(3, min(DAY_COLS, int(widget.get("forecast_days", 7))))
    except (TypeError, ValueError):
        want = DAY_COLS
    first = 1 if state == "morning" else 2
    week = daily[first:first + want]
    # The provider gives a fixed number of days, so the strip is
    # shorter in the evening, where tomorrow has already been spent
    # on the top right.  Divide the width by what actually arrived
    # rather than by the requested count, or the last column sits in
    # a gap and reads as missing data.
    n_days = max(1, len(week))
    day_w = (CANVAS_W - 2 * MARGIN - (n_days - 1) * DAY_GUTTER) / n_days
    days = []
    for i, e in enumerate(week):
        when = _local(hass_dt, e.get("datetime"))
        prob = _num(e.get("precipitation_probability"))
        days.append({
            "cx": round(MARGIN + (day_w + DAY_GUTTER) * i + day_w / 2, 1),
            # The day strip always describes daytime, whatever the
            # hour the panel is rendered at, so never the night icon.
            "icon": _icon_name(e, False),
            "label": when.strftime("%a") if when else "",
            "temp": _temp(e.get("temperature")),
            "prob": (
                f"{round(prob)}%"
                if prob is not None and prob >= PROB_MIN
                else ""
            ),
            "remark": _remarkable(e, when),
        })

    if state != "morning":
        hi = _temp(tomorrow.get("temperature"))
        base["header_max"] = f"max {_signed(hi)}" if hi["show"] else ""

    return {
        **base,
        "has_state": True,
        "date_text": now.strftime("%A %-d %B"),
        "hero_icon": hero_icon,
        "moon_phase": moon_phase,
        "headline": headline,
        "line2_kind": line2_kind,
        "line2_text": line2_text,
        "wind_text": wind_text,
        "solar_text": solar_text,
        "uv_show": uv_show,
        "uv_warn": uv_warn,
        "uv_text": f"{round(uv)}" if uv is not None else "",
        "header_left": "" if state == "morning" else "Tomorrow",
        "header_uv": "",
        "hours": hours,
        "rain_d": rain_d,
        "rain_mid": round(rain_mid, 1),
        "rain_peak": rain_peak,
        "caption": caption,
        "days": days,
    }