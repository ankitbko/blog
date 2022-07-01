---
layout: post
title: Patterns for Vision on the Edge - Part 2 - Handling Multiple Consumers
comments: true
categories: [AI, ML, vision on edge, python, multiprocessing, threading, GIL, back-pressure, reactivex, rxpy]
description: Challenges in implementing Vision based solution using Python on Edge.
image: images/previews/vision-on-edge-2.png
source_code: https://github.com/ankitbko/vision-on-edge
author: <a href='https://twitter.com/ankitbko', target='_blank'>Ankit Sinha</a>, <a href='https://github.com/prabdeb', target='_blank'>Prabal Deb</a>
---


This post is the second part in a 2 part blog series on Patterns for implementing Vision on Edge. In the [previous post]({{ site.baseurl }}/2022/06/vision-on-edge-part-1/), we discussed two of the three common challenges faced when creating a Computer Vision based solution using Python on Edge. 

In this post we will cover the third challenge i.e. reading the video frames from the source (camera) and distributing them to multiple consumers based on the frame rate supported by the individual consumers.

One of the most common ways to implement such a pattern is using the [ReactiveX](https://reactivex.io/).

ReactiveX is an API for asynchronous programming with observable streams which enables to multiplex stream of data to multiple consumers. Under the hood, ReactX is an implementation of [Observer pattern](https://en.wikipedia.org/wiki/Observer_pattern).

In our sample application, we read frames from camera in FrameProvider process and then we send the frame to two consumers - UI and Queue.

Behind the scenes, ReactiveX is enabling us to read stream of video frames (from source camera), split the stream into two different streams (one per consumer), independently apply sampling on each stream to adhere to different FPS requirement for the consumer, and transmit the frames to different consumers asynchronously.

Now let's see how is this all implemented.

## ReactiveX for Python (RxPY)

*ReactiveX for Python (RxPY) is a library for composing asynchronous and event-based programs using observable collections and pipable query operators in Python.*

As the concept of ReactiveX is vast, we will focus on 2 key aspects of this framework referenced in this sample application.

### Observable

An *Observable* emits items sequentially. Multiple *Observers* can *subscribe* to an *Observable* and react to the items as emitted by *Observable*. This enables better concurrency and non-blocking operations.

If we relate this concept to our problem, we can have an *Observer* that reads a frame from camera and emits it. And we can have two different *Observers* subscribed to it, one for emitting the frame to Queue and another for sending the frame in UI. In practice, we will have many more *Observers* in the pipeline to transform and modify the frames before we emit them to downstream consumers.

### Operator

There are multiple operators that are used in `ReactiveX` to compose the pipeline, where each operator is a function that takes an Observable, transforms the item and yields a new Observable. Let's look at the following operators that we have used in this sample:

* `map`: transform the items emitted by an Observable to a new Observable by applying a function to each item.
* `filter`: filters the items emitted by an Observable using a predicate.
* `sample`: emit the most recent items within periodic time intervals.
* `interval`: emits a sequence of items spaced by a specified interval.
* `share`: shares the items emitted by an Observable, by converting connectable Observable (that does not begin emitting items) to a ordinary Observable. By applying this operator we can prompt an Observable to begin emitting items
* `do_action`: performs an action for each item emitted by an Observable.

We can use these operators to perform several tasks like reading frame from camera, resizing the frame, sending to UI, etc.

## Implementation

Lets take a look at how we have implemented the above concepts in the application. All the code is present in `frame_provider.py`.

![ReactiveX Implementation]({{ site.baseurl }}/assets/images/posts/vision-on-edge-2/ReactiveX.png)

### Frame Stream

First task is to read the frames from the camera at a defined rate supported by the camera. To do this we make use of `interval` operator in *RxPY* to emit an event at defined interval. We then need to discard the invalid frames and encapsulate it in our own data structure.

```python
frame_stream = interval(frame_rate).pipe(
    op.map(lambda _: self.vid.read()),  # read frame
    op.do_action(lambda result: self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0) if result[0] is False else None), # restart video on completion
    op.filter(
        lambda result: result[0] is True and result[1] is not None
    ),  # filter None frames
    op.map(lambda result: result[1]),  # get frame
    op.map(
        lambda frame: Frame(
            frame=frame,
            correlation_id=str(uuid.uuid4()),
        )
    ),  # create frame object
    op.share(),  # share frame stream
)
```

Let's take a look at step by step operations

1. `interval(frame_rate)` - emits a sequence an event at a FPS rate for camera.
1. `map(lambda _: self.vid.read())` - discards the original event and emits the frame after reading it from camera using `vid.read()`.
1. `do_action(...)` - required only if reading from video file instead of camera. Used to restart the video when EOF is reached.
1. `filter(lambda result: result[0] is True and result[1] is not None)` - filters out the invalid frames.
1. `map(...)` - create a Frame object, by adding additional information (`correlation_id`) to the frame.
1. `share` - returns an observable sequence that shares a single subscription to the underlying sequence.


### UI Stream

Next we want to subscribe to *Frame Stream*, sample the frames to match FPS required by UI, resize the frames and transmit it using websocket. The `sample` operator changes the frequency of the items being emitted for the downstream operators allowing us to change the FPS rate.

```python
frame_stream.pipe(
    op.sample(socket_fps),
    op.map(
        lambda frame: Frame(
            cv2.resize(frame.frame, frame_size),
            frame.correlation_id,
        )
    ),
    op.map(
        lambda frame: Frame(
            frame.frame,
            frame.correlation_id,
        )
    ),
    op.map(lambda frame: self._write_to_socket(frame=frame)),
)
```

Let's take a look at step by step operations, that is being performed primarily on the Observer.

1. `sample(socket_fps)` - that samples the frame stream to send the frame to the UI at a FPS rate required by UI.
1. `map(...)` - resize the frame to the required size needed for UI.
1. `map(lambda frame: self._write_to_socket(frame=frame))` - send each frame to the UI.

### Queue Stream

Simultaneously we need to get frames from *Frame Stream* and send the frame to the Queue for performing frame processing. The `share` operator in *Frame Stream* allows us to share the stream between two different observers where each observer gets copy of same item as emitted from *Frame Stream*. We perform the same actions as we did with *UI Stream* but with different FPS rate and resize parameters.

```python
frame_stream.pipe(
    op.sample(queue_fps),
    op.map(
        lambda frame: Frame(
            cv2.resize(frame.frame, frame_size),
            frame.correlation_id,
        )
    ),
    op.map(lambda frame: self._write_to_queue(frame=frame)),
)
```

Let's take a look at step by step operations, that is being performed primarily on the Observer.

1. `sample(queue_fps)` - samples the frame stream to send the frame to the Queue at a FPS rate required by frame processing.
1. `map(...)` - resize the frame to the required size needed for frame processing.
1. `map(lambda frame: self._write_to_queue(frame=frame))` - send each frame to the Queue.

### Subscribe to the stream

Now we have two observables - one from *UI Stream* and another from *Queue Stream*. We need to *subscribe* to the observables to start the pipelines.

```python
socket_result_stream.subscribe(
    on_next=lambda _: None,
    on_error=lambda ex: self.logger.exception(ex),
    on_completed=lambda: self.logger.info("Completed frame stream"),
)
queue_result_stream.subscribe(
    on_next=lambda _: None,
    on_error=lambda ex: self.logger.exception(ex),
    on_completed=lambda: self.logger.info("Completed frame stream"),
)
```

Once subscribed, the operators will start receiving the frames from the Observable, which is an asynchronous and non-blocking operation.

## Unit Test

Conventional way of testing is not sufficient to test the *ReactiveX* code. We need to use [Marble diagrams]((https://rxmarbles.com/)) to represent the behavior of an Observable and then we can can use it to assert the Observable as expected.

Also for mocking we can use `Hot` and `Cold` Observables. *A “hot” Observable may begin emitting items as soon as it is created, and so any observer who later subscribes to that Observable may start observing the sequence somewhere in the middle. A “cold” Observable, on the other hand, waits until an observer subscribes to it before it begins to emit items, and so such an observer is guaranteed to see the whole sequence from the beginning.*

Let's have a look at the following unit test case for function `def _emit_frame_to_queue` in `frame_provider.py`:

```python
import unittest
from unittest.mock import patch
from rx import operators as ops
from rx.testing.marbles import marbles_testing
from frame_provider import FrameProvider, Frame


def print_marbles(stream, ts):
    diagram = stream.pipe(ops.to_marbles(timespan=ts)).run()
    print('got        "{}"'.format(diagram))


class TestFrameProvider(unittest.TestCase):
    @patch("frame_provider.cv2.resize", side_effect=lambda x, _: x)
    @patch(
        "frame_provider.FrameProvider._write_to_queue", side_effect=lambda frame: True
    )
    def test__emit_frame_to_queue_samples_at_given_rate(self, _, *args):
        frame_rate = 1.0 / 2.0
        frame_provider = FrameProvider(None)
        ts = 1.0 / 10.0
        mock_frame = Frame(None, None)
        with marbles_testing(timespan=ts) as (start, cold, hot, exp):
            e1 = cold(
                "-a-b-c---d-e-----|",
                {
                    "a": mock_frame,
                    "b": mock_frame,
                    "c": mock_frame,
                    "d": mock_frame,
                    "e": mock_frame,
                },
            )
            ex = exp(
                " -----c----d----e----|",
                {
                    "c": True,
                    "d": True,
                    "e": True,
                },
            )
            expected = ex

            result_stream = frame_provider._emit_frame_to_queue(
                e1, frame_rate, [900, 900]
            )
            print_marbles(result_stream, ts)

            results = start(result_stream)
            assert results == expected

```

## Conclusion

In this blog series, we discussed common challenges when implementing a vision based solution. In part 1 of the blog post, we discussed how to handle backpressure when ML model is unable to keep up to the FPS rate of camera. We also discussed how to run inference on ML model while concurrently performing other tasks. We learned the bottlenecks of *threading* and *GIL* in Python and how to leverage *multiprocessing* instead. In this article we saw how ReactiveX can be leveraged to multiplex the camera stream to multiple consumers in a asynchronous and non blocking manner. 


## References

1. [ReactiveX](https://reactivex.io/)
1. [ReactiveX for Python (RxPY)](https://rxpy.readthedocs.io/en/latest/)
1. [github.com/ReactiveX/RxPY](https://github.com/ReactiveX/RxPY)
1. [Interactive diagrams of Rx Observables](https://rxmarbles.com/)
