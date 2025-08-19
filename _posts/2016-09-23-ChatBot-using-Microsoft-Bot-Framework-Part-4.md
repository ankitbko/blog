---
layout: post
title: Chatbot using Microsoft Bot Framework - Part 4
comments: true
categories: [Microsoft Bot Framework, LUIS, Bots, Chat Bots, Conversational Apps]
description: A guide on how to build chat bots using Microsoft Bot Framework - Part 4
---

I finally got time to write another post and with this I will finish of my blog series on Microsoft Bot Framework. In my [last post](https://ankitbko.github.io/2016/08/ChatBot-using-Microsoft-Bot-Framework-Part-3/), I showed how to use other features of LUIS such as entities and phrase list. I also showed how to nest Dialogs and how to maintain context between Dialogs. If you are new to Microsoft Bot Framework, I highly recommend you go through [part 1](https://ankitbko.github.io/2016/08/ChatBot-using-Microsoft-Bot-Framework-Part-1/), [part 2](https://ankitbko.github.io/2016/08/ChatBot-using-Microsoft-Bot-Framework-Part-2/) and [part 3](https://ankitbko.github.io/2016/08/ChatBot-using-Microsoft-Bot-Framework-Part-3/) of my blog series before continuing. As usual, you can find source code at my [github repo](https://github.com/ankitbko/MeBot/tree/part4).

In this post, I will delve into how FormFlow works and where it can be used. I will add another feature to my bot which will let user to send feedback to me through chat.


#### Adding Feedback Intent

I first enhance LUIS by adding another intent called "Feedback". I have trained LUIS for sentences such as "I want to send a feedback", I will not go into details as I have already covered LUIS aspects in my previous posts. There are no entities to return so I just leave it to this.

![Feedback]({{ site.baseurl }}/assets/images/posts/mebot-4/feedbackIntent.png)


### FormFlow

Till now I have only created conversations which are very shallow. In other words, it is a simple QA scenario where conversation does not flow deep and their are no context to maintain. However, there are many scenarios where I would need to take a more guided approach, where I may require multiple inputs from user and bot may take different path based on previous inputs. In short, I will need to create a state machine. A good example is ordering a pizza. I will need to ask a lot of questions such as size, crust, toppings, etc. and I will need to maintain them in the context. I will also need to provide a way for user to change previously entered data and I must only complete order once I have all the information with me. All of this would require managing a lot of state and workflow. This is where FormFlow comes in.

FormFlow sacrifices some of the flexibility of Dialogs to provide an easy way to achieve all the above. FormFlow itself is derived from `IDialog` so it can be nested within another dialog.

The basic idea behind `FormFlow` is *forms* i.e. collection of fields. Think of it as filling a form in any website. To order a pizza online, you would go to your favorite pizza restaurant's website, fill out a *form* with details such as type of pizza, crust, size etc, put down delivery address and then order it. At any point before placing the order, you can revisit and change any aspect of pizza.


To accomplish the same using FormFlow, I start with creating a class and adding public fields or properties. Each public field and property corresponds to a *field in the form*. So the user will be asked to input values for each field before *completing* the form. The way FormFlow achieves this is by creating a state machine in background and maintaining the transition between states. It also allows user to change any previously entered value for any field and view the current status of the *form*. You can read more about FormFlow in the [docs here](https://docs.botframework.com/en-us/csharp/builder/sdkreference/forms.html).


In my scenario of implementing feedback functionality, before allowing user to send a feedback, I will ask him to enter his name and contact info. Only when I have both the information, would I allow him to send a feedback message. To achieve this, I first create a class called `FeedbackForm` and properties for `Name`, `Contact` and `Feedback`.

```csharp
public class FeedbackForm
{
    [Prompt(new string[] { "What is your name?" })]
    public string Name { get; set; }

    [Prompt("How can Ankit contact you? You can enter either your email id or twitter handle (@something)")]
    public string Contact { get; set; }

    [Prompt("What's your feedback?")]
    public string Feedback { get; set; }

    public static IForm<FeedbackForm> BuildForm()
    {
        return new FormBuilder<FeedbackForm>()
            .Field(nameof(Contact), validate: ValidateContactInformation)
            .Field(nameof(Feedback), active: FeedbackEnabled)
            .AddRemainingFields()
            .Build();
    }
}
```

The `Prompt` attribute on top of fields allow me to specify what message would be shown to the user for asking him to enter value for the respective fields. Do note that FormFlow only accepts .NET primitive types, `enum` and `List<enum>` as Type for properties or fields. The `BuildForm` static method returns an `IForm<>` which would be used by `FormDialog` to build forms later. I will explain each line of the method -

* `new FormBuilder<FeedbackForm>()`: Create a new FormBuilder of type FeedbackForm. FormBuilder has fluent api to help me build it.
* `.Field(nameof(Contact), validate: ValidateContactInformation)`: Add the property `Contact` to the form and set a delegate to validate the input. ValidateContactInformation delegate will be called whenever user inputs for this field.
* `.Field(nameof(Feedback), active: FeedbackEnabled)`: Add the property `Feedback` to the form and assign an `ActiveDelegate` to it. This means that this field will be visible only when `ActiveDelegate` returns `true`.
* `.AddRemainingFields()`: Add any remaining valid public fields and properties to the form. In this case `Name`.
* `.Build();`: Build the form and return an `IForm<FeedbackForm>`.


The `ValidateContactInformation` delegate validates that the input is either a valid email address or starts with '@' to signify twitter handle.

```csharp
private static Task<ValidateResult> ValidateContactInformation(FeedbackForm state, object response)
{
    var result = new ValidateResult();
    string contactInfo = string.Empty;
    if(GetTwitterHandle((string)response, out contactInfo) || GetEmailAddress((string)response, out contactInfo))
    {
        result.IsValid = true;
        result.Value = contactInfo;
    }
    else
    {
        result.IsValid = false;
        result.Feedback = "You did not enter valid email address or twitter handle. Make sure twitter handle starts with @.";
    }
    return Task.FromResult(result);
}
```

The `ValidateAsyncDelegate` must return a `ValidateResult` object whose property `IsValid` should be set appropriately. If `IsValid` is set to `true`, FormFlow will assign the field to the value in `Value` property. This gives us chance to transform the user input before assigning it to the form. If the `IsValid` is set to `false`, text in `Feedback` field will be displayed to the user. This allows us to notify user why validation failed and give clear instructions as to what to do next. If the validation fails, the FormFlow will ask user to enter the value again.


Each field can be controlled as to whether it is available to be filled or not by `ActiveDelegate`. The `ActiveDelegate` returns a `bool`, if it is `true` the field is available to be filled by the user else it will be not be shown.

```csharp
 private static bool FeedbackEnabled(FeedbackForm state) =>
    !string.IsNullOrWhiteSpace(state.Contact) && !string.IsNullOrWhiteSpace(state.Name);
```

This completes creation of my form, next I will add an intent handler.

#### Add handler for Feedback intent

```csharp
[LuisIntent("Feedback")]
public async Task Feedback(IDialogContext context, LuisResult result)
{
    try
    {
        await context.PostAsync("That's great. You will need to provide few details about yourself before giving feedback.");
        var feedbackForm = new FormDialog<FeedbackForm>(new FeedbackForm(), FeedbackForm.BuildForm, FormOptions.PromptInStart);
        context.Call(feedbackForm, FeedbackFormComplete);
    }
    catch (Exception)
    {
        await context.PostAsync("Something really bad happened. You can try again later meanwhile I'll check what went wrong.");
        context.Wait(MessageReceived);
    }
}
```

Here I create a new `FormDialog` object by passing the new instance of `FeedbackForm` and `BuildFormDelegate` which I have defined above. The `BuildFormDelegate` will be used by FormFlow to build the form. `FormOptions.PromptInStart` tells the bot to prompt user for the first field to be filled as soon as the dialog starts. FormDialog has another optional parameter which takes `IEnumerable<EntityRecommendation>`. This can be used to pass the entities returned by the LUIS and FormFlow will *pre-populate* the form and will not ask the user to fill in those fields.


Next I use `context.Call` to push my `FormDialog` to top of the `DialogStack`. Unlike `context.Forward`, `context.Call` will not pass the current message to the Dialog. Instead the next message from the user will be routed to the child dialog.


`FeedbackFormComplete` is called once all the fields in my form is successfully filled and the form completes. I also get the completed form passed in the `result` parameter.

```csharp
private async Task FeedbackFormComplete(IDialogContext context, IAwaitable<FeedbackForm> result)
{
    try
    {
        var feedback = await result;
        string message = GenerateEmailMessage(feedback);
        var success = await EmailSender.SendEmail(recipientEmail, senderEmail, $"Email from {feedback.Name}", message);
        if (!success)
            await context.PostAsync("I was not able to send your message. Something went wrong.");
        else
		{
            await context.PostAsync("Thanks for the feedback.");
			await context.PostAsync("What else would you like to do?");
		}

    }
    catch (FormCanceledException)
    {
        await context.PostAsync("Don't want to send feedback? That's ok. You can drop a comment below.");
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

I use SendGrid to send a mail to myself with the feedback message which I get from completed form. The interesting part here is the catch block for `FormCanceledException`.
`FormCanceledException` is thrown when user quits or cancels the form. This is another feature of FormFlow. User can quit the form anytime by typing 'quit' or 'bye'. Along with this, user can type 'Help' anytime to view all the available options if he feels stuck anywhere and 'Status' to view the current state of form. These *commands* are configurable and list of them is available in 'Help' menu.

![Help]({{ site.baseurl }}/assets/images/posts/mebot-4/help.png)
![Status]({{ site.baseurl }}/assets/images/posts/mebot-4/status.png)


### Wrapping up
This is it. We have created a bot and in the process I have explained fundamentals of bots and Microsoft Bot Framework. But in no way have I touched upon every feature of Bot Framework. There are many other features such as `Scorable`, `BotState`, `IPostToBot`, `IBotToUser` etc. which are very useful and you should definitely explore. Voice calling through Skype is an upcoming feature which can be integrated to the bot. There are many other cognitive services which can be integrated with bots to make it more smarter. Microsoft Bot Framework is a powerful and feature rich platform to build bots. The open source community around it is great and developers are quick to respond to any issues.

I will write more about above things in future. If you have any specific topic which you would like me to write about, drop a comment or send a feedback through bot :).
