import socket
import threading
import time
import random
from abc import ABC, abstractmethod

NotImplementedErrorMsg = "Subclasses must implement this property."

class AmmeterEmulatorBase(ABC):
    def __init__(self, port: int):
        self.port = port
        self._stop_event = threading.Event()
        random.seed(time.time())  # Seed the random number generator for each instance

    def stop(self) -> None:
        """Signal the emulator server loop to stop gracefully."""
        self._stop_event.set()

    def start_server(self):
        """
        Starts the server to listen for client requests.
        Runs until stop() is called, handling one client request at a time.
        """
        self._stop_event.clear()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('localhost', self.port))
            s.listen()
            s.settimeout(0.2)
            print(f"{self.__class__.__name__} is running on port {self.port}")
            while not self._stop_event.is_set():
                try:
                    conn, addr = s.accept()
                except socket.timeout:
                    continue
                with conn:
                    conn.settimeout(2.0)
                    print(f"Connected by {addr}")
                    try:
                        data = conn.recv(1024)
                    except socket.timeout:
                        continue
                    if data == self.get_current_command:
                        # Call the specific measure_current() method defined in subclasses
                        current = self.measure_current()
                        conn.sendall(str(current).encode('utf-8'))

    @property
    @abstractmethod
    def get_current_command(self) -> bytes:
        """
        This property must be implemented by each subclass to provide the specific
        command to get the current measurement.
        """
        raise NotImplementedError(NotImplementedErrorMsg)

    @abstractmethod
    def measure_current(self) -> float:
        """
        This method must be implemented by each subclass to provide the specific
        logic for current measurement.
        """
        raise NotImplementedError(NotImplementedErrorMsg)

