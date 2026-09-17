# Climatology

`build_climatology.py` builds `climatology.json`, the percentile
table the weather wall widget uses to decide whether a day is
unusual for the time of year.

Neither the table nor the coordinates it was built from are
tracked, since both disclose a location.

To build your own:

1. Create `tools/location.json`:

       {"latitude": x.xx, "longitude": x.xx}

2. Run `python3 tools/build_climatology.py` from the repository
   root.

It writes `custom_components/eink_dashboard/climatology.json`.
Without that file the widget still works; the remarkable line under
each day is simply suppressed.