---
layout: post
title: BusyBot - Chat Bot for Skype for Business
comments: true
categories: [Microsoft Bot Framework, LUIS, Bots, Chat Bots, Conversational Apps, Skype For Business, Lync]
description: A chatbot for Skype for business
---

We use Skype for Business in our organization which is a fairly common IM applications used in enterprises. The most common distraction while working is popping up of Skype message. And then it takes even more time to reply and finish the conversation, because not replying to colleagues is just rude. So I thought why not create a bot that replies to the messages for me. Unfortunately, Microsoft Bot Framework does not support Skype for Business as one of the channels so I had to find another way to make it works.


Skype for Business has set of APIs called [Unified Communications Web API](https://msdn.microsoft.com/en-us/skype/ucwa/unifiedcommunicationswebapi2_0) which can enable us to integrate it with a bot, however it is unnecessarily complicated (it requires 5 HTTP calls to just send 1 message). So after searching a bit, I found that Lync 2013 SDK still works with Skype for Business (courtesy to my friend Om) and found an excellent starter code at Taha Amin's Github Repo [BotConnectorSkypeForBusiness](https://github.com/tahazayed/BotConnectorSkypeForBusiness).


Lync SDK is fairly straightforward to use. It is event-based and integrates easily with Bot Framework. The only limitation is that Lync 2013/Skype for Business should be already running. Using this I created a simple bot that would let me work in peace. Source code is over [here](https://github.com/ankitbko/SkypeForBusinessBot)

### Dependency
The bot has an **optional** dependency on Redis server. Since the bot will not be talking to Microsoft Bot Connector in any way, we would need to store bot's context somewhere ourself. I had earlier used locally running instance of Redis. However now I have commented out `RedisStore` and used `InMemoryStore`. To use Redis store uncomment the *region* in `Program.cs` and comment InMemory *region*.

You would also need Skype For Business running and signed in.

### Features

So what does the bot do as of now? It accepts the incoming IM and -

* Responds to greetings - Hi, Hello, Good Morning etc.
* In case the person wants to call me or asks whether I am free - respond that I am busy and will talk later and set my status to Busy.
* Ignore any other messages - *Pretend I am busy*
* Exception Filter - Bot does not reply anything if sender is present in **Exception List**. I don't want to reply to my manager that I am busy if he pings me. :)

### How to use

The bot is just a console application. The bot service is not hosted as Web Api, but runs within the console applications.
First create a new [LUIS](https://www.luis.ai/) application by importing the model json from `LuisModel` directory. Copy your LUIS model id and subscription key and paste it in `LuisModel` attribute in `LyncLuisDialog.cs`.


The exception list is located in `App.config` in the console project. Values are *;* separated.

```xml
<add key="ManagerList" value="sip:name1@domain.com;sip:name2@domain.com"/>
```

Make sure your Skype for Business client is running and you are signed in and just start the console project. Ask your friend to ping you and see what happens.


### How it works

Lync 2013 SDK is based on event driven programming. We just subscribe to right event `instantMessageModality.InstantMessageReceived += InstantMessageReceived;` and any messages will come to our `InstantMessageReceived` method.

```csharp
private void InstantMessageReceived(object sender, MessageSentEventArgs e)
{
    var text = e.Text.Replace(Environment.NewLine, string.Empty);
    var conversationService = new ConversationService((InstantMessageModality)sender);
    SendToBot(conversationService, text);
}
```

Once we get the message text, we bootstrap our bot and pass the text as properly formatted `Activity` message.

```csharp
private async void SendToBot(ConversationService conversationService, string text)
{
    Activity activity = new Activity()
    {
        From = new ChannelAccount { Id = conversationService.ParticipantId, Name = conversationService.ParticipantName },
        Conversation = new ConversationAccount { Id = conversationService.ConversationId },
        Recipient = new ChannelAccount { Id = "Bot" },
        ServiceUrl = "https://skype.botframework.com",
        ChannelId = "skype",
    };

    activity.Text = text;

    using (var scope = Microsoft.Bot.Builder.Dialogs.Conversation
        .Container.BeginLifetimeScope(DialogModule.LifetimeScopeTag, builder => Configure(builder, conversationService)))
    {
        scope.Resolve<IMessageActivity>
            (TypedParameter.From((IMessageActivity)activity));
        DialogModule_MakeRoot.Register
            (scope, () => new Dialogs.LyncLuisDialog(scope.Resolve<PresenceService>()));
        var postToBot = scope.Resolve<IPostToBot>();
        await postToBot.PostAsync(activity, CancellationToken.None);
    }
}
```

The bot then follows usual flow of sending the text to LUIS and determining the intent. Based on the context, it will then send it response back to - `BotToUserLync` class which implements `IBotToUser`. This allows us to catch the bot response and instead of sending it to the Bot Connector, we use Lync SDK once again to reply it to our counterpart.

The **Exception Filter** is managed in `ManagerScorable` which implements `IScorable<IActivity, double>`. Scorables are the way to intercept the bot pipeline and branch off with another logic based on requirements. In our case, we check if the incoming message was sent from anyone on the filter list and if it is then we just do nothing. I may write another post on Scorables and discuss about it a little more later.


### Conclusion

That's it. It took me a day to get it all done. The bot is very rudimentary but gets the job done. I now no longer have to reply toe very conversation when I am working. In any case, Skype for Business already saves all the conversation history so I can go over them once I get free. One day of work and lifetime of peace. :)


I hope this article was helpful. If you have any questions, please post a comment below.
