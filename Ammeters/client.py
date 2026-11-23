from socket import AF_INET, SOCK_STREAM, socket, timeout as SocketTimeout


def request_current_from_ammeter(
    port: int,
    command: bytes,
    host: str = "localhost",
    timeout: float = 2.0,
    verbose: bool = True,
) -> float:
    """Request a single current reading from an ammeter emulator over TCP.

    Returns the parsed float current in Amperes, or raises an exception on
    connection/timeout/protocol errors.
    """
    with socket(AF_INET, SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            s.sendall(command)
            data = s.recv(1024)
        except SocketTimeout as exc:
            raise TimeoutError(
                f"Timed out waiting for response from {host}:{port}"
            ) from exc
        except OSError as exc:
            raise ConnectionError(
                f"Failed to communicate with ammeter at {host}:{port}: {exc}"
            ) from exc

    if not data:
        raise ValueError(
            f"Empty response from ammeter at {host}:{port} (check command: {command!r})"
        )

    decoded = data.decode("utf-8").strip()
    try:
        current = float(decoded)
    except ValueError as exc:
        raise ValueError(
            f"Invalid numeric payload from {host}:{port}: {decoded!r}"
        ) from exc

    if verbose:
        print(f"Received current measurement from port {port}: {current} A")
    return current
