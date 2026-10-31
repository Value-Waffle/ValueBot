# --- BEFORE: Monolithic Network Loop ---
# server.py
async def handle_client(reader, writer):
    buffer = b""
    while True:
        data = await reader.read(1024)
        buffer += data
        
        # Mixed TCP stream slicing, application parsing, and business logic
        if b"\n" in buffer:
            packet, buffer = buffer.split(b"\n", 1)
            if packet.startswith(b"AUTH:"):
                user = packet.split(b":")[1].decode()
                db.log_login(user)  # Database call stuck inside byte parsing loop
                writer.write(b"OK\n")


# --- AFTER: Abstracted Transport State Machine ---
# transport/framing.py (Pure Logical Abstraction)
class PacketStreamParser:
    """Pure state machine: Zero dependencies on async loops, sockets, or databases."""
    def __init__(self):
        self._buffer = b""

    def feed(self, chunk: bytes) -> list[str]:
        self._buffer += chunk
        packets = []
        while b"\n" in self._buffer:
            packet, self._buffer = self._buffer.split(b"\n", 1)
            packets.append(packet.decode().strip())
        return packets

# server.py (Application/Orchestration Layer)
async def handle_client(reader, writer):
    parser = PacketStreamParser()
    while True:
        data = await reader.read(1024)
        # The transport layer handles byte splitting safely; application handles routing
        for packet in parser.feed(data):
            if packet.startswith("AUTH:"):
                db.log_login(packet.split(":")[1])
                writer.write(b"OK\n")