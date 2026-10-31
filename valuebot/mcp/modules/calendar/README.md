# calendar (reserved)

Owns the corporate calendar: earnings dates, dividends, splits and fiscal
period events. Not implemented in v1 and registers no MCP tools.

Implementation constraints when it is built:

- own storage under `${PLUGIN_DATA}/modules/calendar/`;
- expose only the `CalendarAPI` protocol in `api.py`;
- do not import `fundamentals`, `analysis`, `reports` or `thesis`.
