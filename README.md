## About this fork

This is a personal fork of [hass-eink-dashboard](https://github.com/cryptomilk/hass-eink-dashboard) by
Andreas Schneider, an excellent Home Assistant integration for
rendering dashboards to e-ink displays. All credit for the
integration itself, its rendering pipeline, colour dithering and
editor belongs to him; this fork builds on that work and would not
exist without it.

The fork adds one widget, `weather_wall`: a full-panel forecast
layout designed for wall-mounted colour e-ink, developed on a
Pimoroni Inky Frame 7.3" (Spectra 6). It shows the day or night
ahead, a two-hourly strip with a rain-probability profile, and a
week's outlook, with two-colour icons, moon phases, derived frost
warnings, and notes when a day is unusual for the time of year.

**Status: work in progress.** It works daily on one panel, but it
currently assumes a 5:3 landscape display and a six-colour palette,
and has been tested only with the Met Office integration. Making it
general enough to offer upstream is the aim, not yet the reality.

Not included in the repository, by design:

- `climatology.json`, which is location-specific; build your own
  with `tools/build_climatology.py` (see `tools/README.md`). The
  widget works without it, minus the "unusual" notes.
- Third-party fonts. Roboto is the default; others can be supplied
  through the integration's font directory option.

This fork is not affiliated with or endorsed by the original author.
Licensed under the Apache License 2.0, as is the original.
