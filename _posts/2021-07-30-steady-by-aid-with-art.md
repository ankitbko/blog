---
layout: post
title: STEADY by AID with ART
comments: true
categories: [design, software design]
description: Goals and Techniques for Software Design
image: images/previews/steady-by-aid.jpg
author: <a href='https://twitter.com/ankitbko', target='_blank'>Ankit Sinha</a>
---

> This post is heavily inspired by [Hints and Principles for Computer System Design by Butler Lampson](https://www.microsoft.com/en-us/research/publication/hints-and-principles-for-computer-system-design-3/) and is derived from my notes when reading the paper. My goal of this article was to condense information in Butler's paper into short actionable article that can be referenced when designing software. I strongly recommend reading the original paper.

Designing software is hard. It is not only a matter of writing code, but it is also a matter of managing complexity. Designing a system is very different from designing an algorithm. The requirements are complicated, unclear and always changing. The measure of success is not clear. There usually isn't a *"best"* way to design a system.

So what does the title of the article mean?
- Goals - **STEADY** - **S**imple, **T**imely, **E**fficient, **A**daptable, **D**ependable, **Y**ummy.
- Techniques - by **AID** - **A**pproximate, **I**ncremental, **D**ivide and Conquer.
- Process - with **ART** - **A**rchitecture, **A**utomate, **R**eview, **T**echinques, **T**est.

In this article we explore these ideas focusing mostly on *goals*. But before we get started we need to understand a bit about tradeoffs and oppositions.

# Tradeoffs and Oppositions

Designing a system is a balance between the following (not exhaustive list):
- **Complexity:** The system should be simple enough to be understood by a wide variety of people.
- **Flexibility:** The system should be flexible enough to be extended to meet the needs of the future.
- **Robustness:** The system should be robust enough to handle the failure of its components.
- **Portability:** The system should be portable enough to be used in a variety of environments.
- **Scalability:** The system should be scalable enough to be used in a large number of concurrent users.
- **Availability:** The system should output result even after partial failure.
- **Maintainability:** The system should be easy to maintain.
- **Reliability:** The system should output correct result and doesn't loose data in spite of partial failure.

Software design is an art of managing tradeoffs. In ideal world we could achieve all the above criteria. Unfortunately real systems are constrained by many factors which results in us making decisions on what is important. Some of these choices can even affect other choices indirectly. For example can we keep a system simple or should we make it more rich. Do we want to fetch all data from database (increase memory and I/O bandwidth) or paginate data (increased number of I/O calls). Some of these tradeoffs are talked later in the article. The *goals* described below will act as guide on making choices on tradeoffs.

Butler expresses this idea as form of *oppositions*. Oppositions are *extremes* between choices. These are not opposite but the endpoints of a range of possibilities. Imagine these oppositions as a continuous scale (like 1 to 10), and when designing make choice where your system will fall in this scale. Some of the examples of oppositions are `simple <-> rich`, `general <-> specialized`, `perfect <-> adequate`, `time <-> space`, etc. I will not discuss the oppositions in great length in this article so I recommend reading the paper to get better understanding of what oppositions are. But keep in mind the idea about oppositions being a scale of extreme possibilities.

# Goals
Goals are general properties that system should have, not the problems it tries to solve.

## Simple
Simple is arguably the most important goal but it gets forgotten all the time. Simplicity is the key to successful software design. Simple systems are easy to understand, easy to extend, and easy to maintain.

{% include tip.html content="Figure out how to solve one really tricky sticky problem and then leave the rest of the system straightforward and boring. I call this the “rocket science” pattern. —Terry Crowley" %}

- Design your system around a small number of *key* modules with simple specs and predictably good performance. This leaves rest of the code easy to change.
- *Key* modules will grow over time, get optimized and new features get added building a solid foundation.
- Make *key* module **fast** rather than **general** or **powerful**. This is a tradeoff between generalization and specialization. Slow and powerful module forces client to pay for power that it doesn't want or need.
- Beware of *universal goals* such as "create powerful storage" or "create a fast server". These do not provide enough value and add lot of generality and complexity.
- **Brute Force**: Computers have become faster - take advantage of it. Often times its not needed to implement a complex solution just to avoid (taboo)brute force solution. But there are many successful solutions that employ brute force. One common example is *polling* instead of notification, its simple and efficient if you can tolerate enough latency.
- **Reduction**: Solve a problem by reducing it to a problem that is easier to solve. This is fundamental to successful design. Although beware of reducing problem to an already solved problem which is not *simpler* but more complex. Using a fraction of power of a powerful module is often a good engineering. But it can be wasteful of resource, which is not always bad, but its easy to loose track of how much resource is being wasted.
- Code is read more number of times than it is written. Keep the code simple to read and understand.


## Timely
Timely system is the one that ships soon enough to meet your time-to-market need. You may have a great idea compared to current boring technology but if you take 3-5 years to ship it, the old one improves enough that its no longer worthwhile to switch. So being fast to market is very important goal. And this means making choices to give up features and dependability. This is a tradeoff.

- If you keep your solution *simple*, you increase your odds of meeting *timely* goal.
- If design is extensible, you can add features later. However adding dependability is harder.
- Most often it is ok for system to fail to deliver expected or timely result. User's may notice that result they are seeing is incomplete or wrong, but this doesn't matter as long as it doesn't happen too often. Perhaps the biggest example of this is *the web*. It is successful because it doesn't have to work *always*. The model is that user will try again or come back tomorrow.


## Efficient
Efficiency is about doing things fast and cheaply. It is tricky to write an efficient program, so don't do it unless you really need the performance.

{% include tip.html content="The rule for optimization is - first design, then code, then measure and finally (if ever) optimize. In other words, don't optimize until you know you need to."  %}

*Premature Optimization* is a common trap many people fall into. Your goal should never be to create *most optimized system* (a universal goal). First make your code correct, understand the need, then optimize. It's often good idea to keep unoptimized code around as oracle to test the optimized code against.

{% include important.html content="The resources you are trying to use efficiently are <strong>computing</strong>, <strong>storage</strong> and <strong>communication</strong>. The dimensions are <strong>time</strong> and <strong>space</strong>. For <em>time</em> the parameters are <strong>bandwidth</strong> (or throughput) and <strong>latency</strong> (or response time). Latency is the time to do the work plus time spent waiting for the resource. For <em>space</em> the parameters are <strong>memory</strong> and <strong>bandwidth</strong>" %}

To evaluate a design idea -
- Work out *roughly* how much latency, bandwidth and storage it consumes to deliver performance you need.
- Make an optimistic assumption if the resources can be afforded after potential optimization.

If not, the idea not good enough. But if it can then perform more detailed analysis of possible *bottleneck*s and find out how sensitive *cost* is to the parameters of the platform and workload. The *cost* here does not refer to monetary price, but to effort, complexity, resource utilization, etc invested in order to achieve the goal.

When performance of module is bad or unpredictable, you have incurred a *performance debt*. The debt can be
- Unknown: when it hasn't been measured.
- Bad: when it is worse than what is needed.
- Fragile: its sufficient now but you don't have any process to keep it that way.

### Concurrency
This is one way to reduce *latency*. The other is *fast path*. The requirement to create concurrent program is to divide the work in independent parts. Using concurrency we trade more resources (bandwidth) for less latency. There are two main problems with concurrency-
- It's hard to reason and debug concurrent computation that make arbitrary code change.
- To run fast, data must be either immutable or local.

**Sharding** aka partitioning is one of the easiest way to achieve concurrency. Break the state into *n* pieces (shards) that change *independently* and process each shard in parallel. Often there is a *combining function* for results from several shard. Shards can either be flat by hashing the key or hierarchial if there is natural groupings or subsets of keys such as DNS names. Hierarchy is good for change notifications (notify all subset of keys) but not good for load balancing since there may be hot spots on the hierarchy.

In other words there are 2 ways to bring independent shards together:
- Combining Function that combines the independent outputs or synchronizes state.
- Naming the shards and indexing them or by naming as a hierarchy. If the shards already exist, put them into a single name space by making a new root with all of them as children. Example - *mounting* in file system, domain names, etc.

**Streaming** is another kind of concurrency. Divide the work for a single item in 'k' sequential steps, put one step on each processor and pass the items along the chain. This generalizes to *dataflow* where the work flows through a directed acyclic graph (DAG). The number of distinct processing steps defines the limit of concurrency.

Map-Reduce operations are great example that combine both sharding and streaming. The combining phase of map-reduce illustrates that concurrency requires communication which is becomes the bottleneck.

### Fast path and bottlenecks
Fast path - do common case fast and leave the rare cases to be slow. It may be difficult to identify fast path if the code has lot of rare cases. In this case profile the code to identify fast paths and restructure the code to make it obvious and easy to maintain. The ties down well with identifying *key* modules. Segregate the fast path from rare cases and isolate it from rest of the code. This will make it easier to optimize, test and maintain. The fast path should be the normal case for the application. Handle the worst case separately because requirements for the two are different.

*Bottlenecks* are opposite of fast path. It is the part of the system that consumes most resource (time). The key for optimizing is to look for bottlenecks first. Most of the time optimizing anything else wastes time and adds complexity. Once bottlenecks are identified, design the code to use it as little as possible, measure and control how it's used. Rest of the code becomes your fast path where most of the traffic flows through.


### Locality
Communication is expensive. So keep the data close to the computation. A cache lets you trade locality and bandwidth for latency. Less code working on less data closer in space and time.
- Keep the parts that run *concurrently* as independent as possible to minimize communication.
- Make the data smaller so there is *less* to communicate and easier to make it local. For example instead of working on full dataset, work on *summary* of the dataset. Or rearrange the dataset such that what is accessed a lot is small and compressed.

Another way is to process data in *stream*. Instead of pulling all the dataset at once, divide data into small parts and stream it to be processed. Identify data that is accessed frequently and cache it.

If moving data to computation has high cost, doing reverse can be a good idea. Database do the same by processing query or stored procedure closer to data.


### ABC's of Efficiency
- **Algorithms**: Its usually best to stick with simple algorithms: like hash table for looking up key, B-tree for finding all keys in range, etc. If the problem you have is hard, look for a widely-used library. Understand the asymptotic complexity of the algorithm. Remember - *fancy algorithms are slow when N is small, and N is usually small - Rob Pike*.
- **Approximate**: If finding a *good enough* approximation is fine, then use it. Often you can approximate the program's behavior rather than its data. For example *Eventual Consistency* lets application work on stale data. A *hint* is information that bypasses an expensive computation if it's correct and its cheap to check that its correct and there is a (expensive) *backup* path that will work if its wrong. An example is routing hints tells how to forward a packet. The backup is rerouting.
- **Batch**: When the overhead of processing a list of items is lower than sum of overhead of processing each item, batching items will make things faster. Batching trades off latency (for earlier elements in the batch) for increased bandwidth. *Index* is an example of batching where we pay big cost upfront so that queries later is faster. Another reason to batch could be to gather and defer the work until the machine is idle (buffering). Opposite of batching is **fragmentation**, breaking up big chunk of work into smaller pieces. This is good for load-balancing work and distributing work across multiple machines.
- **Cache**: Caching is to remember the result of function evaluation (*f(x)*), indexed by the function (*f*) and its arguments (*x*).  Most references will *hit* in the cache if there is enough *locality* and it's bigger than *working set* of frequently referenced location, otherwise cache will *thrash*. A cache *hit* is the fast path. Cache are of two types -
  - Historical caching: Saving result that was obtained because the program needed it. It is good idea to cache frequently accesses result to increase *locality*.
  - Predictive caching: Guessing what result will be needed in future and precomputing and saving the result. Materialized view in database is an example of this.
- **Concurrency**: We discussed concurrency above.


## Adaptable
Making system extensible to accommodate new workloads is a key goal of software engineering. Any system is bound to change and there can be various reasons for change -
- New business requirements: A successful business will change to adapt as per customer's need and the system needs to be able to adapt.
- Change in usage pattern: It is very likely the behavior of end user will change over time.
- Changes in external dependencies: Any external dependencies such as services, frameworks, libraries, even host platform will change. New interfaces, versions, deprecations, change in performance is bound to happen.
- Changes in scale: From 100 users to 100 million or from storing text to storing videos. The change can be temporary in form of burst load then the system needs to be **elastic** not just scalable.

The key to adapting to functional changes are -
- **Modularity**: The only known way to build a large system is to reinforce abstraction with **Divide and Conquer** i.e. break the system down to independent abstractions called modules. The interface of module serves two purposes -
  - It simplifies the client's life by hiding the complexity of module.
  - It decouples client from the module so both can evolve independently.
- **Extension points**: *Extensibility* is a special form of modularity. It is a way to add new functionality to the system. Follow *Open-Close* principle.
- **Isolate moving (frequently changing) part** of the system from rest of the system. This will *decouple* the volatile parts of application with rest of the system. An extra layer of abstraction or indirection over volatile parts is often a good idea. You trade a bit of performance and complexity for ease of maintenance and extensibility.

The key to adapting to scaling are -
- **Modularity**: Modularize algorithm so its easy to change to one that scales better.
- **Automation**: Automate everything, from infrastructure to deployment, from fault tolerance to operations.
- **Concurrency** by sharding. Different shards are independent if they don't share state (exception if state is immutable) or resource. All communication is asynchronous.


## Dependable
A system's dependability is measured in three dimensions -
- **Reliable**: Gives right answer in spite of partial failures and doesn't lose data
- **Available**: It delivers result even in case of partial failures
- **Secure**: Its reliable and available in spite of malicious actors.


### Redundancy
The idea of redundancy is to have no *single point of failure*. Finding all single points of failure is hard. No single point of failure means a *distributed system*, which is inherently concurrent and can absorb partial failures (some part can fail but whole system keeps working). But redundancy is the key to manage *reliability* and *availability*. Redundancy can be either in time or space.
- Redundancy in *time* is retry or redo: doing same thing again. The challenge here is to detect need for retry, recover from partial state changes, make original input available again and avoid confusion if more than one try succeeds.
- Redundancy in *space* is replication: doing same thing in several places. The challenge is to give all places same input and making computation deterministic so all outputs agrees.

But redundancy in itself is not sufficient, we also need *repair*. This is crucial if the redundant copies fail and system is no longer fault tolerant. Repair is also important if the retry cost is significantly higher than single try, so as to avoid paying this extra cost over long period of time.


### Retry
- If the failure of a function is detectable, and after it fails there is good chance it will succeed the second time, then *retry* is the redundancy that will work.
- Retry is form of *slow path*. First try is the fast path of the system.
- If the retry that succeeds yields the same state as single try, then this is *idempotence*.
- To make arbitrary actions such as state increment (x = x + 1) idempotent, make it *testable* by assigning the action a Unique ID, storing ID of completed action and discarding any redundant retries. Discarding duplicate message at receiver is also called *at-most-once* messaging.
- If message and IDs are persistent it's called a *message queue* with *exactly-once* processing.
- Use *exponential backoff* to avoid overloading system with retries.

### Replication
Replication is another form of redundancy by making copies of data or the actions that lead to data transformation (state changes). Two extremes of replication are -
- Simplest: Create several copies of data. The challenge here is that updating all copies is not atomic operation, so in case of failure its tricky to maintain data consistency.
- Powerful: A log that records sequence of operations that produced the current state. This is similar to event sourcing. With some sort of checkpoint, the current state can be reconstructed by redoing the operations.

#### Replicated State Machine
Replicated State Machine (RSM) is a system that has multiple copies of the same state machine. RSM is the strongest variation of the *powerful* extreme of replication discussed above. The replicas of the host run same code, start at same initial state and if same *sequence* of deterministic commands are provided, they will reach same state. In case of mismatch the replicas can vote if there are at least three copies running. Things to keep in mind -
- Commands must be *deterministic*.
- *Sequence* of commands are important. Each replica should see the same sequence. A distributed system consensus algorithm such as [Paxos](https://people.cs.rutgers.edu/~pxk/417/notes/paxos.html) or [Raft](https://raft.github.io/) can be used to achieve this.
- *Reads* must go through RSM as well. But since this is expensive. To avoid this cost, one replica can take a time-limited lock called *lease* on part of state that prevents anyone else to change the state. The drawback here is that the leaseholder can become a bottleneck.
- A common way to do replication using RSM is *primary-secondary*. One replica is primary, selected by RSM, and it leases the whole state so that it can do fast reads and batch writes. The secondaries replicates all the writes through RSM and maintain the latest state in case primary fails.
- A variation of the above is *chain replication*. Arrange set of replicas in a chain, read happens at tail and writes propagates down the chain starting at head, but acknowledged only by tail. This ensures that each replica has seen every write that it's successor has seen.


## Yummy
A system is much easier to sell if it's *yummy*, that is, if the customers are enthusiastic about it. If it's a customer product, being yummy certainly helps. For enterprise product, power takes on precedence.

Two important things makes up a good user interface (UI) -
- The *user model* of the system: user should be able to think what system is doing makes sense.
- *Completeness* and *coherence*: user should clearly see how to get their whole job done not just part of it.

It is good idea to separate the internal state of the system from details of the UI. Model View Controller (MVC) is a good pattern for separating the two. Another popular one is MVVM (Model View ViewModel).


# Techniques
## Approximate
There are two types of softwares - precise and approximate, with contrasting goal. This is an opposition. Precise software has a specification and the software must satisfy the specs. Some softwares needs to be precise, such as controlling rocket, nuclear engine, airplane, IP protocol etc. Approximate software whereas have loose spec. As long as it is "good enough" the system works. For example, retail shopping, social media, etc. Approximate softwares are neither better or worse than precise, they are different, designed to meet different goals. There is no benefit of designing a social media platform with same precision as rocket engine controller. The user of social media don't need this precision. However if system is wrongly classified as approximate, the customer won't be satisfied by it.

## Divide and Conquer
This is the most important idea for designing software. When the system gets too complicated for one person's head, divide and conquer is the only technique to maintain control. Break down the system into sub systems, break down the subsystems into modules. If the module is still too complex, break it down into sub modules where each sub module has clear defined responsibility, if it still doesn't help break it down into further abstractions. The name of the game is to break down complexity till it no longer feels complex. A spec of the module is called its interface. A module's boundary does not just decouple its code from the client, it can decouple the execution and resource consumption as well. Thinking of module as independent system makes it easy to reason about the cost of the system as whole.

A system usually has lots of modules. To make management of modules easier and to identify how a change in module will propagate across, group related modules in *layers*. A layer is single unit that a team can ship and client can understand. The layers are stacked on each other to form hierarchy. A lower layer is not allowed to call methods in a higher layer.

```
|------------------|
|     Clients      |
|------------------|
|Peers| YOU | Peers|
|------------------|
|       Host       |
|------------------|
```

Layers is good for decoupling, but it comes with cost for each level of abstraction. If the performance is key goal, then its prudent to measure it. There are two ways to reduce it: make it inter-layer communication cheaper or bypass some layers.

## Incremental
Take *baby steps* and *useful steps*. Incremental is another form of divide and conquer. Smaller steps is easier to understand, less disruptive and easier to get right. Focus on creating building blocks with good foundation.

# Process
Process is essential to deliver any sufficiently big product. A small system can be built by a single developer with entire architecture in his/her head. A bigger system however requires a team to work together to achieve the goals and the process lays down the framework on how to achieve teamwork. However no amount of process will help if the goals are badly conceived.

- **Architecture**: Design and document the the architecture of the system. Everyone in the team should have same understanding of the design and documentation helps in driving this. Any architecture decisions should be documented as [Architecture Decision Records](https://github.com/microsoft/code-with-engineering-playbook/blob/main/docs/design/design-reviews/decision-log/README.md)(ADR)
- **Automation**: Automate everything, from code analysis, to build, test, deploy.
- **Review**: Review both the design and the code. Often I see design decisions happen within subset of people (leads and architect) in isolation with the entire team. This leads to confusion, loss of information and lack of growth in the team. Even if design is done by single person, always [review design](https://github.com/microsoft/code-with-engineering-playbook/blob/main/docs/design/design-reviews/README.md) decisions with entire team. The team must be invested as much as the person who created the design.
- **Testing**: Unit test, component test, integration test, stress test, chaos test, end to end test, BCDR test. Test the system. Test the code. Test the architecture. Test the automation.


# Conclusion
The idea of the article is to make it a reference point when designing softwares. The goals section discussed a lot of possibilities and what should be the focus of a system and is quite dense with information. Even then this is in no way exhaustive discussion on the subject. Butler has gone even more in depth discussing each of these aspects and I strongly recommend reading his paper. I hope you enjoyed reading this. If you have any questions, please feel free to comment below.