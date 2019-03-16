##Server
A socket server which allows to communicate between websocket clients 
and send commands between them.
The server can be incoken by  
`socketserver = SockerServer()`  
by default the server uses 127.0.0.1 (normaly equally to 'localhost') as the host and the port 8888.  
This can be changed to any other host/port by using respective arguments:  
`socketserver = SockerServer(port='localhost',port=8888)`  

If the Server cannot bind to the host:port pair an OSError is thrown.
This can be used to connect to the first free port
```
SOCKETPORT=8888
notconnected = True
socketserver = None
while notconnected:
    try:
        socketserver = SockerServer(port=SOCKETPORT)
        notconnected = False
    except:
        SOCKETPORT += 1
```
after the port is opened it can be run constantly by calling:  
`socketserver.run_forever()`

By default the server ask any connected client for a identification and sends a time stamp which can be used for time synchronization (see below)

##Client
The package comes also with a client.
To invoke a client use:  
`wsc = WebSocketClient("name",host="ws://127.0.0.1:8888")`   
The name should be unique and the host has to be changed match the socket server.

If a host is provided (not None) the client connects immediately to the server. If no host is provides or the auto_connect is set to False
the connection has to be established by calling:  
`wsc.connect_to_socket("hostadress")`  

The client can call functions when connecting, disconnecting or an error occures:
to add a function call:  
`wsc.add_on_open("name", func[,overwrite=False])#run func on connecting`  
the name is used as a reference to remove the function if nescessary and overwrite=False (the default) protects already set functions from overwriting by the same name.
No parametes are passed to the function. Same goes for the disconnecting (add_on_close) and and error (add_on_error) functions.
By default the Client reconnects on error or on close. To turn this off set the **reconnect** attribute to false

In the same manner a on message can be assigned to the client. In this case the function passed resives the massage as parameter.

Initially an **intrinsic message validator** is added as on-message function which validates the massage according to the default message template:
```
{
        "type": "messagetype",
        "data": {},
        "from": sendername,
        "target": messagetarget,
    }
```

By default if the messagetype is "cmd" the message is threaten as a commandmessage and validated.
A commandmessage has to have the data-structure:
```
{
    "cmd": "commandname",
    "args": [],
    "kwargs": {}
}
``` 
Initially two commands are registered:  
- "indentify": answers to the identtify request of the server and registers with the SocketClient.name    
- "set_time": sets SocketClient.time to the given data which can be used for time synchronization.

additional commands can be registered via:  
`wsc.add_cmd_function('name',func[,overwrite=False])`  

Example:  
```
import time
import logging
import random
import threading
from websocket_communication_server.messagetemplates import commandmessage
from websocket_communication_server.socketclient import WebSocketClient
from websocket_communication_server.socketserver import SockerServer, SOCKETPORT


class Testclass:
    def __init__(self, host, name):
        self.runime = 0
        self.name = name
        self.wsc = WebSocketClient(name, host=host)
        self.wsc.add_cmd_function("pass_ball", self.pass_ball) # registers own pass_ball method to be called when reciving the pass_ball command
        self.pingpong = "ping" if "1" in name else "pong"
        self.opponent = "Player2" if "1" in name else "Player1"

    def pass_ball(self, catch=None): #methods called by the message validator should have default attributes to be valid against "TypeError: pass_ball() missing 1 required positional argument: 'catch'"
        if catch is None:
            print("End of the game because the ball went missing somewhere")
            return
        print(self.pingpong)  # prints ping or pong
        if not catch:
            print("Damn!")  # dont like losing the ball
        time.sleep(1)  # delay in game because it would be way to fast without, maybe the flytime of the ball :)
        self.wsc.write_to_socket(
            commandmessage(
                cmd="pass_ball", # the command to call at the reciver
                sender=self.name, # sender of the command
                target=self.opponent, # reciver
                catch=random.random() < 0.8, # 80% ball catch
            )
        )


if __name__ == "__main__":
    # connects to the firsts free port
    notconnected = True
    socketserver = None
    while notconnected:
        try:
            socketserver = SockerServer(port=SOCKETPORT)  # binds to 127.0.0.1:8888++
            notconnected = False
        except:
            SOCKETPORT += 1

    threading.Thread(
        target=socketserver.run_forever
    ).start()  # runs server forever in background
    test1 = Testclass(host=socketserver.ws_adress, name="Player1")  # create player 1
    test2 = Testclass(host=socketserver.ws_adress, name="Player2")  # create player 2
    time.sleep(1)  # gives the players enought timw to identify
    test1.pass_ball(True)  # throw the first ball
    while 1:
        time.sleep(1)  # play forever

```
Output:  
ping
pong
ping
pong
ping
pong
Damn!
ping
Damn!
pong
ping
pong
ping
pong
ping
pong
ping

