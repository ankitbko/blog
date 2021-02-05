---
layout: post
title: Azure Devops Pull Request Extension for VS Code
comments: true
categories: [azdo, azure devops, pull request, code review, vscode]
description: Introducing Azure Devops Pull Request Extension for VS Code
image: images/previews/azdo-pr-vscode-extension.jpg
source_code: https://github.com/ankitbko/vscode-pull-request-azdo
---

> Marketplace: [https://marketplace.visualstudio.com/items?itemName=ankitbko.vscode-pull-request-azdo](https://marketplace.visualstudio.com/items?itemName=ankitbko.vscode-pull-request-azdo).

I have been fascinated with [Github Pull Request VSCode Extension](https://github.com/microsoft/vscode-pull-request-github). The extension bridges the gap that currently exists between development workflow and Pull Request review. You know how you have to switch from your development environment to some browser in order to review PR or address comments. This usually leads to loss of context and laziness when reviewing PRs. The extension solves it by integrating the PR review process within VS Code itself. Unfortunately my day work involves working in Azure Devops and not Github. So during this new year I decided to try porting this extension to support Azure Devops.

Now I have never developed VS Code extension before and didn't knew anything about what APIs are exposed by VS Code. To make matter worse the Github PR extension is quite huge and complicated. The Github PR extension is developed and maintained by VS Code team themselves so I was a little concerned if the team is using some internal vscode feature which is not publicly available. However over past 3 weeks I was able to port subset of features to support AzDO. Because of breadth of diversity that can exist in any repository or pull request it is impossible for me to test such different scenarios by myself. In hope of community will help me by trying out the extension in variety of projects I am releasing a preview version of extension today. Please give it a try and report any issues that you may encounter and I will fix it as soon as possible.

In this blog post I will describe some of these features and the current state of extension. Let me know in the comments if you would like a technical deep dive post on how these features are implemented.

> This extension is in very early stages of development. Raise an issue in the repository above if you face any problems.


# Features

To get started simply download the extension from marketplace linked at the top and follow the **Getting Started** section in the extension page. I will not repeat the steps here as those may change in future.

The extension will only start if you have a folder containing git repository open. To get started you will need to add 2 settings - `azdoPullRequests.orgUrl` and `azdoPullRequests.projectName`. The best places to add these is in workplace settings and commit them so others in your team won't have to set these. Currently the app requires a PAT token to authenticate which in future I will change to OAuth based authentication. The scopes required for PAT token is in extension's description.

If everything works the extension will create a new tab in the activity bar (the leftmost bar). The features that are available to you depends on which mode you are on - *browse* mode or *review* mode. The type of *mode* depends upon whether the branch which you are currently on has any pull requests *from* it or not. In case you don't have any pull requests you will be in *browse* mode. If you do have a PR from the current branch you will be in *review* mode. In *browse* mode you will be able to browse through the pull requests described in next section. In *review* mode you will get some additional functionality which is described later in the post.


## Browse Mode

This mode shows a *View active pull requests* `TreeView` on the sidebar. This particular `TreeView` is shown in both the modes. It allows you to view any open (active) pull requests. There are some built in filters like PR's raised by you or assigned to you. You can expand any of these nodes to fetch the PR's in it. Expanding the PR will show you which files have changed in the PRs. A small *diamond* icon will appear on the files which have comments on it. You can click on any of these files to view the diff and the comments on the file.

![PR diff view]({{ site.baseurl }}/assets/images/posts/azdo-pr-extn/pr_modified.jpg)

As you can see in image above the comments are grouped in *threads* similar to how it is in AzDO. You can reply to any existing thread or create a new thread by clicking on the white line that shows beside the line number. You will only be able to create a new thread on modified lines +/-3 three lines. Its always regarded as good practice to review and comment on lines which have changed in PR instead of any arbitrary location. Based on feedback I may change this logic or make it configurable.

Each thread has its status displayed on the title bar of the thread. At the extreme right of the thread's title bar, just beside the collapse button, there is another button that allows you to change the thread's status as shown in image below.

![PR thread status]({{ site.baseurl }}/assets/images/posts/azdo-pr-extn/thread_status.jpg)

All the threads and comments are also shown in a new "comments" window just beside the terminal (or output) window in the bottom. This window shows all the comments in that diff and allows you to quickly jump to a particular comment by clicking on it.

![Comment view]({{ site.baseurl }}/assets/images/posts/azdo-pr-extn/comment_tab.jpg)

In addition to all the files displayed for the PR you will also notice a node called **Description**. This is a separate React app that represents the *Overview* page in AzDO PR. This page allows you to view description of the PR, cast a vote (approve, reject, wait for author etc), view all the comments, perform Merge or Abandon action, etc. The page tries to mimic how PR looks in Azure DevOps. As of today certain functionality such as adding or removing reviewers or displaying work items does not work.

![Dashboard]({{ site.baseurl }}/assets/images/posts/azdo-pr-extn/pr_dashboard.jpg)

In the dashboard you will see a **Checkout** button that allows you to checkout the source branch of Pull Request. This is one way to get into *review* mode.


## Review Mode

In *review* mode a new `TreeView` is added that shows changes in the pull request. This view just shows the files changed in the checked out pull request. There is nothing special in this view as compared to the active pr view except that it shows changes only from one pull request. The advantage of the *review* mode is apparat when you switch back to Explorer in vscode. The purpose of the review mode is to be able to work on the pull request and review it in completeness. If you open any changed file normally through the Explorer tab you will get the same white line that denotes the modified lines along with any comments on the file. This enables you to work on addressing the comments right there in the file and then follow up with replying or changing status of comments without having to switch back to other window.

![Review mode]({{ site.baseurl }}/assets/images/posts/azdo-pr-extn/review_mode_explorer.jpg)


# Current State and Future of the Extension

Its important to state that I work at Microsoft. And just because I work at Microsoft and this extension is fork of Microsoft's Github PR extension does not mean this extension is an official release from Microsoft. This extension is a side project that I did as part of couple of weeks break during new year and is not by any means officially supported by Microsoft.

Having said that I quite enjoyed developing this and will continue improving it in future. This is a very early release. There are lots of known issues and tons of unknown ones. This is expected as I have not tested the extension in variety of scenarios. If there is enough interests in this extension I may even add more features such as native jupyter notebook diffs, integration with work items etc. Give the extension a try and let me know your thoughts in comment below.
