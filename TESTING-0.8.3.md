# MeshCore Station 0.8.3 — QA checklist

After installing and refreshing the browser:

1. Open **Messages**, expand a received Public (Channel 0) message that starts `HamHock: ...` (or another sender name).
2. Select **@ Reply**. The composer should switch to Public (#0), start with `@HamHock `, focus the text field, and show the reply context.
3. Try with an unsent draft; it should preserve the draft, prepend the mention once, and warn before switching destination.
4. Direct replies should select a unique radio contact rather than insert a channel mention.
5. If a message does not provide a sender name, the app must **not** insert `@channel` or guess an identity.

An `@name` is plain text on a MeshCore channel, not an acknowledgment or guaranteed notification. The update does not transmit a message automatically.
