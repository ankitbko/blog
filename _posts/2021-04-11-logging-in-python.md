---
layout: post
title: A better way to logging in Python
comments: true
categories: [python, decorators]
description: A generic logging decorator for python
image: images/previews/python-logging.jpg
author: <a href='https://twitter.com/ankitbko', target='_blank'>Ankit Sinha</a>
---

Any production application will likely have some guidelines regarding how and what needs to be logged in your application. More often these guidelines stem from common industry patterns such as "log all exceptions". However implementing these guidelines are left to individual developers and leads to same set of logging statements repeated throughout the codebase. For instance to log all exceptions you would have a logging statement in every `except` block that captures exception and logs it under `ERROR` level. But the logging statement for same scenario may differ between developers due to their individual style of development. Overtime this leads to fragmented and inconsistent logging in the application. Moreover developers can make mistake and miss having logging statement at necessary places.

One approach to alleviate this problem is by utilizing Python's decorator feature. This article will give a brief overview of decorators and demonstrate how to create a decorator to abstract these common logging statements. You can read more about decorators and variety of ways they can be utilized in this excellent [Primer on Python Decorators](https://realpython.com/primer-on-python-decorators/).


## What are decorators

A decorator is a function that takes another function and extends the it's behavior without explicitly modifying it. These are also known as [higher-order functions](https://en.wikipedia.org/wiki/Higher-order_function).

Python's functions are [first-class citizens](https://en.wikipedia.org/wiki/First-class_citizen). This means functions can passed as argument or can be subject of assignment. So if you have a function called `sums(a, b=10)`, you can use it as any other objects and drill down into its properties.

```python
def sum(a, b=10):
    return a+b
```

```python
>>> sum
<function sum at 0x7f35e9dde310>
>>> sum.__code__.co_varnames  # Names of local variables
('a', 'b')
```

Since functions behave like any other object, you could assign `sum` to another function. Then calling `sum` will call this another function instead of the one that we defined before. The decorators utilizes this behavior by assigning `sum` a new function which takes `sum` as parameter and wraps some additional logic around it thereby *extending* it without modifying the function itself.


```python
def my_decorator(func):
    def wrapper(*args, **kwargs):
        # do something before `sum`
        result = func(*args, **kwargs)
        # do something after `sum`
        return result
    return wrapper

sum = my_decorator(sum)
```

```python
>>> sum
<function my_decorator.<locals>.wrapper at 0x7f9c0359b0d0>
```

This pattern is so common that Python has a syntactic sugar for decorating a function. So instead of `sum = my_decorator(sum)` we can use `@` symbol on top of `sum` method like this -

```py
@my_decorator # Equivalent to `sum = my_decorator(sum)` after the method
def sum(a, b=10):
    return a+b
```


## Logging Decorator

We are going to create a decorator that handles two common logging scenarios - logging exceptions as *ERROR* and logging method arguments as *DEBUG* logs.

Lets start by capturing the exceptions and logging it using python `logging` library.

```python
import functools
import logging

logging.basicConfig(level = logging.DEBUG)
logger = logging.getLogger()

def log(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            logger.exception(f"Exception raised in {func.__name__}. exception: {str(e)}")
            raise e
    return wrapper

@log
def foo():
    raise Exception("Something went wrong")
```

```sh
ERROR:root:Exception raised in foo. exception: Something went wrong
Traceback (most recent call last):
  File "<REDACTED>/foo.py", line 15, in wrapper
    result = func(*args, **kwargs)
  File "<REDACTED>/foo.py", line 28, in foo
    raise Exception("Something went wrong")
Exception: Something went wrong
```

