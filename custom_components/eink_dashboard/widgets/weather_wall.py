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
  hours on the right, the next seven days below.
* **evening** — tonight's minimum as the headline, tomorrow's hours
  on the right, the seven days from the day after tomorrow below.
* **night** — as evening, with the tonight block on a black ground.
"""

from __future__ import annotations

from typing import Any

import markupsafe

from ..svg_render import _weather_svg_filter
from ._helpers import _color_context, _widget_dim

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
HERO_SCALE_PX = 92  # rendered icon size
TEMP_X = 128
Y_DATE = 44
Y_UV_LABEL = 110
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
HOUR_ICON_CY = 120
HOUR_ICON_PX = 42
Y_HOUR_TEMP = Y_LINE2
BAND_BOTTOM = 242
BAND_H = 46
Y_CAPTION = Y_METRICS

# The rule, and the seven-day strip below it.
Y_RULE = 284
DAY_COLS = 7
DAY_GUTTER = 12
DAY_W = (CANVAS_W - 2 * MARGIN - (DAY_COLS - 1) * DAY_GUTTER) / DAY_COLS
Y_DAY_LABEL = 316
DAY_ICON_CY = 346
DAY_ICON_PX = 50
Y_DAY_TEMP = 400
Y_DAY_PROB = 426
Y_DAY_REMARK = 450

# Night block.
NIGHT_W = RIGHT_X
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
# two or three drops.
PRECIP_LIGHT = 0.5
PRECIP_HEAVY = 2.0

# Probability bands used where no amount is forecast.
PROB_LIGHT = 40
PROB_HEAVY = 70

# Lowest precipitation probability worth printing.
PROB_MIN = 10

_COMPASS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)

# HA moon phase states to the phase key used by the template.
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


def _compass(bearing: Any) -> str:
    """Return a sixteen-point compass abbreviation for a bearing."""
    n = _num(bearing)
    if n is None:
        return ""
    return _COMPASS[int((n % 360) / 22.5 + 0.5) % 16]


def _local(hass_dt: Any, raw: str | None):
    """Parse an ISO timestamp into local time, or return ``None``."""
    if not raw:
        return None
    parsed = hass_dt.parse_datetime(raw)
    return hass_dt.as_local(parsed) if parsed else None


def _drop_count(entry: dict[str, Any]) -> int:
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
    if prob is None or prob < PROB_MIN:
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


def _icon(condition: str, size: int) -> object:
    """Return an inline icon for a condition, or an empty string."""
    try:
        return _weather_svg_filter(condition, size)
    except (KeyError, FileNotFoundError):
        return ""


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
    temps = [t for e in overnight if (t := _num(e.get("temperature")))
             is not None]
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
        clouds = [c for e in overnight
                  if (c := _num(e.get("cloud_coverage"))) is not None]
        winds = [w for e in overnight
                 if (w := _num(e.get("wind_speed"))) is not None]
        clear = not clouds or min(clouds) < FROST_GROUND_CLOUD
        calm = not winds or max(winds) < FROST_GROUND_WIND
        if clear and calm:
            return "Ground frost"
    return ""


def _remarkable(day: dict[str, Any], week: list[dict[str, Any]]) -> str:
    """Return a short note when one measure stands out, else "".

    Interim implementation: each candidate is compared against the
    spread of the days on screen.  The intended basis is a percentile
    against a thirty-year climatology for the calendar date, which
    needs an archive this widget does not yet carry, so treat the
    thresholds here as placeholders.
    """
    def spread(key: str) -> tuple[float, float] | None:
        vals = [v for d in week if (v := _num(d.get(key))) is not None]
        if len(vals) < 3:
            return None
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        return mean, var ** 0.5

    candidates: list[tuple[float, str]] = []

    uv = _num(day.get("uv_index"))
    s = spread("uv_index")
    if uv is not None and s and s[1] > 0 and uv >= 6:
        candidates.append(((uv - s[0]) / s[1], f"UV {round(uv)}"))

    gust = _num(day.get("wind_gust_speed"))
    s = spread("wind_gust_speed")
    if gust is not None and s and s[1] > 0 and gust >= 50:
        candidates.append(
            ((gust - s[0]) / s[1], f"gust {round(gust)}")
        )

    low = _num(day.get("templow"))
    s = spread("templow")
    if low is not None and s and s[1] > 0:
        z = abs(low - s[0]) / s[1]
        t = _temp(low)
        sign = "\u2212" if t["neg"] else ""
        candidates.append((z, f"min {sign}{t['text']}"))

    if not candidates:
        return ""
    best = max(candidates, key=lambda c: c[0])
    return best[1] if best[0] >= 1.3 else ""


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
    panel always frames the day the same way.
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

    tomorrow = (now + __import__("datetime").timedelta(days=1)).date()
    out = []
    for hour in EVENING_HOURS:
        for when, e in parsed:
            if when.date() == tomorrow and when.hour == hour:
                out.append(dict(e, _label=f"{hour:02d}"))
                break
    return out


def _column(
    entry: dict[str, Any],
    cx: float,
    icon_px: int,
) -> dict[str, object]:
    """Build the shared parts of one forecast column."""
    return {
        "cx": round(cx, 1),
        "icon_svg": _icon(str(entry.get("condition", "")), icon_px),
        "dark": _is_dark_cloud(entry),
    }


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
    import datetime as _dt

    from homeassistant.util import dt as hass_dt

    x = widget.get("x", 0)
    y = widget.get("y", 0)
    svg_w = _widget_dim(widget, "w", config["width"] - x)
    svg_h = _widget_dim(widget, "h", config["height"] - y)

    states = config.get("states", {})
    entity_id = widget.get("entity", "")
    entity = states.get(entity_id)

    now = hass_dt.now()

    forced = widget.get("force_state", "auto")
    if forced in ("morning", "evening", "night"):
        state = forced
    elif now.hour >= NIGHT_FROM:
        state = "night"
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
        "minus_s": round(FONT_S * MINUS_SCALE),
        "dx_xl": round(FONT_XL * MINUS_DX),
        "dx_m": round(FONT_M * MINUS_DX),
        "dx_s": round(FONT_S * MINUS_DX),
        "left_x": LEFT_X,
        "left_right": LEFT_RIGHT,
        "right_x": RIGHT_X,
        "right_right": RIGHT_RIGHT,
        "hero_cx": HERO_CX,
        "hero_cy": HERO_CY,
        "hero_px": HERO_SCALE_PX,
        "temp_x": TEMP_X,
        "y_date": Y_DATE,
        "y_uv_label": Y_UV_LABEL,
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
        "band_bottom": BAND_BOTTOM,
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
    sun = states.get("sun.sun", {}).get("attributes", {})
    sunset = _local(hass_dt, sun.get("next_setting"))
    sunrise = _local(hass_dt, sun.get("next_rising"))
    sunset_ahead = sunset is not None and sunset > now

    # ---- headline --------------------------------------------
    if state == "morning":
        hero_entry = today
        headline = _temp(today.get("temperature"))
        uv_source = today
    else:
        hero_entry = today
        headline = _temp(today.get("templow"))
        uv_source = tomorrow

    # Temperature sensor override applies only to the morning
    # headline, where the number is a live reading rather than a
    # forecast maximum.
    temp_entity = widget.get("temperature_entity", "")
    if state == "morning" and temp_entity:
        override = states.get(temp_entity)
        if override is not None:
            headline = _temp(override.get("state"))

    # ---- the hero icon, moon or weather ----------------------
    moon_phase = ""
    hero_icon: object = ""
    if state in ("evening", "night"):
        cover = _num(today.get("cloud_coverage"))
        obscured = cover is not None and cover >= CLOUD_OBSCURES_MOON
        if not obscured and _drop_count(today) == 0:
            moon_state = states.get(
                widget.get("moon_entity", "sensor.moon_phase"), {}
            ).get("state", "")
            moon_phase = _MOON_PHASES.get(str(moon_state), "")
    if not moon_phase:
        hero_icon = _icon(
            str(hero_entry.get("condition", "")), HERO_SCALE_PX
        )

    # ---- the second line -------------------------------------
    line2_kind = ""
    line2_text = ""
    if state == "morning":
        low = _temp(today.get("templow"))
        if low["show"]:
            line2_kind = "plain"
            line2_text = f"{'\u2212' if low['neg'] else ''}" \
                         f"{low['text']} overnight"
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
            if (w := _local(hass_dt, e.get("datetime"))) is not None
            and now - _dt.timedelta(hours=6) <= w <= now
        ]
        warn = _frost_warning(overnight, preceding)
        if warn:
            line2_kind = "warn"
            line2_text = warn

    # ---- the bottom metrics line -----------------------------
    wind_src = today if state == "morning" else today
    gust = _num(wind_src.get("wind_gust_speed"))
    speed = _num(wind_src.get("wind_speed"))
    unit = attrs.get("wind_speed_unit", "km/h")
    if speed is not None and gust is not None:
        wind_text = (
            f"{_compass(wind_src.get('wind_bearing'))} "
            f"{round(speed)}\u2013{round(gust)} {unit}"
        )
    elif speed is not None:
        wind_text = (
            f"{_compass(wind_src.get('wind_bearing'))} "
            f"{round(speed)} {unit}"
        )
    else:
        wind_text = ""

    if state == "morning":
        solar_text = sunset.strftime("%H:%M") if sunset else ""
    elif line2_kind == "solar":
        solar_text = ""
    else:
        solar_text = sunrise.strftime("%H:%M") if sunrise else ""

    # ---- ultraviolet -----------------------------------------
    hide_below = _num(widget.get("uv_hide_below")) or UV_HIDE_BELOW
    warn_above = _num(widget.get("uv_warn_above")) or UV_WARN_ABOVE
    uv = _num(uv_source.get("uv_index"))
    uv_show = uv is not None and uv >= hide_below
    uv_warn = uv is not None and uv > warn_above

    # ---- the right-hand strip --------------------------------
    hours_raw = _pick_hours(hourly, hass_dt, now, state)
    hours = []
    for i, e in enumerate(hours_raw):
        cx = RIGHT_X + HOUR_W * (i + 0.5)
        hours.append({
            **_column(e, cx, HOUR_ICON_PX),
            "label": e.get("_label", ""),
            "temp": _temp(e.get("temperature")),
        })
    rain_d, rain_mid = _rain_path(hours_raw)
    caption = f"Chance of {_precip_word(hours_raw)}"

    # ---- the seven-day strip ---------------------------------
    try:
        want = max(3, min(DAY_COLS, int(widget.get("forecast_days", 7))))
    except (TypeError, ValueError):
        want = DAY_COLS
    first = 1 if state == "morning" else 2
    week = daily[first:first + want]
    days = []
    for i, e in enumerate(week):
        cx = MARGIN + (DAY_W + DAY_GUTTER) * i + DAY_W / 2
        when = _local(hass_dt, e.get("datetime"))
        prob = _num(e.get("precipitation_probability"))
        days.append({
            **_column(e, cx, DAY_ICON_PX),
            "label": when.strftime("%a") if when else "",
            "temp": _temp(e.get("temperature")),
            "prob": (
                f"{round(prob)}%" if prob is not None and prob >= PROB_MIN
                else ""
            ),
            "remark": _remarkable(e, week),
        })

    if state == "morning":
        date_text = now.strftime("%A %-d %B")
        header_left = ""
    else:
        when = _local(hass_dt, tomorrow.get("datetime"))
        date_text = now.strftime("%A %-d %B")
        hi = _temp(tomorrow.get("temperature"))
        header_left = "Tomorrow"
        base["header_max"] = (
            f"max {'\u2212' if hi['neg'] else ''}{hi['text']}"
            if hi["show"] else ""
        )

    return {
        **base,
        "has_state": True,
        "date_text": date_text,
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
        "header_left": header_left,
        "header_uv": (
            f"UV {round(uv)}" if uv_show and state != "morning" else ""
        ),
        "hours": hours,
        "rain_d": rain_d,
        "rain_mid": round(rain_mid, 1),
        "caption": caption,
        "days": days,
    }