import threading
import time

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.client import request_current_from_ammeter


def run_greenlee_emulator(port: int = 5001) -> GreenleeAmmeter:
    greenlee = GreenleeAmmeter(port)
    threading.Thread(target=greenlee.start_server, daemon=True).start()
    return greenlee


def run_entes_emulator(port: int = 5002) -> EntesAmmeter:
    entes = EntesAmmeter(port)
    threading.Thread(target=entes.start_server, daemon=True).start()
    return entes


def run_circutor_emulator(port: int = 5003) -> CircutorAmmeter:
    circutor = CircutorAmmeter(port)
    threading.Thread(target=circutor.start_server, daemon=True).start()
    return circutor


if __name__ == "__main__":
    # Start each ammeter emulator in a separate daemon thread (ports 5001-5003
    # avoid macOS ControlCenter conflict on port 5000).
    greenlee = run_greenlee_emulator(5001)
    entes = run_entes_emulator(5002)
    circutor = run_circutor_emulator(5003)

    # Allow TCP servers to bind and start listening
    time.sleep(1.0)

    try:
        g_val = request_current_from_ammeter(5001, b"MEASURE_GREENLEE -get_measurement")
        e_val = request_current_from_ammeter(5002, b"MEASURE_ENTES -get_data")
        c_val = request_current_from_ammeter(
            5003, b"MEASURE_CIRCUTOR -get_measurement -current"
        )
        print(
            f"\nSummary -> Greenlee: {g_val:.4f} A | ENTES: {e_val:.4f} A | CIRCUTOR: {c_val:.6f} A"
        )
    finally:
        greenlee.stop()
        entes.stop()
        circutor.stop()
