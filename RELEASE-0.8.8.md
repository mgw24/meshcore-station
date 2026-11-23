# MeshCore Station 0.8.8

## Quality and usability release

- **Message History:** Clearly labeled channel filter with live channel names for slots 0–7, All channels and DMs, or Direct messages only. Search and Received/Sent filters can be combined with channel filtering.
- **Global server-side sorting:** Newest first, oldest first, channel 0→7, or channel 7→0. Messages within a channel are newest first; direct and unknown destinations follow all channel groups.
- **Stable paging:** Direction, channel, search, and sort are applied to the complete PostgreSQL archive. The keyset cursor includes the channel group when relevant, so loading subsequent pages does not re-sort only the visible rows.
- **Quality improvements:** Preserve the selected channel when status refreshes, maintain ordering during automatic refresh, prevent stale page requests from clearing current loading indicators, use clearer result labels, and handle invalid timestamps safely.
- **CSV export safety:** Stream the full history rather than silently stopping at 10,000 rows, and neutralize spreadsheet formulas in user-controlled message fields.
- **Backend cleanup:** Replace deprecated FastAPI startup hook with the lifespan API.
- **No radio-side changes:** No collector, firmware, radio configuration, PostgreSQL schema or message records changed. Existing Grafana and radio settings are untouched.

## Release notes

This is an incremental update from 0.8.7. The API container is rebuilt, and active web sessions may require a browser refresh. Existing chat history and saved channels remain intact. CSV export still downloads the full archive (it is labeled **Export all CSV**); filters apply to the interactive history.
