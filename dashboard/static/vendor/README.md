# Vendored frontend libraries

These bundles are committed so the dashboard works on a LAN-only pi with no
internet access. Both are permissively licensed (MIT).

| File                        | Package                                       | Version | Source URL                                                                              |
| --------------------------- | --------------------------------------------- | ------- | ---------------------------------------------------------------------------------------- |
| `alpine-3.14.1.min.js`      | [alpinejs](https://alpinejs.dev/)             | 3.14.1  | https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js                             |
| `mqtt-5.10.1.min.js`        | [mqtt](https://github.com/mqttjs/MQTT.js)     | 5.10.1  | https://cdn.jsdelivr.net/npm/mqtt@5.10.1/dist/mqtt.min.js                                |

## Refreshing

To bump versions, edit `refresh.sh` in this directory, run it, delete the old
files, and update the script tags in `../index.html`. Nothing else uses these
paths.

## Licenses

* Alpine.js — MIT © Caleb Porzio and contributors
  <https://github.com/alpinejs/alpine/blob/main/LICENSE.md>
* MQTT.js  — MIT © MQTT.js Contributors
  <https://github.com/mqttjs/MQTT.js/blob/main/LICENSE>
