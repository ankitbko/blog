---
layout: post
title: IdentityServer4 on Docker (ASP.NET Core 1.0)
comments: true
categories: [.net core, docker, IdentityServer]
description: A tutorial on how to host IdentityServer 4 on Docker targeting ASP.NET Core 1.0
---

In my previous article I showed how to run Identity Server 4 on Docker targeting ASP.NET Core RC1. In June .NET Core 1.0 and ASP.NET Core 1.0 was released which had some breaking changes. In this post I'll show what changes are required to run Identity Server 4 targeting ASP.NET Core 1.0 on Docker. I will take up from where we left off on my [previous post](https://ankitbko.github.io/2016/03/IdentityServer4-on-Docker/), so check that out before continuing.

### What changed in ASP.NET Core 1.0?
There are some breaking changes in ASP.NET Core 1.0. In this guide I only focus on changes needed to run IdSrv4 on docker. For complete detail on how to migrate an application to ASP.NET Core 1.0 from RC1, check out [official guide](https://docs.asp.net/en/latest/migration/rc1-to-rtm.html).

* The first major change you'll notice is that `dnx` is gone instead .NET Core 1.0 features new `dotnet` CLI. This change would affect how we build and publish our application and Dockerfile.
* Another change is that `dnx commands` are gone. This directly affects how we host our applications.
* There are also small changes in `project.json` and `Program.cs` which are not of great interest to us for this guide.
* Apart from these, Microsoft has also released a new docker base image for .NET Core 1.0 applications called `microsoft/dotnet:1.0.0-core`. We will use this to create our docker image.

I have changed my sample application to target ASP.NET Core 1.0 and made all the above changes to it. You can find the source code [here](https://github.com/ankitbko/IdentityServer4.DockerSample/tree/netcore1.0).

### Changes to the sample application
There are few changes I would like to point out before we continue.

* I have updated all the projects to target ASP.NET Core 1.0. All the projects are fork of IdentityServer4 repository with some minor changes.
* `dnx web` no longer exist. Instead we self-host the application using `dotnet` CLI. To configure port, we use environment variable ASPNETCORE_URLS present in Dockerfile.
* I have included Dockerfile in each of the project directory. The Dockerfile will automatically be copied when we publish our applications.
* There are changes in the ports in which applications are hosted -
	* Identity Server is hosted on port 1941
	* Javascript Client remains hosted on 7017
	* Sample Api is now hosted on 3721

### Let's get started

Again before continuing, I recommend you read though my [previous article](https://ankitbko.github.io/2016/03/IdentityServer4-on-Docker/). It would set up the context and fill in the gaps present in this post.
Done! Good!

The first two steps remain same, download and install Docker Toolbox and create a Docker VM. If you have Windows 10 Pro or Enterprise, you may also give try to new Docker for Windows which has recently moved out of beta.

#### Change URLs in the code

You will have to change the URLs in your code to point to the new VM URL in the following places:

* `IdSrvHost\Configuration\Clients.cs`: Change all the URL here to point to the VM. Leave the port as 7017.
* `SampleApi\Startup.cs`: Change the URL in `app.UseIdentityServerAuthentication`. Leave the port as 1941.
* `JavaScript Oidc\wwwroot\index.html`: There are two places in this file where URL needs to be changed. Leave the ports as it is in each place.

#### Publish the projects

Go to each project folder and run `dotnet publish` to publish in your desired folder.

{% highlight Powershell %}
dotnet publish -r debian.8-x64 -o <Path to output directory>
{% endhighlight %}

#### Changes to Dockerfile

I have already added Dockerfile to each of the project which should automatically get copied when you published each application in the previous step. Below I'll explain the new Dockerfile.

{% highlight shell %}
FROM microsoft/dotnet:1.0.0-core

# Copy the app
COPY . /app

# Set the Working Directory
WORKDIR /app

# Configure the listening port to 80
ENV ASPNETCORE_URLS http://*:80

# Start the app
ENTRYPOINT dotnet <DLLNAME>

{% endhighlight %}

* `FROM microsoft/dotnet:1.0.0-core`: We use the newer dotnet base image from Microsoft. Docker will run all the following commands on top of this base image.
* `COPY . /app`: Copy the current folder to `/app` folder in container.
* `WORKDIR /app`: Set the WORKDIR to /app folder. We now no longer have approot folder. Instead all the DLL lies here. This sets the working directory in container and executes remaining command from this directory.
* `ENV ASPNETCORE_URLS http://*:80`: This adds an environment variable `ASPNETCORE_URLS` which directs kestrel to listen to port 80.
* `ENTRYPOINT dotnet <DLLNAME>`: This instruction will host the application specified in <DLLNAME>. This is how we host application in `dotnet` CLI.

#### Build Image

This step remains as it was. Just run `docker build -t <tag> .` command in each output directory to create images.

#### Create the container

There are minor changes in the port mapping. Now kestrel in each container will listen on port 80, to which we bind host port as specified below

{% highlight Powershell %}
docker run -d -p 1941:80 --name idsrv-host idsrvhost
docker run -d -p 7017:80 --name client jsclient
docker run -d -p 3721:80 --name api sampleapi
{% endhighlight %}

* `docker run`: Creates and start a new container.
* `-d`: Run the container in background.
* `-p <host>:<container>`: Map the specified port of host to the port container.
* `--name <ContainerName>`: Creates the container with the specified name.
* The last parameter is the name of the image from which to create the container.

#### That's it.

These are all the changes required to run IdSrv 4 on docker targeting ASP.NET Core 1.0. Open the browser and go to the URL:PORT to view each of the site.

Leave a comment if you have any feedbacks.