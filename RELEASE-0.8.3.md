# MeshCore Station 0.8.3 — Channel @ Reply hotfix

## Fixed

- Read incoming Public/private channel sender names from the firmware's `Sender Name: message` text envelope, rather than relying on a sender field that may only say `channel`.
- Correctly handle Channel 0 whether the API supplies `'0'` or numeric `0`.
- Prepend `@Sender Name ` to the existing composer draft when replying to a named channel sender, without adding the same mention twice.
- Keep the original channel selection, draft-preservation confirmation, cursor focus, and message-length guard.
- Leave unknown sender names unmentioned rather than fabricating an identity. Direct replies still require an unambiguous radio contact.

## Upgrade from 0.8.2

Copy `meshcore-station-0.8.3-upgrade.zip` to `/tmp/` on Ubuntu and run:

```bash
sudo mkdir -p /tmp/meshcore-083
sudo unzip -oq /tmp/meshcore-station-0.8.3-upgrade.zip -d /tmp/meshcore-083
sudo bash /tmp/meshcore-083/install.sh
```

Only the API container is rebuilt. No database migration, channel/radio change, collector restart, email change or firmware update is required. The installer backs up overwritten files. The new Reply workflow was tested with a mocked browser environment; it still needs confirmation on the live UI.

After verifying the fix, publish with `bash scripts/publish-0.8.3.sh` as the normal `meshcore` user. The release uses tag `v0.8.3` and includes a version consistency check.
