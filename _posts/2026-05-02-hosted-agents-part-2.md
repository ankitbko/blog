---
layout: post
title: Foundry Hosted Agents - Sessions, State & the Sandbox
comments: true
categories: [Azure, AI, Foundry, Hosted Agents, Sessions, State Management, Sandbox]
description: Deep dive into sessions, session lifecycle, $HOME persistence, and exploring the sandbox from inside using a VS Code tunnel.
image: images/previews/ai-icon.png
author: <a href='https://twitter.com/ankitbko', target='_blank'>Ankit Sinha</a>
source_code: https://github.com/ankitbko/hosted-agents-vscode-tunnel
---


In [Part 1]({{ site.baseurl }}/2026/05/hosted-agents-part-1/) we deployed a hello-world agent and had a conversation with it. It replied, remembered context across turns, and we moved on. But what actually happened behind the scenes? Where did the conversation history live? What if the agent needed to save a file — a report, a processed dataset, a set of notes — where would that go? And what happens when nobody talks to the agent for an hour?

State management is what separates a toy demo from a real agent. If your agent can't remember what happened five minutes ago, or loses a file it generated, it's useless in production. Foundry Hosted Agents have a rich state model built around **sessions** — isolated, persistent sandboxes that give each agent instance its own workspace.

This is Part 2 of my series on Foundry Hosted Agents. Let's dig into how state actually works.

> Hosted Agents and `azd` are in active development. Command surfaces are expected to evolve and new features will be added. If you see any discrepancies with the commands mentioned in this post, please comment below and I will update accordingly.

## What Is a Session?

A session is the core primitive of Foundry Hosted Agents' state model. Think of it as an **isolated compute sandbox + persistent filesystem**, bundled together and assigned to your agent.

Every session runs in its own **microvm** — completely isolated from other sessions. There's no cross-session access, no shared filesystem, no shared memory. Each session gets its own `$HOME` directory that persists across idle and resume cycles. This is your agent's durable workspace.

Sessions are identified by a `session_id` (called `agent_session_id` in the API) and are scoped to a specific agent. You can't share a session across agents. Sessions persist for up to **30 days** — after that, they're cleaned up automatically.

How do sessions get created? Two ways:

1. **Implicitly** — send a request to your agent without specifying a session ID, and the platform creates one for you automatically.
2. **Explicitly** — use the Session Management API to create a session before sending any requests *or* specify your own `agent_session_id` in the request.

Either way, once a session exists, subsequent requests with the same `session_id` land in the sandbox with the same `$HOME`.

## A Brief Note on Conversations

If you're using the Responses protocol, the platform also manages **conversations** — durable records of message history. Conversations are what `context.get_history()` reads from when your agent needs to recall previous turns. Every conversation is mapped to a session — the platform handles this mapping for you. The session provides compute and filesystem; the conversation provides message history.

For the Invocations protocol, there are no platform-managed conversations — you manage history yourself. We'll focus on sessions for the rest of this post since that's the core primitive that applies to both protocols.

## Session Lifecycle

Sessions go through a well-defined lifecycle. Understanding this is critical to building agents that behave correctly in production.

**Active** — Compute is running and your agent code is executing. This is the state your session is in while serving requests.

**Idle (~15 minutes)** — No requests have arrived for about 15 minutes. The platform deprovisions compute — the container process is killed, CPU and memory are reclaimed. But `$HOME` is persisted to durable storage before teardown. Any in-memory state is gone.

**Expired (30 days)** — The session has exceeded its TTL. Everything is cleaned up — compute, `$HOME`, all state is deleted.

> The 15-minute idle timeout is the key number to remember. Your container process restarts from scratch on resume — only `$HOME` survives. If you keep your working state in files under `$HOME`, the idle/resume cycle is completely transparent to your agent code. If you rely on in-memory variables or processes running in the background — those won't survive. We are actively working to enable sandbox to be running for more than 15 minutes to support long running workflows.

## Let's SSH Into the Sandbox — VS Code Tunnel Agent

