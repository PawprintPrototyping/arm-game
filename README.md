# opensauce23
Code, design files, etc for the coolest robot game at OpenSauce 2023 (and beyond!)

# MQTT System Architecture

The arm-game uses message passing via MQTT topics to drive each gameplay component.  Here's a state diagram showing how each topic drives the gameplay state:

![MQTT Topic Architecture](https://raw.githubusercontent.com/PawprintPrototyping/arm-game/refs/heads/main/docs/MQTT%20Service%20Architecture.png)

Another overview of how each topic queue and component interacts:

![MQTT Topic Map](https://raw.githubusercontent.com/PawprintPrototyping/arm-game/refs/heads/main/docs/MQTT%20Topic%20Map.png)

Detailed MQTT Topic API documentation can be found in [the docs folder](https://github.com/PawprintPrototyping/arm-game/tree/main/docs).