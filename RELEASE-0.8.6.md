# MeshCore Station 0.8.6

## Message history: configured channel names

- Incoming channel messages whose sender is the generic firmware label `channel` now show the live configured **channel name** in the compact sender column (for example, `Public` or a configured slot 5 name).
- Channel messages in both directions show their configured channel name **and numeric slot** in the conversation column and expanded details; sender names on outgoing messages remain intact.
- Expanded incoming details retain the best available actual sender identity when it appears in the received message's sender envelope, avoiding confusion between a channel name and the person who sent the message.
- A missing or unnamed channel falls back to `Channel N`; all names are HTML-escaped for safe display.
- Channel renames are reflected by the next normal status refresh without rewriting stored history. History filtering, pagination, search, CSV, and `@ Reply` routing still use the original channel slot and are unchanged.
- The message-history conversation column is widened slightly on desktop/tablet; on phones the existing compact layout is preserved.

## Upgrade and compatibility

This is an **API/web presentation release** for an installed **0.8.5** station. It updates the web/API source and version metadata, with no collector, firmware, PostgreSQL schema, Grafana dashboard or radio changes. The installer checks source baselines, backs up existing source files and rebuilds **only the API container**. Make a separate database backup first. Review any local-source mismatch instead of bypassing checks blindly.

`README.md` remains a concise project introduction; installation instructions are provided in the upgrade archive.
