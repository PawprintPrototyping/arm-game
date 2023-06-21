import asyncio
import logging

from asyncio_paho import AsyncioPahoClient
import json

from flippies.flipdigits import FlipDigits
import structlog

MQTT_HOST="localhost"
DEBUG=True
DEVICE="/dev/ttyUSB4"
BAUDRATE=57600

#structlog.configure(
#    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
#)

log = structlog.getLogger(__name__)
flipdigits = FlipDigits(DEVICE, BAUDRATE, debug=DEBUG)

async def on_connect_async(client, userdata, flags_dict, result):
    log.info("on_connect", client=client, userdata=userdata, flags_dict=flags_dict, result=result)
    client.subscribe("/display/digits/#")

async def on_message_async(client, flipdigits, msg):
    log.info("on_message_async", flipdigits=flipdigits, topic=msg.topic, payload=msg.payload)
    data = None
    try:
        data = json.loads(msg.payload.encode("utf8"))
    except json.JSONDecodeError:
        log.warn("Payload is not JSON decodeable", mqtt_msg=msg)

    match msg.topic:
        case "/display/digits/clear":
            flipdigits.clear()
        case "/display/digits/set_number":
            delay = data.get("delay", 0)
            flipdigits.set_number(data["number"], delay)
        case "/display/digits/marquee":
            delay = data.get("delay", 0.1)
            flipdigits.marquee(delay)
        case "/display/digits/set_digit":
            flipdigits.set_digit(data["address"], data["number"])

    print(f"Received from {msg.topic}: {str(msg.payload)}")


async def main():
    async with AsyncioPahoClient() as client:
        client.asyncio_listeners.add_on_connect(on_connect_async)
        client.asyncio_listeners.add_on_message(on_message_async)
        client.user_data_set(flipdigits)
        await client.asyncio_connect(MQTT_HOST)

        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())