The best way to understand sessions is to get inside one. I built a simple agent that starts a [VS Code tunnel](https://code.visualstudio.com/docs/remote/tunnels) from inside the sandbox — letting you connect to the running microvm and explore it like any remote machine.

The sample is available at [ankitbko/hosted-agents-vscode-tunnel](https://github.com/ankitbko/hosted-agents-vscode-tunnel). You can literally drop in the `vscode_tunnel.py` in any of your agents to get the same functionality.

### Deploy the Tunnel Agent

```bash
mkdir vscode-tunnel && cd vscode-tunnel

azd ai agent init -m https://github.com/ankitbko/hosted-agents-vscode-tunnel/blob/main/agent.manifest.yaml

azd provision  # if you don't have an existing Foundry project
azd deploy
```

### Start the Tunnel

Once deployed, invoke the agent to start a VS Code tunnel. You can specify provider as either `github` or `microsoft` — both work with the same authentication flow.

```bash
azd ai agent invoke '{"action": "start", "provider": "github"}'
```

The response will include a device code and a URL:

```json
{
  "status": "waiting_for_auth",
  "message": "To grant access to the server, please log into https://github.com/login/device and use code ABCD-1234",
  "auth_url": "https://github.com/login/device",
  "device_code": "ABCD-1234"
}
```

Open the device code URL in your browser and enter the user code to authenticate. Then get the status using

```bash
azd ai agent invoke '{"action": "status"}'
```

The response will have `tunnel_url`:

```json
{
  "status": "running",
  "message": "Tunnel is running.",
  "tunnel_url": "https://vscode.dev/tunnel/vscode-tunnel-agent/app/user_agent",
  "device_code_info": {
    "auth_url": "https://github.com/login/device",
    "device_code": "ABCD-1234",
    "message": "To grant access to the server, please log into https://github.com/login/device and use code ABCD-1234"
  }
}
```

Open that URL in your browser or connect via VS Code Remote and login with same provider and account you used to set up tunnel. You're now inside the sandbox microvm.

## Exploring the Sandbox

Once connected, open the VS Code terminal. Let's poke around. You have complete control over the sandbox environment. You can also run VS Code Copilot Chat in the terminal to ask questions about the environment and get code suggestions in real time.

### Check the OS

```bash
$ cat /etc/os-release
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"
```

### Check Resources

```bash
$ apt update && apt install procps -y
$ free -h
              total        used        free
Mem:          2.2Gi       434Mi       1.3Gi
```

### Check Environment Variables

```bash
$ env | grep FOUNDRY
FOUNDRY_PROJECT_ENDPOINT=https://myaccount.services.ai.azure.com/api/projects/myproject
FOUNDRY_AGENT_NAME=vscode-tunnel-agent
FOUNDRY_AGENT_VERSION=1
FOUNDRY_AGENT_SESSION_ID=abc123def456...
FOUNDRY_HOSTING_ENVIRONMENT=1
```

These are the `FOUNDRY_*` environment variables I mentioned in Part 1 — injected by the platform at runtime. Your agent automatically knows its name, version, session ID, and project endpoint without any configuration.

## Session State Persistence

### Explore the Filesystem

```bash
$ echo $HOME
/root

$ ls -la $HOME
total 30020
drwx------  5 root root     4096 May  6 18:00 .
drwxr-xr-x 20 root root     4096 May  6 17:56 ..
-rw-r--r--  1 root root      607 Mar  2 21:50 .bashrc
drwxr-xr-x  4 root root     4096 May  6 18:00 .cache
-rw-r--r--  1 root root      132 Mar  2 21:50 .profile
drwxr-xr-x  3 root root     4096 May  6 17:56 .vscode
drwx------  4 root root     4096 May  6 18:00 .vscode-server
-rw-r--r--  1 root root      169 Apr 22 02:01 .wget-hsts
-rwxr-xr-x  1 1000 1000 30704864 May  5 18:31 code
```

`$HOME` is the directory that the platform persists across idle/resume cycles. Let's create some files and prove they survive the idle/resume cycle.

### Step 1: Create Files in $HOME

```bash
$ echo "Hello from session $(printenv FOUNDRY_AGENT_SESSION_ID)" > $HOME/greeting.txt
$ echo '{"notes": ["review PR #42", "deploy v2 on Friday"]}' > $HOME/notes.json
$ ls -l $HOME
total 29996
-rwxr-xr-x 1 1000 1000 30704864 May  5 18:31 code
-rw-r--r-- 1 root root       70 May  6 18:15 greeting.txt
-rw-r--r-- 1 root root       52 May  6 18:15 notes.json
```

### Step 2: Wait for Idle Timeout

After ~15 minutes of no activity, the platform deprovisions compute. Your VS Code tunnel will disconnect — the container process was killed, along with everything running in memory.

### Step 3: Resume the Session

Any request to the same session triggers the platform to provision fresh compute and restores the state. Send a new request with the same session ID:

```bash
azd ai agent invoke '{"action": "status"}'
```

The platform spins up a new microvm, restores `$HOME` from durable storage, and routes the request. This time the status will show that the tunnel is not running in the new sandbox — because the tunnel process was an in-memory process that didn't survive the idle cycle. But the files we wrote to `$HOME` should still be there.


### Step 4: Verify the $HOME state

We can use `azd` to view the contents of `$HOME` without needing to reconnect the VS Code tunnel:

```bash
azd ai agent files list .
```

The command will return the list of files in `$HOME` as JSON. You should see `greeting.txt` and `notes.json` still there, with their contents intact. Let's download these files to verify their content:

```bash
azd ai agent files download greeting.txt
azd ai agent files download notes.json
```

The files survived. New compute, same `$HOME`. This is the persistence model.

### What Did NOT Survive

- Any in-memory state (variables, caches, running background processes).
- Any files outside `$HOME` (like `/tmp`).

This is the mental model: **`$HOME` is your agent's durable memory. Everything else is ephemeral.** Design your agent to write anything important to `$HOME`, and the idle/resume cycle becomes invisible.

Let's try to create a new session and look at the files there:

```bash
$ azd ai agent invoke '{"action": "status"}' --new-session
$ azd ai agent files list .
```

This will create a new session with a different `session_id`. If you check the files in this new session, you'll see that `$HOME` does not have the two files we created — proving that sessions are isolated sandboxes with their own persistent storage.

You can list all sessions using `azd ai agent sessions list`. Each session is associated with an agent version and has its own state.

## Isolation Keys

So far we've seen that each session is an isolated sandbox. But in a real application, you need to answer a harder question: **which caller is allowed to operate on which sessions?** That's what isolation keys solve.

### What Is an Isolation Key?

An isolation key is a scoping value attached to every session. Think of it as a partition tag — every session belongs to exactly one isolation key, and the platform ensures that a caller only sees and operates on sessions tagged with the key their request supplies.

The key applies consistently across all session-related endpoints:
- Session CRUD operations (`/sessions`)
- Responses (`/protocols/openai/responses`)
- Invocations (`/protocols/invocations`)
- File operations (`/sessions/{id}/files`)

> **Important:** The isolation key is a partitioning value, not an authentication mechanism. The Microsoft Entra token on the request authenticates the caller and authorizes the call against the project's role assignments. The isolation key only narrows *which sessions* that authenticated caller can act on.

### Two Authorization Schemes

How the isolation key gets set depends on the agent endpoint's **authorization scheme**, which you configure when setting up the agent:

**`Entra` (default)** — The platform derives the isolation key automatically from the caller's Microsoft Entra token. Each authenticated caller gets their own scope without any extra work. You don't need to send any header — the platform handles it.

This is the simplest option and works well when your callers authenticate directly with Entra and each caller should only see their own sessions.

**`Header`** — The platform reads the isolation key from the `x-ms-user-isolation-key` request header. You send a stable string per session owner (a user ID, tenant ID, or any logical boundary) on every request — invocations, session operations, and file operations. Your backend is responsible for choosing the right key for each call.

Until now we have been implicitly using `Entra` mode in our examples. To update the agent to use the `Header` isolation mode, you will need to update the agent using a PATCH operation:

```bash
az rest --method PATCH \
     --url "${BASE_URL}/agents/${AGENT_NAME}?api-version=v1" \
     --resource "https://ai.azure.com" \
     --headers "Content-Type=application/merge-patch+json" "Foundry-Features=AgentEndpoints=V1Preview" \
     --body '{
         "agent_endpoint": {
             "authorization_schemes": [
                 {
                     "type": "Entra",
                     "isolation_key_source": {
                         "kind": "Header"
                     }
                 }
             ]
         }
     }'
```
> Note: `azd` does not yet have first-class support for updating agent endpoint configuration, so we need to call the REST API directly here. We are actively working on adding this support to `azd` to make it easier to manage agent endpoints.

Now let's invoke the agent with isolation key `user-A`. The platform will create a session scoped to this key:

```bash
az rest --method POST \
    --url "${BASE_URL}/agents/${AGENT_NAME}/endpoint/protocols/openai/responses?api-version=v1" \
    --resource "https://ai.azure.com" \
    --headers "x-ms-user-isolation-key=user-A" "Foundry-Features=HostedAgents=V1Preview" \
    --body '{
        "input": "Hello from user A"
    }'
```

The response includes an `agent_session_id`. Let's verify we can see the session when listing with the same isolation key:

```bash
# List sessions with user-A's key — the session shows up
az rest --method GET \
    --url "${BASE_URL}/agents/${AGENT_NAME}/endpoint/sessions?api-version=v1" \
    --resource "https://ai.azure.com" \
    --headers "x-ms-user-isolation-key=user-A" "Foundry-Features=HostedAgents=V1Preview"
```

You'll see the session we just created. Now try listing with a **different** isolation key:

```bash
# List sessions with user-B's key — empty result
az rest --method GET \
    --url "${BASE_URL}/agents/${AGENT_NAME}/endpoint/sessions?api-version=v1" \
    --resource "https://ai.azure.com" \
    --headers "x-ms-user-isolation-key=user-B" "Foundry-Features=HostedAgents=V1Preview"
```

Empty. `user-B` can't see `user-A`'s session. Same authentication token, same agent, different isolation key — different view of the world.

Let's try to get the session details using `user-B`'s key:

```bash
# Try to get user-A's session using user-B's key — 403
az rest --method GET \
    --url "${BASE_URL}/agents/${AGENT_NAME}/endpoint/sessions/${SESSION_ID}?api-version=v1" \
    --resource "https://ai.azure.com" \
    --headers "x-ms-user-isolation-key=user-B" "Foundry-Features=HostedAgents=V1Preview"
```

You get a 403 Forbidden error because `user-B` is not authorized to access `user-A`'s session. 

```bash
Forbidden({
  "error": {
    "code": "session_not_accessible",
    "message": "Session is not accessible. [Request ID: 1244f2c67b0f87f5f8acf66e89def5b4]",
    "type": "invalid_request_error",
    "details": [],
    "additionalInfo": {
      "request_id": "1244f2c67b0f87f5f8acf66e89def5b4"
    }
  }
})
```

### When to Use Which Scheme

**Use `Entra` (default) when:**
- Your end-users call the agent directly with their own Entra identity (e.g., a web app where each user signs in with Microsoft Entra)
- Each user already has an `Azure AI User` role assignment on the Foundry project
- You want zero-config session scoping — the platform handles everything

**Use `Header` when:**
- A backend service calls the agent on behalf of multiple end-users using a single service principal
- Your users don't have direct Entra identities on the Foundry project (e.g., they authenticate against your app, not against Azure)
- You need to scope sessions by something other than the caller's identity — a tenant ID, a team ID, or any application-level grouping

This gives you full control over the partitioning, but your backend is responsible for sending the right `x-ms-user-isolation-key` on every request.

### Key Behaviors to Remember

- The isolation key is **immutable** — once set at session creation, it can't be changed.
- The key is **write-once** — it's never returned in any response payload (Create, Get, List). You must track it yourself.
- **Delete requires the matching key** — when using Header mode, you must pass the same isolation key that was used at creation.
- **All session-scoped operations** use the same key — invocations, file uploads, session management.

## Conclusion

We covered a lot of ground in this post. Here's the recap:

- **Sessions** are isolated microvm sandboxes with persistent `$HOME` storage — one per agent instance, no cross-session access.
- The **lifecycle** is Active → Idle (15 min) → Resumed (state restored) → Expired (30 days). Only `$HOME` survives the idle/resume cycle.
- **Conversations** provide message history (Responses protocol only) and are mapped to sessions by the platform.
- **`$HOME` is your agent's durable memory** — design for resume-friendliness by writing working state to files.
- **Isolation keys** partition sessions by caller — use Entra mode for per-identity scoping, Header mode for backend services acting on behalf of end-users.
- The **file API** bridges the outside world and the agent's filesystem — upload inputs, download outputs, up to 50 MB.

In the next post, we'll explore agent identity, security, and how to inject secrets into your agent — because a production agent needs more than just a filesystem.

## References

1. [Hosted Agents Overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
2. [Manage Hosted Sessions](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-sessions)
3. [VS Code Tunnel Agent Sample](https://github.com/ankitbko/hosted-agents-vscode-tunnel)
4. [foundry-samples Repository](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents)
5. [Part 1 — What, Why, Protocols & Your First Deployment]({{ site.baseurl }}/2026/05/hosted-agents-part-1/)
