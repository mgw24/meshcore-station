# MeshCore Station 0.8.7

## Overview recent messages: configured channel names

- In **Overview → Recent messages**, received channel entries that previously said `channel` now use the same live channel-name resolver as **Messages → Message History**.
- Example: `#5 · Received · LongFast` instead of `#5 · Received · channel`, and `#0 · Received · Public` for the public channel.
- A slot without a configured name uses `Channel N`; channel renames update both views on the normal refresh.
- Real sender names and all outgoing/direct messages retain their existing identities. Sender information in full message details is not lost.
- No message, radio, collector, database, channel-key, or firmware changes.

## Upgrade

Install on a current **0.8.6** MeshCore Station; API/web files and release metadata only. The installer verifies file checksums and version, refuses unexpected local edits, backs up source files, and rebuilds only the API container. Details and exact commands are in `UPGRADE-INSTRUCTIONS.md` in the upgrade ZIP.
