---
layout: post
title: Skype for Business bot using UCWA
comments: true
categories: [Microsoft Bot Framework, LUIS, Bots, Chat Bots, Conversational Apps, Skype For Business, UCWA]
description: Chatbot for Skype for business online using UCWA
---

I had recently written a post on how to create a [Skype for Business chatbot](/2017/01/BusyBot-Sykpe-For-Business-Bot/). In that I used Lync 2013 SDK to intercept messages and pass to bot. However I mentioned in my post that there is a better way to achieve the same by using [Unified Communications Web API 2.0](https://msdn.microsoft.com/en-us/skype/ucwa/unifiedcommunicationswebapi2_0)(UCWA). Since then I had received a lot of request to write a post on how to do the same. Though I had the code available with me(thanks to Om Shrivastava, my colleague), I did not post it because it was is a very bad shape(you will see). But since there was a lot of demand for it and after discussing with my readers(thank you Dan Williams and Hitesh), I finally got down to do some cleaning up. You can find the source code [here](https://github.com/ankitbko/ucwa-bot). The source code is based on [Tam Huynh UCWA Sample](https://github.com/tamhinsf/ucwa-sfbo-console), a really well written sample which I then made a mess of.

### What is UCWA and why should I care?
From Microsoft's own words:

> Microsoft Unified Communications Web API 2.0 is a REST API that exposes Skype for Business Server 2015 instant messaging (IM) and presence capabilities.

Ok, so it is set of APIs, but why can't I just keep on using Lync 2013 SDK for my bot as I created [previously](/2017/01/BusyBot-Sykpe-For-Business-Bot/)?.

Well, using Lync 2013 SDK has one major demerit. It requires the bot to run on the system where Skype For Business(SFB)/Lync 2013 is installed and running. That means you are tied down to a machine which would also create problems with scaling. Plus you are dependent upon 4 years old SDK which is no more recommended by Microsoft.

UCWA solves all these problems. Using UCWA, we now no longer need a SFB client running on the system. Bot can be deployed anywhere and scaled independently.


UCWA has a lot of capabilities. However what interests us most is how to [send messages](https://msdn.microsoft.com/en-us/skype/ucwa/sendanim) and [receive messages](https://msdn.microsoft.com/en-us/skype/ucwa/receiveanim). Each of these tasks require us to send series of HTTP requests in *order* to UCWA endpoints. I recommend you read through the above links to understand how it works.

### Getting Started
Before even delving into code, you need to set up a lot of things. When developing UCWA applications you need to target either *Skype For Business Online* or *Skype for Business Server(On-Premise)*. Both have different setup procedure. I recommend you to read through [MSDN documentation](https://msdn.microsoft.com/en-us/skype/ucwa/developingapplicationswithucwa) to understand the differences. In this article and the accompanying code, I would only work with *Skype For Business Online*. This is primarily because I don't have an on-premise installation.


The pre-requisite to this is that you must have Office 365 subscription and access to Azure Active Directory to which O365 is linked. Also for setting up you would need to grant permission to our app in Azure Active Directory, which only AD admin can do. Also create two users in Active Directory, one which bot would sign in as and other to test sending message to bot.


Once you have these things ready, the next step is to create an *application* in Azure Active Directory. I recommend you follow Tam Huynh's excellent [guide](https://github.com/tamhinsf/ucwa-sfbo-console/blob/master/README.md).


Once you have the app in azure AD properly setup, keep `TenantID`, app's `ClientID` and app's `RedirectURI` handy as we would need them in the code.

### Understanding the solution structure

The code itself is just a *Console Application*. The solution contains 4 folders:

- The **Bot** folder contains the `Dialog` class and an implementation of `IBotToUser`. All these classes are related to Bot Framework. I have used `EchoDialog` from the bot framework sample which echoes back the initial message with a count.
- **UcwaSfbo** folder mostly contains classes as it is from Tam Huynh's sample except for `UcwaReciveMessage.cs` and `UcwaSendMessage.cs`. As name suggests, these two classes are used to receive and send messages to SFB.
- **Utilities.cs** contains some some convenience methods.
- **Data** folder contains auto generated classes that represents UCWA JSON responses.

---

#### Code Smell

**Data** folder is a mess. All these classes were auto-generated based on responses from UCWA APIs. Therefore there are lot of duplicate classes. I tried to clean up some of it but couldn't get time to see it through. `UcwaReciveMessage.cs` and `UcwaSendMessage.cs` are also not very well written. It was hastily written as a first attempt to get a PoC on UCWA. Once you get the understanding of what is happening, I would suggest you rewrite them for your own applications.

### Setting up the code
Open `Program.cs` and you would see some `static strings`. Replace the values of `tenantId`, `clientId` and `redirectUri` to what you copied before. `hardcodedUsername` and `hardcodedPassword` are credentials for the user that you would want the bot to sign in as. If you don't want to hardcode the credentials, that is fine too as we will see later. `destinationAddress` is not used so you could leave it as it is.

Go to `App.config` and enter a valid `MicrosoftAppId` and `MicrosoftAppPassword` for an existing registration of bot in bot framework portal. It is required as we would be using Bot State Service to store the conversation state.


Once done run the sample and you would be greeted by a console message to choose a login style. **If you are running the project for first time after creating the AD app, choose `dialog` option.** This is needed as you would be asked to provide some consent, which requires a web page so `console` login doesn't work. This only needs to be done once. Next time you could just use `console` option and bot would sign in using hardcoded credentials which we defined before. If you don't want to hardcode, your only choice to proceed is through `dialog` option.

If the program started successfully you would see json responses in the console. Login to Skype for Business as the other user and send the message to the bot. The bot should echo back what you typed. Great!! Our bot is working as expected.

### Under the hood

Once the bot signs in using the credentials provided, it polls the UCWA for incoming messages. As mentioned before, you need to send series of requests to UCWA in specific order for this to work. All this is handled in `UcwaReciveMessage.cs` class. When you send a message to the bot, the message is actually received in `GetIM_Step03_Events` method. Once I get the message I create the `Activity` object with minimum information required.


```csharp
string SendMessageUrl = item1._embedded.message._links.messaging.href;
var conversationId = item.href.Split('/').Last();
var fromId = item1._embedded.message._links.contact.href.Split('/').Last();

Activity activity = new Activity()
{
    From = new ChannelAccount { Id = fromId, Name = fromId },
    Conversation = new ConversationAccount { Id = conversationId },
    Recipient = new ChannelAccount { Id = "Bot" },
    ServiceUrl = "https://skype.botframework.com",
    ChannelId = "skype",
    ChannelData = SendMessageUrl
};

activity.Text = message;
```

The `conversationId` and `fromId` are extracted from the JSON response. These are required as the conversation state are stored using these key. `SendMessageUrl` is required to reply to user. We store it in the `ChannelData` property of `Activity`.


Once `activity` object is properly initialized, we jump start the bot and pass the `activity` object as the incoming message. Instead of starting the bot here, or if you have an existing bot, you could use [Direct Line API](https://docs.botframework.com/en-us/restapi/directline3/) to send the message to the bot.


```csharp
using (var scope = Microsoft.Bot.Builder.Dialogs.Conversation
    .Container.BeginLifetimeScope(DialogModule.LifetimeScopeTag,
    builder => Configure(builder)))
{
    scope.Resolve<IMessageActivity>
        (TypedParameter.From((IMessageActivity)activity));
    DialogModule_MakeRoot.Register
        (scope, () => new EchoDialog());
    var postToBot = scope.Resolve<IPostToBot>();
    await postToBot.PostAsync(activity, CancellationToken.None);
}
```

In the `Configure` method I register my custom implementation of `IBotToUser`.


```csharp
private static void Configure(ContainerBuilder builder)
{
    builder.RegisterType<BotToUserLync>()
       .As<IBotToUser>()
       .InstancePerLifetimeScope();
}
```

`BotToUserLync` reads the `ChannelData` property of the `Activity` and calls `SendIM_Step05` method of `UcwaSendMessage` which sends a request to UCWA to reply to the user.

### Conclusion

Using UCWA is easy once you understand how it works. However it is tiring process to write code against it. There are lot of steps to follow in particular order and lack of any SDK makes it more difficult. The present sample is not at all production ready. I would recommend you use this sample to understand what happens inside and implement a better(and cleaner) solution if you are developing it for a live environment.


I hope this article was helpful. If you have any questions, please post a comment below.