In addition to setting up the `logger`, we have also used [@functools.wraps](https://docs.python.org/3/library/functools.html#functools.wraps) decorator. The `wraps` decorator updates the `wrapper` function to look like `func`. Our `@log` decorator can now be used on any function to catch every exception from *wrapped* function and log it in consistent manner.


Since `wrapper` function accepts all arguments (`*args and **kwargs`), the `@log` decorator can be extended to capture all the parameters passed to the decorated function. We can do this by just iterating over *args* and *kwargs* and joining them to form string message to log.

```python
def log(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        logger.debug(f"function {func.__name__} called with args {signature}")
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            logger.exception(f"Exception raised in {func.__name__}. exception: {str(e)}")
            raise e
    return wrapper
```

```python
>>> sum(10, b=20)
DEBUG:root:function sum called with args 10, b=20
30
```

We log the parameters in *DEBUG* level as we don't want our logs cluttered with all functions arguments. Debug logging can be toggled on our systems as and when necessary. **Keep in mind that this will write all argument values into log including any PII data or secrets**.

This basic logging decorator looks good and already does what we originally set out to achieve. As long as a method is decorated with `@log` decorator we will capture any exception raised within it and all arguments passed to it.


However in real projects, the `logger` can itself be abstracted away into its own class that initializes a logger based on certain configuration (such as push log to a cloud sink). In this case its useless to log into console by creating our own logger in the `@log` decorator. We need a way to pass an existing `logger` into our decorator at runtime. To do this we can extend the `@log` decorator to accept `logger` as an argument.


To mimic this scenario we will start with having a class that returns us creates logger for us. For now we will create the basic logger but you can imagine the class configuring the behavior of the logger as required.

```python
class MyLogger:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

    def get_logger(self, name=None):
        return logging.getLogger(name)
```

Since at the time of writing the decorator we do not know whether the underlying function will be passing us `MyLogger` or `logging.logger` or no logger at all, our generic decorator will have be able to handle all of them.

```python
from typing import Union

def get_default_logger():
    return MyLogger().get_logger()

def log(_func=None, *, my_logger: Union[MyLogger, logging.Logger] = None):
    def decorator_log(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if my_logger is None:
                logger = get_default_logger()
            else:
                if isinstance(my_logger, MyLogger):
                    logger = my_logger.get_logger(func.__name__)
                else:
                    logger = my_logger
            args_repr = [repr(a) for a in args]
            kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
            signature = ", ".join(args_repr + kwargs_repr)
            logger.debug(f"function {func.__name__} called with args {signature}")
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                logger.exception(f"Exception raised in {func.__name__}. exception: {str(e)}")
                raise e
        return wrapper

    if _func is None:
        return decorator_log
    else:
        return decorator_log(_func)
```

The above code looks quite scary but let me summarize it. The `@log` decorator now handles three different scenarios -

- No logger is passed: This is same scenario what we have been doing up until before this. The decorator is simply used as `@log` statement on top of the function. In this case the decorator gets a logger by calling `get_default_logger` method and uses it for rest of the method.

- `MyLogger` is passed: Our `@log` decorator can now accept instance of `MyLogger` as an argument. It can then call `MyLogger.get_logger` method to create a nested logger and use it rest of the way.

```python
@log(my_logger=MyLogger())
def sum(a, b=10):
    return a + b
```

- `logging.logger` is passed: In this third scenario we can pass the logger itself instead of passing `MyLogger` class.

```python
lg = MyLogger().get_logger()

@log(my_logger=lg)
def sum(a, b=10):
    return a + b
```


We are still not done. Even in current form our log decorator is restricted. One limitation is that we *must* have `logger` or `MyLogger` available *before* the method we want to decorate. In other words the reference to logger *must* exist before the method itself exists. This may work in cases where the target function is part of a class and the class `__init__` method can instantiate the logger, but it won't work with functions outside the context of class. In many real world applications we wont have each module or function creating their own logger. Instead we may want to pass the logger to the function itself. The `logger` or `MyLogger` will be dependency injected into downstream methods. In other words a function may have logger passed to it in its parameter.

But if the function is part of a class then the `logger` will be injected into class itself and not into every method of the class. In this case we would want to use the logger available to our class instead.

So our objective is to capture the `logger` passed as the argument *to the decorated* function **or** passed to the *class constructor of our decorated function*, and use it to log *from the decorator* itself. By doing this our decorator can be completely decoupled from the logger itself and will utilize whatever logger is available to the underlying method at runtime.


 To do this we will iterate over the `args` and `kwargs` argument and check if we get `logger` in any of them. To check if the function is part of the class, we can check if first argument of `args` has attribute `__dict__`. If the first argument has attribute `__dict__` we will iterate over the `__dict__.values()` and check if one of these values is our logger or not. Finally if nothing works we will default to `get_default_logger` method.

```py
def log(_func=None, *, my_logger: Union[MyLogger, logging.Logger] = None):
    def decorator_log(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_default_logger()
            try:
                if my_logger is None:
                    first_args = next(iter(args), None)  # capture first arg to check for `self`
                    logger_params = [  # does kwargs have any logger
                        x
                        for x in kwargs.values()
                        if isinstance(x, logging.Logger) or isinstance(x, MyLogger)
                    ] + [  # # does args have any logger
                        x
                        for x in args
                        if isinstance(x, logging.Logger) or isinstance(x, MyLogger)
                    ]
                    if hasattr(first_args, "__dict__"):  # is first argument `self`
                        logger_params = logger_params + [
                            x
                            for x in first_args.__dict__.values()  # does class (dict) members have any logger
                            if isinstance(x, logging.Logger)
                            or isinstance(x, MyLogger)
                        ]
                    h_logger = next(iter(logger_params), MyLogger())  # get the next/first/default logger
                else:
                    h_logger = my_logger  # logger is passed explicitly to the decorator

                if isinstance(h_logger, MyLogger):
                    logger = h_logger.get_logger(func.__name__)
                else:
                    logger = h_logger

                args_repr = [repr(a) for a in args]
                kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                signature = ", ".join(args_repr + kwargs_repr)
                logger.debug(f"function {func.__name__} called with args {signature}")
            except Exception:
                pass

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                logger.exception(f"Exception raised in {func.__name__}. exception: {str(e)}")
                raise e
        return wrapper

    if _func is None:
        return decorator_log
    else:
        return decorator_log(_func)
```

The above decorator is generic enough to work for 2 more scenarios in addition to 3 scenarios we discussed before -

- Either `logger` or `MyLogger` is passed to the decorated method

```py
@log
def foo(a, b, logger):
    pass

@log
def bar(a, b=10, logger=None): # Named parameter
    pass

foo(10, 20, MyLogger())  # OR foo(10, 20, MyLogger().get_logger())
bar(10, b=20, logger=MyLogger())  # OR bar(10, b=20, logger=MyLogger().get_logger())
```

- Either `logger` or `MyLogger` is passed to class `__init__` method hosting the decorated function

```py
class Foo:
    def __init__(self, logger):
        self.lg = logger

    @log
    def sum(self, a, b=10):
        return a + b

Foo(MyLogger()).sum(10, b=20)  # OR Foo(MyLogger().get_logger()).sum(10, b=20)
```

One additional thing we have done is to wrap all the code *before* calling the decorated function `func` in a `try - except` block. We don't want the execution to fail due to problems in logging even before the target function is called. In no case our logging logic should cause failure in the system.


Reach out to me in the comments below for any questions that you may have.