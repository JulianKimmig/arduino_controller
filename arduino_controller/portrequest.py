import numpy as np

STARTBYTE = b"\x02"
STARTBYTEPOSITION = 0
COMMANDBYTEPOSITION = 1
LENBYTEPOSITION = 2
DATABYTEPOSITION = 3

np.seterr(over='ignore')
def generate_checksum(array):
    sum1 = np.uint8(0)
    sum2 = np.uint8(0)
    for i in np.array(array, dtype=np.uint8):
        sum1 = sum1 + i
        sum2 = sum2 + sum1
    return sum2 * np.uint16(256) + sum1


def generate_port_message(cmd, datalength, *args):
    # print("W: ",cmd,datalength,args)
    assert len(args) >= datalength
    return generate_request(cmd, args[:datalength])


def generate_request(command, data):
    a = [2, command, len(data), *data]
    # print(generate_checksum(a))
    a.extend(generate_checksum(a).tobytes())
    # print(bytearray(a))
    return bytearray(a)


def validate_buffer(port):
    # print(port.read_buffer)
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
                firststart : firststart + DATABYTEPOSITION + datalength
            ]
            checksumbuffer = port.read_buffer[
                firststart
                + DATABYTEPOSITION
                + datalength : firststart
                + DATABYTEPOSITION
                + datalength
                + 2
            ]
            # print(databuffer)
            # print(checksumbuffer)
            databuffer = np.array([ord(i) for i in databuffer], dtype=np.uint8)
            checksumbuffer = np.array([ord(i) for i in checksumbuffer], dtype=np.uint8)
            # print(databuffer)
            # print(checksumbuffer)
            checksum = np.frombuffer(checksumbuffer, dtype=np.uint16)[0]
            generated_cs = generate_checksum(databuffer)
            # print("cs: ",checksum,generated_cs)
            if checksum == generated_cs:
                port.board.receive_from_port(
                    cmd=databuffer[COMMANDBYTEPOSITION],
                    data=b"".join(databuffer[DATABYTEPOSITION:]),
                )
            port.read_buffer = port.read_buffer[
                firststart + DATABYTEPOSITION + datalength + 2 :
            ]
