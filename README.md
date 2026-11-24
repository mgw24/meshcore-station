# MeshCore Station 0.8.8

**MeshCore Station** is a self-hosted web console for operating and monitoring a MeshCore USB Companion radio. It is built for a Heltec T114 V2 connected to an Ubuntu Linux server or virtual machine, with browser access from desktop and mobile devices.

The project combines messaging, radio diagnostics, node discovery, maps, and historical monitoring in one interface. It is an independent community project, **not an official MeshCore release**.

## AI Development Disclosure

**Most of MeshCore Station has been generated or developed with AI assistance, primarily using OpenAI's ChatGPT.** This includes substantial portions of the application code, architecture, tests, documentation, and development scripts. A human project maintainer directs the work, chooses requirements, configures the deployment, and provides testing and feedback.

**AI-generated or AI-assisted software can contain bugs, security vulnerabilities, and unexpected behavior.** Anyone using or modifying this project should independently review the source code and test it in their own environment before relying on it—especially for radio hardware, firmware updates, message handling, credentials, or services exposed through a network.

MeshCore Station is an independent community project, **not an official MeshCore release** and not endorsed or supported by OpenAI. It is provided under the repository's license, without warranties or guarantees of security, reliability, or fitness for a particular purpose.

## Features and capabilities

- **Messaging:** Send channel and direct messages, browse a compact searchable history and an Overview preview with configured channel names, filter by named channel or direct messages, sort by date or channel across the full archive, and export records, expand messages for details, and compose `@name` channel replies or replies to identified direct contacts.
- **Transmission diagnostics:** Show when the radio accepts a message and record matching channel echoes or supported direct-message acknowledgments. Delivery remains unconfirmed without evidence.
- **Radio Monitor:** One consolidated page for radio health, telemetry, routing diagnostics and outbound evidence. Track RX/TX packet rates, flood versus direct traffic, receive errors, RSSI, SNR when available, noise floor, uptime, and suspected radio resets.
- **Nodes and contacts:** Discover MeshCore contacts, identify companions, repeaters, room servers, and sensors with distinct markers, and maintain a separate address book with nicknames, favorites, and notes.
- **Node map:** Plot nodes with advertised or manually assigned coordinates, including a private location marker for the local station.
- **Radio configuration:** Manage supported radio parameters, messaging channels, path-hash modes, and outgoing region scopes through the web interface.
- **Identity and advertisements:** Configure the local node's fixed coordinates and location-sharing policy, and manually issue local or flood advertisements with confirmation and cooldown safeguards.
- **Monitoring and history:** Store telemetry, messages, and events in PostgreSQL; visualize long-term trends in Grafana and collect operational metrics with Prometheus.
- **Email digests:** Optionally schedule operational summaries of messages, radio health, and issues using configurable SMTP delivery.
- **Firmware management:** Manage supported firmware update jobs through a separate host-side flashing agent.

## How it works

A Docker-based collector communicates with the T114 over USB serial and records radio information in PostgreSQL. The web application reads stored information and submits commands through a queue, keeping the collector as the sole owner of the serial connection. Grafana, Prometheus, and the optional email service run alongside the application.

MeshCore Station runs with **USB Companion firmware**; it does not turn the connected radio into a mesh repeater. Radio acceptance or a transmitted-packet count does not by itself prove that another node received a message. Private map coordinates are not broadcast unless location sharing is explicitly enabled.

**Current release:** `0.8.8` · [Project source](https://github.com/mgw24/meshcore-station)
