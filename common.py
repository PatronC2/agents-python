import struct

def write_delimited(sock, message):
    data = message.SerializeToString()
    length = struct.pack(">I", len(data))
    sock.sendall(length + data)

def read_delimited(sock, message_class):
    len_bytes = sock.recv(4)
    if not len_bytes:
        raise EOFError("[common] No bytes read (connection closed before message length)")
    if len(len_bytes) < 4:
        raise ValueError("[common] Incomplete length prefix")

    length = struct.unpack(">I", len_bytes)[0]
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise EOFError("[common] Socket closed before full message received")
        data += chunk

    msg = message_class()
    msg.ParseFromString(data)
    return msg
