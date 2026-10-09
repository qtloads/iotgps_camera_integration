import logging
import socket
import time
from datetime import datetime

SERVER_HOST = "vltsgw.karnataka.gov.in"
SERVER_PORT = 8085
SEND_INTERVAL_SECONDS = 10
CLIENT_PORT_START = 50001

# Replace these entries with the 15 unique, 15-digit vehicle IMEIs.
IMEI_LIST = [
    "358250331862309",
    "358250331826254",
    "358250331804160",
    "358250331847573",
    "358250331834845",
    "358250331856095",
    "358250331854934",
    "358250331827955",
    "358250331852789",
    "358250331861574",
    "358250331861103",
    "358250331849280",
    "358250331853209",
    "358250331849140",
    "358250331802750"
]

# The fixed GPS payload from the original packet builder.
GPS_PACKET_DATA = "$Header,iTriangle1,BHARAT101C_0415,NR,01,L,358250331297472,KA1234,1,02012025,033538,12.9838889,N,77.5873418,E,0.0,89,15,196.0,1.70,1.10,Airtel,1,1,26.0,4.0,0,C,19,404,10,c64,213,30,98,5679,30,0,0,26,0,0,24,0,0,1001,01,699412,0.018,0.018,0,()*22"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def create_packet(imei: str, date, time) -> str:
    packet = f"$Header,iTriangle1,BHARAT101C_0415,NR,01,L,{imei},KA1234,1,{date},{time},12.9838889,N,77.5873418,E,0.0,89,15,196.0,1.70,1.10,Airtel,1,1,26.0,4.0,0,C,19,404,10,c64,213,30,98,5679,30,0,0,26,0,0,24,0,0,1001,01,699412,0.018,0.018,0,()*22"
    return (packet)


def validate_configuration() -> None:
    if SERVER_HOST == "YOUR_SERVER_IP_OR_DOMAIN":
        raise ValueError("Set SERVER_HOST to the TCP server address.")
    if len(IMEI_LIST) != 15:
        raise ValueError("IMEI_LIST must contain exactly 15 IMEI numbers.")
    if len(set(IMEI_LIST)) != 15:
        raise ValueError("IMEI_LIST must contain 15 unique IMEI numbers.")
    if any(len(imei) != 15 or not imei.isdigit() for imei in IMEI_LIST):
        raise ValueError("Each IMEI must be a 15-digit number.")


def main() -> None:
    # validate_configuration()
    connections: dict[str, socket.socket] = {}

    try:
        while True:
            cycle_started = time.monotonic()
            cycle_date = str(datetime.now().strftime("%d%m%Y"))
            cycle_time = str(datetime.now().strftime("%H%M%S"))
            logging.info(f"Cycle date/time: {cycle_date} and {cycle_time}")

            for index, imei in enumerate(IMEI_LIST):
                client_port = CLIENT_PORT_START + index
                sock = connections.get(imei)
                try:
                    if sock is None:
                        sock = socket.create_connection(
                            (SERVER_HOST, SERVER_PORT),
                            timeout=10,
                            source_address=("0.0.0.0", client_port),
                        )
                        connections[imei] = sock
                        logging.info(
                            "Connected for IMEI %s using client port %s",
                            imei,
                            client_port,
                        )

                    packet = create_packet(imei, cycle_date, cycle_time)
                    logging.info(f"[{imei}] Packet : {packet}")
                    sock.sendall(packet.encode("utf-8"))
                    logging.info("Sent packet for IMEI %s", imei)
                except OSError:
                    logging.exception("TCP send failed for IMEI %s", imei)
                    if sock is not None:
                        sock.close()
                    connections.pop(imei, None)

            wait_seconds = SEND_INTERVAL_SECONDS - (
                time.monotonic() - cycle_started
            )
            if wait_seconds > 0:
                time.sleep(wait_seconds)
    except KeyboardInterrupt:
        logging.info("Stopping GPS packet sender.")
    finally:
        for sock in connections.values():
            sock.close()
        logging.info("All TCP connections closed.")


# if __name__ == "__main__":
#     main()
