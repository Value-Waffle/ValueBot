# --- BEFORE: Monolithic UI Layer ---
# ui_dashboard.py
def on_slider_change(val):
    # Mixed presentation, state management, and raw network logic
    gauge.set_value(val)
    if val > 80:
        gauge.set_color("red")
    
    # Raw I/O block nested inside UI event loop
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 9000))
    sock.sendall(f"TELEMETRY:{val}".encode())
    sock.close()


# --- AFTER: Abstracted Middleware Boundary ---
# telemetry_client.py (Lower-Level Abstraction)
class TelemetryClient:
    def send_metric(self, metric_id: str, value: float) -> bool:
        """Isolated Network I/O layer with a minimal public contract."""
        try:
            with socket.create_connection(("127.0.0.1", 9000), timeout=2) as sock:
                sock.sendall(f"{metric_id}:{value}".encode())
            return True
        except IOError:
            return False

# ui_dashboard.py (Presentation Layer)
# The UI remains 100% blind to networking sockets or protocols
def on_slider_change(val, telemetry: TelemetryClient):
    gauge.set_value(val)
    gauge.set_color("red" if val > 80 else "green")
    
    # Clean, non-blocking call across the boundary line
    telemetry.send_metric(metric_id="slider_position", value=val)