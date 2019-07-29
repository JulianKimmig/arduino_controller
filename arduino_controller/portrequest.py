import struct

STARTBYTE = b'\x02'
STARTBYTEPOSITION = 0
COMMANDBYTEPOSITION = 1
LENBYTEPOSITION = 2
DATABYTEPOSITION = 3


def generate_checksum(array):
    try:
        array = [ord(i) for i in array]
    except:
        pass
    sum1 = 0
    sum2 = 0
    for i in array:
        sum1 = (sum1 + i) % 255
        sum2 = (sum2 + sum1) % 255
    return sum2 * 256 + sum1


def generate_port_message(cmd, datalength, *args):
    assert len(args) >= datalength
    return generate_request(cmd, args[:datalength])


def generate_request(command, data):
    a = [2, command, len(data), *data]
    a.extend(struct.pack(">H", generate_checksum(a)))
    return bytearray(a)


def validate_buffer(port):
    #print(port.read_buffer)
    try:
        firststart = port.read_buffer.index(STARTBYTE)
    except ValueError:
        firststart = 0
        port.read_buffer = []

    bufferlength = len(port.read_buffer[firststart:])
    if bufferlength >= DATABYTEPOSITION + 2:
        datalength = ord(port.read_buffer[firststart + LENBYTEPOSITION])
        if bufferlength >= DATABYTEPOSITION + datalength + 2:
            databuffer = port.read_buffer[
                firststart
                + DATABYTEPOSITION : firststart
                + DATABYTEPOSITION
                + datalength
            ]
            checksum, = struct.unpack(
                ">H",
                b"".join(
                    port.read_buffer[
                        firststart
                        + DATABYTEPOSITION
                        + datalength : firststart
                        + DATABYTEPOSITION
                        + datalength
                        + 2
                    ]
                ),
            )

            if checksum == generate_checksum(
                port.read_buffer[firststart : firststart + DATABYTEPOSITION + datalength]
            ):
                port.board.receive_from_port(
                    cmd=ord(port.read_buffer[firststart + COMMANDBYTEPOSITION]),
                    data=b"".join(databuffer),
                )
            port.read_buffer = port.read_buffer[
                firststart + DATABYTEPOSITION + datalength + 2 :
            ]
