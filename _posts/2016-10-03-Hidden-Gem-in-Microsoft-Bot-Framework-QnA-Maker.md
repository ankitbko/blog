---
layout: post
title: Hidden Gem in Microsoft Bot Framework - QnA Maker
comments: true
categories: [Microsoft Bot Framework, LUIS, Bots, Chat Bots, Conversational Apps]
description: Use QnA Maker to quickly create a QnA Bot
---

One of the most common use cases in Bot space is to create a bot to answer FAQ. And almost all businesses has an FAQ either in form of documents or web pages. Now it is not at all difficult to create a bot to answer simple questions. In fact there are hardly any context to maintain and most of the conversations are very shallow which makes it a very repetitive and quite boring task. All the FAQs are mostly same, well they are just list of questions and answers. Only if there would have been a way to upload this "knowledge" and create an NLP model based on the questions without us having to write any code.


Enter [QnAMaker](https://qnamaker.botframework.com), one of the least documented and almost non-existent service offered by Microsoft. QnAMaker allows us to upload a FAQ document or just give a link to a FAQ page and it will create an NLP model and expose an endpoint to query.

### QnA Maker

QnA Maker is provided as a service which is part of Microsoft Bot Framework. It is really hard to find as there are no external links to the page and absolutely no documentation. The only way to reach it by directly going to the sub-domain [qnamaker.botframework.com](https://qnamaker.botframework.com).

![QnA Maker]({{ site.baseurl }}/assets/images/posts/qnamaker/qnamaker.png)

Once on the page, we can create a new service by clicking "Create a new QnA service". We will be redirected a page with list of steps to create QnA Service. We will create a QnA service to answer questions about Bot Framework itself. The Bot Framework FAQ is available at it's [documentation](https://docs.botframework.com/en-us/faq/).

![QnA Edit]({{ site.baseurl }}/assets/images/posts/qnamaker/qnaedit.png)

* Name your service: The first step is to give a name to our service. Let's name it "botframework".
* FAQ URL: This is one of the three steps to seed the QnA Maker with questions and answers. QnA Maker provides sample sites as how the FAQ page should look like. However it is not limited to the same format. Most of the FAQ pages, which clearly separates questions and answers, works with QnA Maker. Here we will provide "https://docs.botframework.com/en-us/faq/" as single line entry.
* Question and Answer Pairs: This is the second way to provide questions and answers. The format is `question:answer` one per each line. We will leave this field blank.
* Upload files: The third and last way to seed data is to upload a file(doc, docx, txt, tsv or pdf) containing questions and answers in a sequence. This too we will leave as it is.


Click on "Extract" and wait a while. The QnA maker will extract all the questions and create an NLP model (probably LUIS). It would also show how many question-answer pair were extracted just above "Next" button. Clicking on it will download a tsv file with question-answer pair.

![QnA Extracted]({{ site.baseurl }}/assets/images/posts/qnamaker/qnaextracted.png)

Click on "Next" to go to fifth and last step which is to test and re-train our model.

![QnA Train True]({{ site.baseurl }}/assets/images/posts/qnamaker/traintrue.png)

This window has three parts. In the middle is a chat bot embedded as an iframe. Enter a question from FAQ in the chat bot and it should respond back with the answer.
The right side of chat bot allows us to enter alternate phrasings to a question. This will further reinforce the model and make it better at classifying the questions correctly. As you can see in the image, I have added another phrase "what is release timeline for bot framework" to this question.
The left side can be used to choose a correct response in case the bot answers incorrectly. The QnA Maker will automatically display answers related to the question. When asked "when the bot framework be publicly available", it returned wrong response. I selected the correct response from the list of responses which appeared on the left.
Once satisfied with the responses, click "Re-Train" to train the model again.


Click on "Publish" to make the service available over an URL.

![QnA End]({{ site.baseurl }}/assets/images/posts/qnamaker/end.png)

Using the "Service URL" we can test the service to see what it returns.

![QnA End]({{ site.baseurl }}/assets/images/posts/qnamaker/result.png)

The question is supplied in the query string and the service returns a json containing an "answer" and a confidence "score". The score tells us how confident is the QnA Maker that it has responded back with correct answer to the question. The score varies from 0-100, higher the number more confident it is.

#### Conclusion

QnA Maker is a powerful tool to quickly create an FAQ bot. However there are couple of limitations. First it does not expose the underlying NLP model. Most likely it uses LUIS internally and it creates an intent for each question. We do not get access to the LUIS or the trained model. Second it is very less documented and there are almost no mention of it anywhere. Which begs the question on how long will it be supported and whether there are any technical limitations and cost to the usage of the service. Overall this is a fine piece of work which lets us create a bot in minutes.


I hope this article was helpful. If you have any questions, please post a comment below.