---
layout: post
title: Measuring latency of Websocket Messages
comments: true
categories: [websocket, python, performance, latency]
description: Measuring latency of Websocket Messages
image: images/previews/websocket_latency.png
source_code: https://github.com/ankitbko/websocket-latency
author: <a href='https://twitter.com/ankitbko', target='_blank'>Ankit Sinha</a>, <a href='https://github.com/prabdeb', target='_blank'>Prabal Deb</a>
---

Have you noticed that the browser does not display time it took for a websocket message to be delivered like it shows for HTTP requests? That is because, in contrast to HTTP protocol which follows *request-response* pattern, websocket messages do not have transaction semantics once the initial handshake is done to establish the connection. Once the websocket connection is established, messages are *pushed* from server to client (or vice versa). Therefore if browser receives a websocket message, it does not know when the message was sent to calculate the latency.


Therefore, an obvious approach would be to have sender attach a timestamp to the message while sending so that it can be used to calculate latency. However, the system clocks for both the system could be different which may be skewed or misleading. Hence, sender's timestamp may not provide sufficient information to calculate latency of message.


To accurately calculate latency we would need round trip of message between client and server. If the original message is small in size and socket is not throttled, the client can echo the same message back to server. The server can then find the roundtrip latency by calculating the time elapsed between sending of original message and receiving the echo'd message. Dividing this by 2 gives one way latency. However if the message size is big, this approach is not recommended as it puts additional stress on socket connection and on the server. In this case we need one additional message to be sent from server to client.

![ws sequence diagram]({{ site.baseurl }}/assets/images/posts/websocket-latency/ws_sequence.png)

1. Server sends the Message (M) to client whose latency needs to be measured. Server adds `server_ts` to the message.
1. Client sends an acknowledgement message (ACK) to server by echoing `server_ts` and attaching its own timestamp in `client_ts`.
1. Server echos the ACK message by attaching another timestamp `server_ack_ts`.
1. Client captures the timestamp `client_ack_ts` onces it receives the ACK message. 


At this stage the client has 4 pieces of information - 
1. `server_ts`: Timestamp when original message M was sent from server.
1. `client_ts`: Timestamp when original message M was received by the client.
1. `server_ack_ts`: Timestamp when ACK message was received by the server.
1. `client_ack_ts`: Timestamp when ACK response was received by the client.

By using these timestamp we can calculate the latency of original message M as follows

```
Latency of M = (server_ack_ts - server_ts) - ((client_ack_ts - client_ts) * 0.5)
```

This works because we are only subtracting server timestamp with server timestamp and client timestamp with client timestamp. 

![ws_workflow]({{ site.baseurl }}/assets/images/posts/websocket-latency/websocket_latency.gif)

The code provided implements this in a python application that sends an image multiple times from server to client using websocket. This is analogous to streaming a video from server to client. To run the application

1. Install dependencies using `pip install -r requirements.txt`.
1. Run the application by executing `python main.py` 
1. Navigate to `http://localhost:7001` and open the browser's console. Click on *start* button and the latency for each socket message will be printed in the console.


![Ws Latency]({{ site.baseurl }}/assets/images/posts/websocket-latency/browser_latency.png)


The python implementation to handle *ACK* message and attach appropriate timestamp is in `latency.py` as a decorator method.

```py
def measure_latency(func):
    def wrapper_measure_latency(*args, **kwargs):
        message = json.loads(args[1])
        _self = args[0]
        if message["type"] == "ack":
            print(f"Received message: {message}")
            message["server_ack_ts"] = str(datetime.now().timestamp())
            _self.write_message(json.dumps(message))
        func(*args, **kwargs)
        return

    return wrapper_measure_latency
```

In `index.html` the `calculate_socket_latency` calculates the latency after all the timestamps are received by the client.

```js
function calculate_socket_latency(data) {
    client_ack_ts = performance.now()
    ack_round_trip_time = client_ack_ts - data.client_ts
    ack_one_way = ack_round_trip_time / 2
    vid_round_trip_time = (data.server_ack_ts - data.server_ts) * 1000
    vid_one_way = vid_round_trip_time - ack_one_way
    console.log(vid_one_way)
}
```

## Conclusion
As we can see, calculating websocket message latency is not straightforward. It requires additional messages that needs to be sent which adds to the network load. In case the primary websocket connection is already throttled, a different dedicated websocket connection for measuring latency can be used to send ACK messages with condition that a client connect to same instance of server for both the socket connections to avoid clock skew between servers.