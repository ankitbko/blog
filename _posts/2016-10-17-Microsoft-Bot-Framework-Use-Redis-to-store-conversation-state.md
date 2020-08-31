---
layout: post
title: Microsoft Bot Framework - Use Redis to store conversation state
comments: true
categories: [Microsoft Bot Framework, LUIS, Bots, Chat Bots, Conversational Apps, Redis]
description: Use Redis for storing conversation state
---

Bots created using Microsoft Bot Framework are by default stateless. The conversation state and it's associated context is stored by [Bot State Service](https://docs.botframework.com/en-us/restapi/state/) in cloud. The state service stores information in 3 distinct bags keyed by their associated ids -

| **Property**                  | **Key**                   | **Description**
|------------------------------ |---------------------------|----------------------------------------------------------
| **User**                      | User Id                   | Remembering context for a user on a channel
| **Conversation**              | Conversation Id           | Remembering context all users in a conversation
| **Private Conversation**      | Conversation Id + User Id | Remembering context for a user in a conversation


Bot State Service [documentation](https://docs.botframework.com/en-us/csharp/builder/sdkreference/stateapi.html) provides more detail explanation to them. Moreover all these property bags are scoped by the Bot id and Channel id, essentially making them unique.
The Dialog Stack and Dialog Data are both stored in Private Conversation bag.


If we want to store these data in our database, Bot Framework provides two extension points to do that -

* Create a REST layer by implementing `IBotState` interface
* Implement `IBotDataStore<T>` in your bot

In this post, we will implement `IBotDataStore` to store the context in Redis. However making a REST service by implementing `IBotState` should be similar. The source code is available [here](https://github.com/ankitbko/Microsoft.Bot.Builder.RedisStore).

### Redis Store

```csharp
public interface IBotDataStore<T>
{
    Task<bool> FlushAsync(BotDataKey key, CancellationToken cancellationToken);
    Task<T> LoadAsync(BotDataKey key, BotStoreType botStoreType, CancellationToken cancellationToken);
    Task SaveAsync(BotDataKey key, BotStoreType botStoreType, T data, CancellationToken cancellationToken);
}
```

`IBotDataStore` is a simple interface with only three methods to implement, all of them being self explanatory. We will start with `SaveAsync`. We will use [StackExchange.Redis](https://github.com/StackExchange/StackExchange.Redis) for C# client.

```csharp
public async Task SaveAsync(BotDataKey key, BotStoreType botStoreType, BotData data, CancellationToken cancellationToken)
{
    Connect();

    var redisKey = GetKey(key, botStoreType);
    var serializedData = Serialize(data.Data);

    var database = _connection.GetDatabase(_options.Database);
    var tran = database.CreateTransaction();
    if (data.ETag != "*")
        tran.AddCondition(Condition.HashEqual(redisKey, ETAG_KEY, data.ETag));
    tran.HashSetAsync(redisKey, new HashEntry[]
    {
        new HashEntry(ETAG_KEY, DateTime.UtcNow.Ticks.ToString()),
        new HashEntry(DATA_KEY, serializedData)
    });

    bool committed = await tran.ExecuteAsync();

    if (!committed)
        throw new ConcurrencyException("Inconsistent SaveAsync based on ETag!");
}
```

The critical part here is to maintain optimistic concurrency control for storing the data. This situation arises most commonly when the bot is in process of handling a user message and the user sends another message. The second message may end up in different bot instance which would start processing with older bot state. We will maintain optimistic concurrency using `ETag` property of `BotData`. ETag property will be set to `DateTime.UtcNow.Ticks`. If it differs while saving the new state, we will throw an exception. To achieve this we will use Transactions in Redis. Note that transactions in Redis works differently than your typical RDBMS. It gets more complicated due to how connection multiplexing is performed by StackExchange Redis client. An excellent explanation of this is given [here](https://github.com/StackExchange/StackExchange.Redis/blob/master/Docs/Transactions.md). In our code, we add a "Condition" for the transaction to be successful. If the condition fails, the entire transaction is void and `committed` will be false.


The `LoadAsync` method is pretty simple. We return `null` if there is no value for a particular key (first time scenario), otherwise we return `BotData`.

```csharp
public async Task<BotData> LoadAsync(BotDataKey key, BotStoreType botStoreType, CancellationToken cancellationToken)
{
    Connect();

    var database = _connection.GetDatabase(_options.Database);
    var redisKey = GetKey(key, botStoreType);
    var result = await database.HashGetAllAsync(redisKey);
    if (result == null || result.Count() == 0)
    {
        return null;
    }

    var botData = new BotData();
    botData.ETag = result.Where(t => t.Name.Equals(ETAG_KEY)).FirstOrDefault().Value;
    botData.Data = Deserialize((byte[])result.Where(t => t.Name.Equals(DATA_KEY)).FirstOrDefault().Value);
    return botData;
}
```

#### Integrating with Bot

To start using Redis Store instead of Bot State Service, we just need to override the existing Autofac registration of `IBotDataStore` with new one. The Bot Builder SDK uses `CachingBotDataStore` implementation for `IBotDataStore` which is just a decorator for `ConnectorStore`. We will replace `ConnectorStore` with `RedisStore`. Just call the `RegisterBotDependencies` in `Application_Start()` in Global.asax.cs and it will work.

```csharp
private void RegisterBotDependencies()
{
    var builder = new ContainerBuilder();

    RedisStoreOptions redisOptions = new RedisStoreOptions()
    {
        Configuration = "localhost"
    };

    builder.Register(c => new RedisStore(redisOptions))
       .As<RedisStore>()
       .SingleInstance();

    builder.Register(c => new CachingBotDataStore(c.Resolve<RedisStore>(),
                                                  CachingBotDataStoreConsistencyPolicy.ETagBasedConsistency))
        .As<IBotDataStore<BotData>>()
        .AsSelf()
        .InstancePerLifetimeScope();

    builder.Update(Conversation.Container);

    DependencyResolver.SetResolver(new AutofacDependencyResolver(Conversation.Container));
}
```

### Wrapping Up

As mentioned before, the other way to achieve the same is by creating a REST Api and implementing `IBotState`. However in essence, the way we do this would remain same.
Microsoft Bot Builder is highly flexible when it comes to extending it with custom logics. Again the source code is at my [github repo](https://github.com/ankitbko/Microsoft.Bot.Builder.RedisStore). I have also published it as a [nuget package](https://www.nuget.org/packages/Microsoft.Bot.Builder.RedisStore/).

I hope you liked it. Post a comment if you have any question.