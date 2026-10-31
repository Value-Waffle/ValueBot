# price_action (reserved)

Owns OHLCV history, adjusted series and technical indicators. Not implemented
in v1 and registers no MCP tools.

Implementation constraints when it is built:

- own storage under `${PLUGIN_DATA}/modules/price_action/`;
- expose only the `PriceAPI` protocol in `api.py`;
- do not import `fundamentals`, `analysis`, `reports` or `thesis`;
- relative valuation may later be requested by `analysis` through an optional
  dependency, never by price importing analysis.
