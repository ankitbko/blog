---
layout: post
title: Chatbot using Microsoft Bot Framework - Part 2
comments: true
categories: [Microsoft Bot Framework, LUIS, Bots, Chat Bots, Conversational Apps]
description: A guide on how to build chat bots using Microsoft Bot Framework - Part 2
---

This is second post in the series of building a chat bot. If you haven't gone through Part 1, you can find it [here](https://ankitbko.github.io/2016/08/ChatBot-using-Microsoft-Bot-Framework-Part-1/). It sets the context and talks about basics of Microsoft Bot Framework. The source code for bot can be found at my [github repo](https://github.com/ankitbko/MeBot).

In this article, I will add the first feature to my bot which is to answer questions about me. The bot should answer questions such as "Who is Ankit", "Who is author of this blog", etc. As I showed previously, the bot in itself is dumb. To understand such questions I will need to take help from LUIS.

### Language Understanding and Intelligence Service

[LUIS](https://www.luis.ai/) Natural Language Processing Service is one of the cognitive services by Microsoft. In general, there are two things LUIS can possibly do -

* **Intent Recognition**: Whenever a user sends a message to my bot, he has an intent. For instance if user types "I want to order a pizza" his intent is "OrderPizza", "I want to rent a car" intent is "RentCar" etc. Given a sentence, LUIS will to classify the sentence into one of the trained intents and give me probability score for each intent. The way I achieve this is by defining the intents and training the LUIS with some sentences (called utterances) by manually classifying them. This type of learning is called Supervised Learning and the algorithm which LUIS uses to classify is Logistic Regression.

* **Entity Detection**: In a sentence, I might be interested in a word or group of words. For example in "I want to order a pepperoni pizza" text "pepperoni" is the word I am interested in. Another example, "Rent a car from London airport tomorrow" - "London airport" and "Tomorrow" are the words which are contextually important to me. LUIS can help me by recognizing these words (called entities) from the sentence. LUIS uses Conditional Random Fields (CRF) algorithm to detect entities, which falls under Supervised Learning. Therefore this is again achieved by training LUIS with some words manually before it can start detecting.

A great tutorial explaining these in detail is present at [Luis Help](https://www.luis.ai/Help). It is a short tutorial which I recommend you go through it later for better understanding.

#### Create a LUIS App

Go over to [luis.ai](https://www.luis.ai) and create a new App. By default, we get one intent called `None`. Any utterances which we feel does not classify into any other intent in our app should be trained under None. Training `None` is important, I have seen many people not training it sufficiently.

#### Training Luis

Let me create a new intent named `AboutMe`. While creating intent I have to enter an example sentence that would be classified to it. Enter "Who is Ankit" and created the intent. Click on Submit to classify the sentence to the intent. I can add more utterances by entering it into input box and classifying it to the intent as shown below. Add some utterances for `None` intent too.

![Intent]({{ site.baseurl }}/assets/images/posts/mebot-2/Intent.png)

Train the LUIS by clicking on "Train" button on bottom left. Next, publish the app so that it is available via HTTP. I can test the app and see what result LUIS returns. LUIS will classify the query into each intent and return me probability score for each.

![Luis Result]({{ site.baseurl }}/assets/images/posts/mebot-2/luisresult.png)

I have exported the LUIS app and added the JSON to the solution.

---

### LuisDialog

Once I have created the LUIS app, next step is to integrate it with my bot. Fortunately Bot Builder SDK provides me an easy way to integrate with LUIS. Enter `LuisDialog`. It derives from `IDialog` and does the low level plumbing work of interfacing with LUIS and deserializing the result back to `LuisResult`. Let me go ahead and create a new class called `MeBotLuisDialog` and derive it from `LuisDialog`. Next I add the following method to the class -

```csharp
[LuisIntent("None")]
public async Task None(IDialogContext context, LuisResult result)
{
    await context.PostAsync("I'm sorry. I didn't understand you.");
    context.Wait(MessageReceived);
}
```

Let me explain each line in above -

* `[LuisIntent("None")]`: Apart from calling LUIS API, `LuisDialog` also takes the result returned by LUIS, calculates the best intent based on probability score and calls the corresponding method defined in our dialog decorated with `LuisIntent` attribute matching the intent name passed as argument with the best intent detected. So, if LUIS classifies a sentence and scores it highest to "None" intent, our above method will get called automatically.

* `public async Task None(IDialogContext context, LuisResult result)`: Our method accepts two parameters, first is of type `IDialogContext` which as discussed before contains the stack of active dialog. It also has helper methods to send reply back to the user which we do in the next line. The second parameter is the result returned by the LUIS which is deserialized as `LuisResult`.

* `await context.PostAsync("I'm sorry. I didn't understand you.")`: I use the Dialog Context to send a reply back to the user. Since this method is called when my bot did not understand the user's intent, I return back a friendly response. Later I will modify it to return more detailed response.

* `context.Wait(MessageReceived)`: This is important. Before exiting from dialog, we must mention which method will be called when the next message arrives. If you forget it, you will get a very ambiguous runtime error something in the line of "need 'Wait' have 'Done'". We again use dialog context to specify it. `MessageReceived` method is defined in `LuisDialog` class and is the same method which calls the LUIS endpoint, calculates the best intent from the result and calls the relevant method for the intent.

So in short, I reply back to user saying that I didn't understand and specify that next message should also be sent to the LUIS to understand the user intent.
Let me add method to handle "AboutMe" intent.

```csharp
[LuisIntent("AboutMe")]
public async Task AboutMe(IDialogContext context, LuisResult result)
{
    await context.PostAsync(@"Ankit is a Software Engineer currently working in Microsoft Center of Excellence team at Mindtree. He started his professional career in 2013 after completing his graduation as Bachelor in Computer Science.");
    await context.PostAsync(@"He is a technology enthusiast and loves to dig in emerging technologies. Most of his working hours are spent on creating architecture, evaluating upcoming products and developing frameworks.");
    context.Wait(MessageReceived);
}
```

This is also similar to the "None" intent handler. Instead of sending only one response, I send two since the sentences are quite big. The response is quire simple but let me keep it this way. Decorate the `MeBotLuisDialog` class with `[LuisModel("modelid", "subskey")]` with correct LUIS ModelId and Subscription Key. You can get the keys from published URL of your LUIS app.
There is just one more place that I need to change before I can test my bot that is in `MessageController`. Replace the entire `If` section of the method with the one below -

```csharp
if (activity.Type == ActivityTypes.Message)
{
    await Conversation.SendAsync(activity, () => new MeBotLuisDialog());
}
```

Done. Press F5 to run the bot. Open the emulator and send a text to check if the bot is replying properly.

![About me]({{ site.baseurl }}/assets/images/posts/mebot-2/aboutme.png)


One last feature to add. When a user add/open my bot for the first time, it is good practice to show a welcome text having information about what my bot can do and how to interact with it. Let me add a small help text and send it to the user when he first interacts with my bot. The place to do it is in `ActivityTypes.ConversationUpdate` block in `MessageController`. Microsoft Bot Framework supports Markdown, which I can utilize to give a richer experience to my user. I have added the relevant welcome text as below.

```csharp
else if (message.Type == ActivityTypes.ConversationUpdate)
{
    // Handle conversation state changes, like members being added and removed
    // Use Activity.MembersAdded and Activity.MembersRemoved and Activity.Action for info
    // Not available in all channels
    string replyMessage = string.Empty;
    replyMessage += $"Hi there\n\n";
    replyMessage += $"I am MeBot. Designed to answer questions about this blog.  \n";
    replyMessage += $"Currently I have following features  \n";
    replyMessage += $"* Ask question about the author of this blog: Try 'Who is Ankit'\n\n";
    replyMessage += $"I will get more intelligent in future.";
    return message.CreateReply(replyMessage);
}
```


#### Registering the bot

Before registering, I need to publish my bot and make it accessible from internet over HTTPS. Once done, head over to bot [registration portal](https://dev.botframework.com/bots/new). An excellent article on how to register the bot is [here](https://docs.botframework.com/en-us/csharp/builder/sdkreference/gettingstarted.html#registering). Once registered, update the `web.config` with correct id and secret and publish the bot again.

Registering the bot will auto-configure it with skype. But let me go a step further and configure the Web Chat Channel. Configuring web chat gives me an iframe which I can include in my web site. I have added the iframe to my blog and the bot appears at the bottom right corner. This is so cool.

I have tagged the code till this point as part2 in my [repo](https://github.com/ankitbko/MeBot/tree/part2). In next post I will add more features to my bot.
Meanwhile if you have any questions or feedbacks, post a comment below.