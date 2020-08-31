---
layout: post
title: Chatbot using Microsoft Bot Framework - Part 3
comments: true
categories: [Microsoft Bot Framework, LUIS, Bots, Chat Bots, Conversational Apps]
description: A guide on how to build chat bots using Microsoft Bot Framework - Part 3
---

This is third part in my series on Chat Bots. In [part one](https://ankitbko.github.io/2016/08/ChatBot-using-Microsoft-Bot-Framework-Part-1/) I discussed how chat bots worked and basics of Microsoft Bot Framework. In [part two](https://ankitbko.github.io/2016/08/ChatBot-using-Microsoft-Bot-Framework-Part-2/) I talked about LUIS and how it provides intelligence to our bot. I also built a simple bot using LUIS in background which answers questions of who I am. In this post, we will add more features to our bot, and see how LUIS detects entities along with intent. Before we proceed, I would mention that I have added application insight to my bot. As usual, head over to my [repo](https://github.com/ankitbko/MeBot/tree/part3) to get the source code.


Since my last post, I have added application insight to the code so that I can view telemetry in Azure. Also I have updated my BotBuilder nuget package to v3.2.

The next feature will let us ask the bot to fetch us articles for a particular topic. More specifically, we can ask bot to search my blog on a particular topic and return us the list posts associated with topic. An example query can be - "show me posts related to docker" should return all the articles having "docker" tag.

#### Enhancing LUIS

To achieve this, not only will LUIS have to classify the sentence to an intent but also return us entities from the sentence which will act as search terms eg. "docker". First, we will create a new entity and call it "Tag". Next, we will add another intent to LUIS named "BlogSearch". This time when training LUIS for this intent, we can select any word or group of words from the utterance and assign it to our entity as shown below. Just click on the word to assign it to an entity and it should get highlighted with a color.

![Entity]({{ site.baseurl }}/assets/images/posts/mebot-3/entity.png)

We will train the system with few more utterances. However we quickly see that LUIS is able to recognize entities already trained, but is having hard time with new words such as "Microsoft Bot Framework" as we see in the image below.

![Failed Entity]({{ site.baseurl }}/assets/images/posts/mebot-3/failedEntity.png)

This is happening because

1. We have not trained our system extensively.

2. LUIS has no way to know that "Microsoft Bot Framework" can be classified as a "Tag" entity since all our previous entities are not even similar to this one.

We can quickly get around it by utilizing another feature of LUIS called "Phrase List Features". It allow us to specify comma separated words which LUIS can use interchangeably when detecting an entity. In our case we will provide a list of tags from my blog. We will see that LUIS is now able to detect entities from phrase list we created.

![Phrase List]({{ site.baseurl }}/assets/images/posts/mebot-3/phraselist.png)

This is an advantage we have with LUIS as it uses Conditional Random Fields(CRF) for entity detection. CRF, unlike some other algorithms, takes neighboring words into account when detecting entities. That is, words preceding and succeeding are important when detecting an entity. With enough training, this allows LUIS to detect words as entities which were not trained before, just by looking at their neighboring words. Once we have sufficiently trained model, let's go and make changes to the code.

---

As before, we will add another method and decorate it with `[LuisIntent("BlogSearch")]`. I have written a class which will get my blog posts and get all the articles I have written along with it's associated tags. Then I filter the posts based on the "Tag" entity detected by LUIS.
My intent handler is pretty straightforward. I get the list of entities detected by LUIS in `LuisResult`. If I find an entity of type "Tag", I filter the posts comparing its associated tags with the LUIS detected entity. I then pass the list of filtered posts and tag to a private method which formats the response and returns back a string.

```csharp
[LuisIntent("BlogSearch")]
public async Task BlogSearch(IDialogContext context, LuisResult result)
{
    string tag = string.Empty;
    string replyText = string.Empty;
    List<Post> posts = new List<Post>();

    try
    {
        if (result.Entities.Count > 0)
        {
            tag = result.Entities.FirstOrDefault(e => e.Type == "Tag").Entity;
        }

        if (!string.IsNullOrWhiteSpace(tag))
        {
            var bs = new BlogSearch();
            posts = bs.GetPostsWithTag(tag);
        }

        replyText = GenerateResponseForBlogSearch(posts, tag);
        await context.PostAsync(replyText);
    }
    catch (Exception)
    {
        await context.PostAsync("Something really bad happened. You can try again later meanwhile I'll check what went wrong.");
    }
    finally
    {
        context.Wait(MessageReceived);
    }
}
```

Fireup emulator to check if everything is working as expected. We just added a new feature to our bot with few lines of code. Sweet!!!
![Blog Search]({{ site.baseurl }}/assets/images/posts/mebot-3/blogsearch.png)

---


#### Greetings Problem
A new user would most likely start conversation with "Hi" or similar greetings. Currently our bot responds with "I'm sorry. I didn't understand you." for any greetings. Well it is not a very good response to give when someone says "Hi". Let us do something about it. One way would be to create a "Greetings" intent in LUIS and train it to recognize "hi", "hello" etc. This is what I have been doing till now. However recently I found an excellent [blog post](http://www.garypretty.co.uk/2016/08/01/bestmatchdialog-for-microsoft-bot-framework-now-available-via-nuget/) by Garry Petty. He created an implementation of `IDialog` to match incoming message to list of strings through regular expression and dispatch it to a handler. So let us go ahead and take his help to solve our little problem here. This approach would also allow me to demonstrate how we can create and use child dialog.

First add reference to his nuget package [BestMatchDialog](https://www.nuget.org/packages/BestMatchDialog/). Next we create `GreetingsDialog` and derive it from `BestMatchDialog<object>`.

```csharp
[Serializable]
public class GreetingsDialog: BestMatchDialog<object>
{
    [BestMatch(new string[] { "Hi", "Hi There", "Hello there", "Hey", "Hello",
        "Hey there", "Greetings", "Good morning", "Good afternoon", "Good evening", "Good day" },
       threshold: 0.5, ignoreCase: false, ignoreNonAlphaNumericCharacters: false)]
    public async Task WelcomeGreeting(IDialogContext context, string messageText)
    {
        await context.PostAsync("Hello there. How can I help you?");
        context.Done(true);
    }

    [BestMatch(new string[] { "bye", "bye bye", "got to go",
        "see you later", "laters", "adios" })]
    public async Task FarewellGreeting(IDialogContext context, string messageText)
    {
        await context.PostAsync("Bye. Have a good day.");
        context.Done(true);
    }

    public override async Task NoMatchHandler(IDialogContext context, string messageText)
    {
        context.Done(false);
    }
}
```

In principle `BestMatchDialog` works in same way as `LuisDialog`. It would check the message against each of the strings in `BestMatch` attribute and calculate a *score*. Then the handler for the highest score is executed passing in the required context and message. If no handler is found with score above the threshold, `NoMatchHandler` is called.
Note in each handler we call `Context.Done` instead of `Context.Wait`. This is because we don't want next message to arrive in this Dialog. Instead this Dialog should finish and return back to it's parent Dialog which is `MeBotLuisDialog`. `Context.Done` will complete the current Dialog, pop it out of stack and return the result back to parent Dialog. We return `True` if we handled the greetings otherwise `False`. We then change the `None` intent handler in `MeBotLuisDialog` to one below -

```csharp
[LuisIntent("None")]
[LuisIntent("")]
public async Task None(IDialogContext context, IAwaitable<IMessageActivity> message, LuisResult result)
{
    var cts = new CancellationTokenSource();
    await context.Forward(new GreetingsDialog(), GreetingDialogDone, await message, cts.Token);
}

private async Task GreetingDialogDone(IDialogContext context, IAwaitable<bool> result)
{
    var success = await result;
    if(!success)
        await context.PostAsync("I'm sorry. I didn't understand you.");

    context.Wait(MessageReceived);
}
```

In None intent handler we call `context.Forward` which will create a child dialog of type `GreetingsDialog`, push it to top of stack and call it's `StartAsync` method passing message as argument. `GreetingDialogDone` is called once the child dialog completes i.e. child dialog calls `context.Done`.

Well this solves our little problem of handling greetings. One last thing we need to do. There should be a way for user to ask for help. We will create another LUIS intent called "Help" and train it with few utterances such as "need help". This will allow user flexibility to ask for help anytime. From our bot, we would return the functionality that our bot can do similar to what we return for ConversationUpdate ActivityType.


In this article we enhanced our bot to search through my blog and filter articles based on associated tags. We also created a child dialog to handle greetings and a way for user to get help. In next post, we will get into FormFlow and make our bot bit more conversational. Till then, if you have any questions or feedback post a comment.