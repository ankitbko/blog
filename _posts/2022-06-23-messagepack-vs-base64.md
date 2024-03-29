---
layout: post
title: Optimizing network footprint using MessagePack
comments: true
categories: [websocket, python, performance, latency, complexity, messagepack, base64, json]
description: Measure space and time improvement when using MessagePack instead of JSON to send image over websocket.
image: images/previews/messagepack.png
source_code: https://github.com/ankitbko/messagepack-websocket
author: <a href='https://twitter.com/ankitbko', target='_blank'>Ankit Sinha</a>, <a href='https://github.com/prabdeb', target='_blank'>Prabal Deb</a>
---

The most commonly used technique to send binary data from server to client is to encode it using Base64 and send it as JSON. Base64 encodes each set of *three bytes* into *four bytes*. In addition the output will be padded to always be multiple of four. So the final output would be `4/3` or 33% larger than the original data. Add overhead of JSON to it and output grows even larger. In most of the scenarios this overhead is negligible and worth paying the cost in return of ease of integration with other applications as most of the languages or frameworks have native support of Base64 encoding. 


However in scenarios such as IoT devices, where the bandwidth is limited or there is need of squeezing extra performance, there are other alternatives to Base64 encoding that are more efficient. One such alternative is to use [MessagePack](https://msgpack.org/). It is a binary serialization format which is faster and emits smaller output than using Base64 + JSON.


## Running the sample

In the provided sample we will send an image from server to UI over a websocket connection using both *MessagePack* and *Base64 encoding + JSON* and measure their performance. The browser's network tab will give us the size of each message. To measure the latency of each message we will use the technique described in my [Measuring latency of Websocket Messages]({{ site.baseurl }}/2022/06/websocket-latency) blog post.

Run the sample by following below steps.

1. Install Python 3.6+.
1. Install the dependencies by running `pip install -r requirements.txt`.
1. Run the application using `python main.py` and open `http://localhost:7001` in the browser.


### Using Base64 encoding and JSON
In `frame_handler.py` set `USE_MSGPACK` to `False` and in `index.html` set `useMsgPack` to `False`. This will result in application encoding the image using Base64 and sending JSON over socket connection. Open browser network tab, refresh the page and press *Start* button. In the network tab, open the *websocket* connection to view the size of each message. You should see multiple messages being transmitted over the connection which are needed to calculate the latency. The message that contains the image is about 238KB. The browser's console will log the latency of each message in milliseconds. 

![Json size]({{ site.baseurl }}/assets/images/posts/messagepack/json-n.png)
![Json latency]({{ site.baseurl }}/assets/images/posts/messagepack/json-l.png)


### Using MessagePack
The application is setup to use *MessagePack* to send the image over websocket. Reverse the changes done in `frame_handler.py` and `index.html`. Follow the same approach as above to see the size and latency of each message. In the network tab you should see multiple *Binary message* being received. This is because after using MessagePack we can send the message in binary instead of text. The message that contains image is about 179KB in size.

![MessagePack size]({{ site.baseurl }}/assets/images/posts/messagepack/msg-n.png)
![MessagePack latency]({{ site.baseurl }}/assets/images/posts/messagepack/msg-l.png)


## Conclusion

When using MessagePack, messages are *25% smaller* when compared to its JSON counterpart. Due to this, the latency has been reduced to over *40%* when compared with JSON message. 

The MessagePack encoding is useful where data needs to be delivered quickly or when bandwidth needs to be saved. One such use case is streaming video from camera from server to client in realtime. MessagePack will allow better FPS and smoother video experience.
