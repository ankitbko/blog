---
layout: post
title: Skype Call your bot - Microsoft Bot Framework with Bing Speech
comments: true
categories: [Microsoft Bot Framework, LUIS, Bots, Chat Bots, Conversational Apps, Skype, Bing Speech]
description: Skype Call your bot by integrating Microsoft Bot Framework with Bing Speech
---

So over this past weekend, I was dead bored when I got this idea of calling a bot from Skype. Skype bot calling feature does exist(preview) but the samples which are available are only for simple IVR bot. So I thought why not integrate it with Bot Builder SDK, so that same bot can text and answer call at same time. So the basic idea is that the bot should follow the same *flow* irrespective whether the user texts or calls. Great idea to past time, after some initial trouble, I did manage to get it done(not neatly though). So why not write a blog about it.
Source code is available over my [github repo](https://github.com/ankitbko/RentACarBot).

> I developed this sample over weekend just to find out whether it could be done or not. It is not a very cleanly written sample and there is a design flaw due to which the bot cannot be scaled out. I will address this design issue and also explain how we can make it scalable. Nonetheless, I decided to write down this blog because it provides a nice insight into Skype Calling Bot and also how to intercept the responses from Bot by implementing `IBotToUser` interface.

For this *fun* project, we will use the Bot Builder Calling SDK which is now part of Bot Framework, to make a call to our bot. Once we get the audio stream of the caller, we will use [Bing Speech API](https://www.microsoft.com/cognitive-services/en-us/speech-api) for Speech-to-Text conversion. After we receive the text, we will just pass it to our bot and our bot will behave in the same way as it does for text input. The trick here is to not let our bot reply back to user through bot connector, but to intercept the reply messages and pass it onto Skype Calling APIs which manages Text-to-Speech conversion and would *speak* back to the user. The plan is to utilize feature rich Bot Builder SDK to build our bot and plugin the voice calling functionality on top of it, without having to modify any of the bot logic.


Fair Warning: This is going to be a long post. Before getting into details, I will give a brief overview of Bot Builder Calling SDK and Bing Speech SDK.

### Bot Builder Calling SDK

Bot Builder Calling SDK is just a nice client package to call [Skype Calling APIs](https://docs.botframework.com/en-us/skype/calling). I recommend you read through the API documentation to understand how calling works through Skype. I will just explain it briefly here.


When a call arrive to Skype Bot Platform, it would notify our bot by calling our bot's HTTPS endpoint. Once we receive this notification, we(our bot) can reply back by providing a list of actions called **workflow** to execute. So for the initial call notification, we can either reply back by `Answer` or `Reject` action. The Skype Bot Platform will then execute the workflow and return us the result of last action executed. The SDK will raise an appropriate `Event` which we can subscribe to and handle the action outcome in our code. For example, on initial call notification, sdk will raise `OnIncomingCallReceived` event. On each event, we have opportunity to send another workflow to the user. In fact it is mandatory to return list of actions otherwise the sdk will throw an error and the call would get disconnected.
The below image, which I shamelessly copied from official documentation, explains how Skype calling works.

![Skype Call Flow]({{ site.baseurl }}/assets/images/posts/skypecall/flow.png)

### Bing Speech API

We will use [Bing Speech API](https://www.microsoft.com/cognitive-services/en-us/speech-api) for Speech-to-Text(STT) conversion. Microsoft team has released a thin C# client library for STT conversion using Bing Speech API. The samples are available on [github](https://github.com/Microsoft/Cognitive-Speech-STT-Windows) and the library is available over nuget. For some reason they have different libraries for x64 and x86. Make sure you use the correct one depending upon your system.


The first thing to do is get a Speech API subscription key (free) by signing up for [Cognitive Services](https://www.microsoft.com/cognitive-services/en-US/subscriptions). The STT sdk also works on event based model. In simple terms, the audio stream is sent to Speech API, which then returns the recognized text which is available in the argument `OnResponseReceived` event which is raised. The Speech API also returns partially converted text, but in our case we ignore them.

### Putting it all together

But before that, we need to get develop a bot which works text inputs. I have gone ahead and created a very simple bot using FormFlow which allows user to rent a car. LUIS is used for text classification which returns the intent as `Rent` and entities such as `PickLocation` and `Pickup Date and Time`. Following which I just pass the entities to the FormFlow which takes care of asking appropriate questions and filling out rest of the form. Simple.

![Skype Call Flow]({{ site.baseurl }}/assets/images/posts/skypecall/rentcar.png)

To integrate Skype call, there are few complication -

* There are 2 layers of event based models which needs to be wired together - Skype Calling SDK and Bing Speech SDK.
* The STT output needs to be supplied to the Bot Builder in *correct* format. Our bot expects an `IMessageActivity` instance with properly filled in IDs such as Conversation ID, Channel ID etc so that it can fetch correct state from State Service.
* The response from the bot needs to be intercepted and somehow returned back to event based model of Skype SDK.

We will address each of them one by one.

To start with we create a project from [Calling Bot Template](https://aka.ms/bf-builder-calling). The template creates a very basic IVR bot with a `CallingController` which receives the request from Skype Bot Platform and a `SimpleCallingBot` class which derives from `ICallingBot` which handles all the events which are raised by the Calling Bot SDK. The template also have a `MessageController` with default bot implementation.

Next create a new class `RentCarCallingBot` and derive it with `ICallingBot`. I have used `SimpleCallingBot` as a reference therefore you will see basic structure and few methods are same. In the constructor we subscribe to the events which will be raised when a workflow is completed.

```csharp
public RentCarCallingBot(ICallingBotService callingBotService)
{
    if (callingBotService == null)
        throw new ArgumentNullException(nameof(callingBotService));

    this.CallingBotService = callingBotService;

    CallingBotService.OnIncomingCallReceived += OnIncomingCallReceived;
    CallingBotService.OnPlayPromptCompleted += OnPlayPromptCompleted;
    CallingBotService.OnRecordCompleted += OnRecordCompleted;
    CallingBotService.OnHangupCompleted += OnHangupCompleted;
}
```

We subscribe to only 4 events -

* `OnIncomingCallReceived`: Is fired when a call arrives at Skype Bot Platform. This is the same event which I explained earlier. Here we can either accept or reject the call.
* `OnPlayPromptCompleted`: Is fired when `PlayPrompt` action is completed. `PlayPrompt` action performs Text-to-Speech(TTS) conversion and plays back the supplied text to the caller. Once the playback is complete and if it is the last action in the workflow, then this event is raised.
* `OnRecordCompleted`: Similar to above, this event is raised when `Record` action completes. `Record` action allows us to record the caller's voice and gives us an audio stream. This is the primary way to receive the audio of caller.
* `OnHangupCompleted`: As name suggests, is raised when we hangup.


#### OnIncomingCallReceived

```csharp
private Task OnIncomingCallReceived(IncomingCallEvent incomingCallEvent)
{
    var id = Guid.NewGuid().ToString();
    incomingCallEvent.ResultingWorkflow.Actions = new List<ActionBase>
        {
            new Answer { OperationId = id },
            GetRecordForText("Welcome! How can I help you?")
        };
    return Task.FromResult(true);
}
```

Upon receiving a call, we get an `IncomingCallEvent` object as argument. To this, we can add next steps of actions to be executed in the workflow. We add 2 events to the workflow - *Answer* and *Record*. We first answer the call and then start a *Record* action to get the caller's input. Skype will start recording after speaking welcome message. The recorded stream will be available to us in `OnRecordCompleted` event.
A thing to note is that we must specify an *OperationId* to each action. It is used to correlate the outcome of the event.

#### OnRecordCompleted

```csharp
private async Task OnRecordCompleted(RecordOutcomeEvent recordOutcomeEvent)
{
    if (recordOutcomeEvent.RecordOutcome.Outcome == Outcome.Success)
    {
        var record = await recordOutcomeEvent.RecordedContent;
        BingSpeech bs =
            new BingSpeech(recordOutcomeEvent.ConversationResult, t => response.Add(t), s => sttFailed = s);
        bs.CreateDataRecoClient();
        bs.SendAudioHelper(record);
        recordOutcomeEvent.ResultingWorkflow.Actions =
            new List<ActionBase>
            {
                GetSilencePrompt()
            };
    }
    else
    {
        if (silenceTimes > 1)
        {
            recordOutcomeEvent.ResultingWorkflow.Actions =
                new List<ActionBase>
                {
                    GetPromptForText("Thank you for calling"),
                    new Hangup()
                    {
                        OperationId = Guid.NewGuid().ToString()
                    }
                };
            recordOutcomeEvent.ResultingWorkflow.Links = null;
            silenceTimes = 0;
        }
        else
        {
            silenceTimes++;
            recordOutcomeEvent.ResultingWorkflow.Actions =
                new List<ActionBase>
                {
                    GetRecordForText("I didn't catch that, would you kinly repeat?")
                };
        }
    }
}
```

There are three sections in this method. The first if block is executed when we have successfully recorded the voice of the caller. We get the recorded content and pass it to `BingSpeech` class. It accepts 3 arguments in constructor, the first being the `ConversationResult`, the second and third being 2 delegates. The first delegate is used add a string to `response` property which is a `List<string>`. The `response` list maintains the list of messages which bot will send to the caller. The second delegate sets a flag if the STT conversion failed. In short this class calls the Bing Speech API and upon receiving the STT output, it goes ahead and passes it to our bot.
Then we go ahead and add a `PlayPrompt` action which just keeps silence for specified period of time. This is required as we do not have result from bot immediately as we will see later.


If we do not receive a successful recoding, we give the caller a chance to speak again once more. If the recording fails again, we disconnect the call gracefully. The `silenceTimes` counter is used for this purpose.

#### OnPlayPromptCompleted

```csharp
private Task OnPlayPromptCompleted(PlayPromptOutcomeEvent playPromptOutcomeEvent)
{
    if (response.Count > 0)
    {
        silenceTimes = 0;
        var actionList = new List<ActionBase>();
        actionList.Add(GetPromptForText(response));
        actionList.Add(GetRecordForText(string.Empty));
        playPromptOutcomeEvent.ResultingWorkflow.Actions = actionList;
        response.Clear();
    }
    else
    {
        if (sttFailed)
        {
            playPromptOutcomeEvent.ResultingWorkflow.Actions =
                new List<ActionBase>
                {
                    GetRecordForText("I didn't catch that, would you kindly repeat?")
                };
            sttFailed = false;
            silenceTimes = 0;
        }
        else if (silenceTimes > 2)
        {
            playPromptOutcomeEvent.ResultingWorkflow.Actions =
                new List<ActionBase>
                {
                    GetPromptForText("Something went wrong. Call again later."),
                    new Hangup()
                    {
                        OperationId = Guid.NewGuid().ToString()
                    }
                };
            playPromptOutcomeEvent.ResultingWorkflow.Links = null;
            silenceTimes = 0;
        }
        else
        {
            silenceTimes++;
            playPromptOutcomeEvent.ResultingWorkflow.Actions =
                new List<ActionBase>
                {
                    GetSilencePrompt(2000)
                };
        }
    }
    return Task.CompletedTask;
}
```

The first time this event is raised is when we have recorded the user's input and have passed it to the `BingSpeech` class. At this point of time, we may or may not have any output from the bot itself. If there are any output(reply) from the bot, it will be added to `response` list. The `response` field contains the `List<string>` which are returned by bot to the user. If `response` is not empty, we get the `PlayPrompt` Action for the responses and add it to the workflow. We add a `Record` action after `PlayPrompt` to capture the next input from caller.
In case the `response` is empty, it may mean one of the following two things, either the STT conversion failed or the processing of earlier input is yet not completed by the bot. If the STT conversion failed, we play a prompt to user and ask him to repeat and start the recording again. If the bot has not yet processed the previous input, then we start another *silence* prompt. We maintain a counter for how many times did we end up waiting for bot to complete processing, if it increases a threshold, we gracefully hangup.

#### OnHangupCompleted

```csharp
private Task OnHangupCompleted(HangupOutcomeEvent hangupOutcomeEvent)
{
    hangupOutcomeEvent.ResultingWorkflow = null;
    return Task.FromResult(true);
}
```

Self-explanatory. Just set the workflow to null and return.

---

### Intercepting Bot response

Microsoft Bot Framework does not return the response/reply in-line to the HTTP request. Instead it sends a separate HTTP request to Bot Connector with the reply message. We can intercept this flow by implementing `IBotToUser` interface. The default implementation which sends the message to Bot Connector is called `AlwaysSendDirect_BotToUser`. We will create a class `BotToUserSpeech` and derive this interface.

```csharp
public BotToUserSpeech(IMessageActivity toBot, Action<string> _callback)
{
    SetField.NotNull(out this.toBot, nameof(toBot), toBot);
    this._callback = _callback;
}

public IMessageActivity MakeMessage()
{
    return this.toBot;
}

public async Task PostAsync(IMessageActivity message, CancellationToken cancellationToken = default(CancellationToken))
{
    _callback(message.Text);
    if (message.Attachments?.Count > 0)
        _callback(ButtonsToText(message.Attachments));
}
```

The constructor takes two parameters, the first being `IMessageActivity` and the second being a delegate to return the response to. This is the same delegate which was passed in `BingSpeech` class constructor in `OnRecordCompleted` event. The delegate just adds the string to `response` field. We need to implement just two method to MakeMessage and PostAsync. In MakeMessage we just return back the `IMessageActivity` object that we received from constructor. In PostAsync, we call the _callback delegate with the message text field. If the message has any attachment, we convert the buttons and cards in the attachment to plain string which is then passed to _callback. This ensures that buttons which are displayed to user normally in chat windows, gets converted to simple text so that the caller has all the options.


Once we have this class ready, we just need to wire it up in the dependency container which we do in `BingSpeech` class.

### BingSpeech

This class performs three tasks (talk about SRP!!!). First it receives the audio stream and sends it in chunks to Bing Speech API. Second it receives the event which is raised once the Bing Speech completes the STT conversion. Third it takes the STT output, and sends it to our RentACar bot. For this step it must setup the required dependencies and get instances through container to pass the message in *correct* format. Let's step through each of them one by one. But before that, put the Bing Speech API subscription key in `SubscriptionKey` property.

```csharp
string SubscriptionKey { get; } = "Bing Speech subscription key";
```

#### Perform Speech-To-Text

```csharp
public void CreateDataRecoClient()
{
    this.dataClient = SpeechRecognitionServiceFactory.CreateDataClient(
        SpeechRecognitionMode.ShortPhrase,
        this.DefaultLocale,
        this.SubscriptionKey);

    this.dataClient.OnResponseReceived += this.OnDataShortPhraseResponseReceivedHandler;
}
```

First we ask `SpeechRecognitionServiceFactory` to give us a `DataClient` instance. `SpeechRecognitionServiceFactory` can give us 4 types of clients -

* MicrophoneClient: Used to get audio stream by using device's microphone and then perform STT conversion.
* DataClient: No microphone support. You can use it to pass audio from `Stream`.
* MicrophoneClientWithIntent: Same functionality as MicrophoneClient. Additionally it will also send the text to LUIS and return LUIS entities and intents along with the text.
* DataClientWithIntent: Same as DataClient. Additionally it too will send the STT result to LUIS to perform intent and entity detection.

In our scenario, we already receive voice stream from Skype and the NLP part will be done by our bot, therefore `DataClient` would work out for us.
Next we subscribe to event `OnResponseReceived`, as this will be raised once STT processing is done by Bing Speech for complete stream.

```csharp
public void SendAudioHelper(Stream recordedStream)
{
    int bytesRead = 0;
    byte[] buffer = new byte[1024];
    try
    {
        do
        {
            // Get more Audio data to send into byte buffer.
            bytesRead = recordedStream.Read(buffer, 0, buffer.Length);

            // Send of audio data to service.
            this.dataClient.SendAudio(buffer, bytesRead);
        }
        while (bytesRead > 0);
    }
    catch (Exception ex)
    {
        WriteLine("Exception ------------ " + ex.Message);
    }
    finally
    {
        // We are done sending audio.  Final recognition results will arrive in OnResponseReceived event call.
        this.dataClient.EndAudio();
    }
}
```

`SendAudioHelper` will use dataClient to send the audio stream to Bing Speech Service. Once the entire stream is processed, the result will be available in `OnResponseReceived` event.

```csharp
private async void OnDataShortPhraseResponseReceivedHandler(object sender, SpeechResponseEventArgs e)
{
    if (e.PhraseResponse.RecognitionStatus == RecognitionStatus.RecognitionSuccess)
    {
        await SendToBot(e.PhraseResponse.Results
                    .OrderBy(k => k.Confidence)
                    .FirstOrDefault());
    }
    else
    {
        _failedCallback(true);
    }
}
```

If the STT conversion is successful, we order the result by confidence score and send it to our bot. Otherwise we call the callback for failure which sets a flag to true. This flag was then checked back at `OnPlayPromptCompleted` to either proceed or request caller to speak again.


#### Send to bot

Next challenge is to take the STT result and construct a valid `Activity` instance. Why? Because everything in Bot Builder depends upon a proper instance of `IMessageActivity`. Moreover we need to wire-in our `BotToUserSpeech` class. We do this by registering it into Autofac `ConnectionBuilder` while starting a new `LifetimeScope`.

```csharp
private async Task SendToBot(RecognizedPhrase recognizedPhrase)
{
    Activity activity = new Activity()
    {
        From = new ChannelAccount { Id = conversationResult.Id },
        Conversation = new ConversationAccount
        {
            Id = conversationResult.Id
        },
        Recipient = new ChannelAccount { Id = "Bot" },
        ServiceUrl = "https://skype.botframework.com",
        ChannelId = "skype",
    };

    activity.Text = recognizedPhrase.DisplayText;

    using (var scope = Microsoft.Bot.Builder.Dialogs.Conversation
      .Container.BeginLifetimeScope(DialogModule.LifetimeScopeTag, Configure))
    {
        scope.Resolve<IMessageActivity>
            (TypedParameter.From((IMessageActivity)activity));
        DialogModule_MakeRoot.Register
            (scope, () => new Dialogs.RentLuisDialog());
        var postToBot = scope.Resolve<IPostToBot>();
        await postToBot.PostAsync(activity, CancellationToken.None);
    }
}

private void Configure(ContainerBuilder builder)
{
    builder.Register(c =>
        new BotToUserSpeech(c.Resolve<IMessageActivity>(), _callback))
        .As<IBotToUser>()
        .InstancePerLifetimeScope();
}
```

The `Activity` instance must be valid. At least the 3 IDs needs to be specified to get and set context from state service. For the IDs, we can use `ConversationResult.Id` which is a unique for each conversation. We also have `ConversationResult.AppId` which is AppId of the caller but for some reason it was always null for me. Along with them, ServiceUrl and ChannelId should also be correct, otherwise bot will throw exception. Once we have a valid `Activity` instance, we assign it's text property to our STT output.


To send this `Activity` instance to the bot, we need to resolve instance of `IPostToBot`. Once we get it, we just call it's `PostAsync` method and pass the `Activity` instance. This would kick start our bot, deserialize the Dialog State and resume/start the conversation. This is exact flow which happens when we call `Conversation.SendAsync` from `MessageController`.

#### CallingController

Finally in `CallingController` pass the instance of `RentCarCallingBot` when registering the calling bot in the constructor.

```csharp
public CallingController()
    : base()
{
    CallingConversation.RegisterCallingBot(c => new RentCarCallingBot(c));
}
```

### Scalability Problems

The response from bot will eventually arrive at our `BotToUserSpeech` class, which would just pass the response text to our delegate which would add it to a list maintained in `RentCarCallingBot`. The list is then monitored when the workflow is finished and Skype API sends us a callback with result. We have put together everything in such a that once the bot finishes user recording, it then plays a silent prompt and monitors the response list.


This is where the problem lies. Our `BotToUserSpeech` class will capture the response and add it to the List. However in scenario where we have scaled out and have multiple bot services running behind a load balance, there is no knowing where the next callback from Skype API is going to land. Our current implementation locks us to only single bot service and prevents us from scaling.


We can resolve this issue by changing our implementation of `BotToUserSpeech` class. For example, instead of passing the response to a delegate, we can push it into a queue such as RabbitMQ. On the `OnPlayPromptCompleted` method, we can then check if there are any messages in the queue to play to the user. We must also take care of posting message to the queue when STT failed. So in short, both our delegates needs to be replaced by an out of process storing mechanism which can be accessed by multiple running services. Since RabbitMQ or any other queue can be monitored by multiple bot services, it solves our scalability issue.


### Testing our bot

We can test our bot locally by using ngrok. Ngrok creates a secure tunnel to localhost and provides us a public URL. Any call to public url will be forwarded to a service running on localhost at our system.
We create a tunnel `ngrok http --host-header=localhost 3999` to forward request to localhost:3999 where we will host our bot. Ngrok will then generate a random public URL. Note the https forwarding URL.

![ngrok]({{ site.baseurl }}/assets/images/posts/skypecall/ngrok.png)

The first place we need to change is in the web.config. Replace the value of *CallbackUrl* key by ngrok URL. It should look like **https://\<ngrokURL\>/api/calling/callback**.
Once we register our bot at [Bot Framework Portal](https://dev.botframework.com), click on **Edit** on Skype channel. We must enable **1:1 audio calls** feature. In the *Calling Webhook* text box, enter the ngrok URL in format of **https://\<ngrokURL\>/api/calling/call**.

![registration]({{ site.baseurl }}/assets/images/posts/skypecall/registration.png)


That's it. Run the bot locally on the same port that was tunneled by ngrok. We can then start making calls to our bot. Try speaking "Rent a car from London"

### Conclusion

In the evolution of UI, and the advent of bot, it is only natural that the next logical step is to voice call the bot. Imagine just calling your self-driving car to pick you up from your current location. Can't wait to live in such a world. The bot ecosystem is pretty new, and the voice call to bot feature itself is just emerging. The current platform is no where production ready. It's messy and STT is not accurate especially for non-US accent. We may see drastic improvement in Bing Speech service and the new [CRIS](https://www.cris.ai/) service looks promising. And with Microsoft achieving human parity in speech recognition, this dream may not be too far.