---
layout: post
title: Foundry Hosted Agents - Tools & Toolbox
comments: true
categories: [Azure, AI, Foundry, Hosted Agents, Tools, Toolbox, MCP, GitHub Copilot]
description: A walkthrough of giving hosted agents tools — from local @tool functions, through direct MCP, to Foundry Toolbox with versioning and multiple auth modes, ending with a working agent built on the GitHub Copilot SDK.
image: images/previews/ai-icon.png
source_code: https://github.com/ankitbko/hosted-agents-daily-standup
author: <a href='https://twitter.com/ankitbko', target='_blank'>Ankit Sinha</a>
---

In [Part 1]({{ site.baseurl }}/2026/05/hosted-agents-part-1/) we deployed a hosted agent. In [Part 2]({{ site.baseurl }}/2026/05/hosted-agents-part-2/) we explored sessions, state, and the sandbox. In [Part 3]({{ site.baseurl }}/2026/05/hosted-agents-part-3/) we gave the agent an identity and a safe way to handle secrets.

Now comes the part where the agent stops being a chatbot and starts doing work.

Tools are how agents get work done. A tool can be a local Python function, a remote MCP server, web search, file search, code interpreter, an OpenAPI endpoint, or even another agent. The idea is simple. The wiring is where things get interesting.

I'll start with a tiny `@tool` function, then move through direct MCP, Foundry Toolbox, versioning, MCP auth, approval gates, multi-tool composition, and finally a working Daily Standup Agent powered by the GitHub Copilot SDK.

> Hosted Agents, Foundry Toolbox, WorkIQ, and `azd` are in active development. Command surfaces and YAML shapes may evolve. If you see drift from the commands here, please comment and I will update the post.


## The Mental Model
There are two paths for giving a hosted agent tools:

| Path | Where tools live | Best for |
|------|------------------|----------|
| **In-code tools** | Inside your agent container | Quick prototypes, local business logic, one-off tools |
| **Foundry Toolbox** | In Foundry as a managed toolbox | Shared tools, enterprise governance, versioning, auth management |

Both are valid. I still use in-code tools when I'm building a small agent and the tool really belongs with that agent's code. But once the same tool is shared by more than one agent, or owned by a platform team, I want it outside the container.

That's what Foundry Toolbox gives us: define tools once, expose them through an MCP endpoint, and let agents consume that toolbox wherever they need it.

## In-Code Tools: The Fast Path
Most agent frameworks expose a way to declare a tool inline — Microsoft Agent Framework uses `@tool`, others have their own decorators or registration calls. The examples in this section use Agent Framework, but the shape is the same elsewhere.

Let's start with the smallest useful version: a Python function decorated as a tool.

```python
from random import randint
from typing import Annotated
from agent_framework import Agent, tool
from pydantic import Field

@tool(approval_mode="never_require")
def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    """Get the weather for a given location."""
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {location} is {conditions[randint(0, 3)]} with a high of {randint(10, 30)}°C."

agent = Agent(
    client=client,
    instructions="You are a friendly assistant. Keep your answers brief.",
    tools=[get_weather],
    default_options={"store": False},
)
```

1. The `@tool` decorator turns the Python function into a model-callable tool.
2. The function name becomes the tool name.
3. The docstring becomes the natural-language description.
4. Type hints and `Field(...)` descriptions become the input schema.
5. `approval_mode="never_require"` tells the runtime this tool can run without a human approval step.

This works well for domain logic that belongs next to the agent: pricing calculation, internal data normalization, template rendering, policy checks, or a wrapper around a private library already in your container.

### Direct MCP From Code
The next step is direct MCP. Instead of writing a function, the agent connects to an MCP server and imports whatever tools that server exposes. In Agent Framework, `FoundryChatClient` has a `get_mcp_tool` helper that wraps a remote MCP server as a tool you can hand to an `Agent`:
```python
from agent_framework.foundry import FoundryChatClient

client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=DefaultAzureCredential(),
)

github_pat = os.environ["GITHUB_PAT"]
tools = [
    client.get_mcp_tool(
        name="GitHub",
        url="https://api.githubcopilot.com/mcp/",
        headers={"Authorization": f"Bearer {github_pat}"},
        approval_mode="never_require",
    )
]
```

1. The hosted agent owns the MCP URL.
2. The hosted agent owns the headers.
3. The hosted agent decides whether the tool requires approval.
4. The tool list is fixed at deploy time.

That is fine for prototypes. It gets painful when several agents need the same GitHub, WorkIQ, Salesforce, or internal MCP server.
### Why In-Code Stops Scaling
Here's the thing — tools are rarely owned by one agent forever.

If every agent wires tools directly, credentials get copied around, tool changes require redeploys, and nobody has a single inventory. Moving a tool definition from dev to prod also becomes a per-agent exercise.

Once you have more than one agent or team, the tools should live somewhere else.

That somewhere else is Foundry Toolbox.

{% raw %}
## Foundry Toolbox
A **Foundry Toolbox** is a tool registry in your Foundry project. You define a set of tools, Foundry exposes them through an MCP endpoint, and hosted agents consume that endpoint.

| Concern | In-code tools | Foundry Toolbox |
|---------|---------------|-----------------|
| Tool definition | Agent code | Foundry resource |
| Tool endpoint | Inside container | Toolbox MCP endpoint |
| Credentials | Agent env vars / code | Project connections |
| Changes | Redeploy agent | Create/promote toolbox version |
| Reuse | Copy code/config | Multiple agents consume same endpoint |

At runtime, the toolbox still looks like MCP. Your agent connects to a toolbox MCP endpoint, calls `tools/list`, and later calls `tools/call`. The toolbox owns the backend catalog and auth configuration.
### Toolbox Versioning
Toolboxes are versioned. Each version snapshots the toolset. The first version becomes the default; later versions can be promoted explicitly.

| Role | Endpoint | Use for |
|------|----------|---------|
| **Consumer endpoint** | `{project}/toolboxes/{name}/mcp?api-version=v1` | Production agents; follows the toolbox default version |
| **Version endpoint** | `{project}/toolboxes/{name}/versions/{version}/mcp?api-version=v1` | Validate a specific version before promotion |

Every toolbox MCP request also needs this preview header:
```http
Foundry-Features: Toolboxes=V1Preview
```
### Creating A Toolbox With `azd`
Declare the toolbox and its connections in `agent.manifest.yaml` under `resources:`, then deploy with `azd ai agent init` followed by `azd provision`. `azd` provisions the connections, creates the toolbox version, and binds it to the agent from the same manifest.
```yaml
resources:
  - kind: connection
    name: github-mcp-conn
    category: RemoteTool
    authType: CustomKeys
    target: https://api.githubcopilot.com/mcp
    credentials:
      type: CustomKeys
      keys:
        Authorization: "Bearer {{ github_pat }}"
  - kind: toolbox
    name: agent-tools
    tools:
      - type: web_search
      - type: mcp
        server_label: github
        server_url: https://api.githubcopilot.com/mcp
        project_connection_id: github-mcp-conn
```

A few things to know:

- Each tool entry in `tools:` becomes a separately addressable tool source inside the toolbox.
- Connections referenced by `project_connection_id` must be declared in the same `resources:` block so `azd` can provision them in dependency order.
- Secrets like `{{ github_pat }}` come from manifest parameters and never land in the file you commit. `azd ai agent init` prompts you for them interactively or reads them from your `azd` environment.
- Each `azd provision` after a change to the toolbox config creates a new toolbox **version**. The versions need to be promoted explicitly to be `default`.

## The Tool Catalog
Toolbox supports a growing set of tool types. This is what `azd` can declare in a manifest today — see the [feature support matrix](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox?pivots=azd#feature-support) for the current list.

| Tool type | What it does |
|-----------|--------------|
| `mcp` | Proxy an MCP server (see the next section for auth modes) |
| `web_search` | Bing-grounded web search |
| `azure_ai_search` | Query an Azure AI Search index |
| `code_interpreter` | Sandboxed Python execution |
| `file_search` | Vector store retrieval |
| `openapi` | Call REST APIs from an OpenAPI spec |
| `a2a_preview` | Delegate to another agent |
| `fabric_iq` | Query Fabric data through Fabric IQ |
| `tool_search` | Search and discover other tools |
| `work_iq` | Access Work IQ knowledge |
| `browser_automation` | Drive a browser session |

The wiring pattern is the same across all of them. If a tool needs a credential, declare a project connection in the manifest first, then reference it by name from the toolbox tool entry. Tools without credentials — `web_search`, `code_interpreter`, `tool_search` — only need their `type`.

MCP is the broadest of these, and it has the most auth flexibility. The next section covers each MCP auth mode.

## MCP Authentication Modes

| Mode | authType | Identity represented downstream | Use when |
|------|----------|---------------------------------|----------|
| No Auth | none | Nobody | Public MCP server |
| API Key / CustomKeys | `ApiKey` / `CustomKeys` | Shared secret | PATs, API keys, static headers |
| OAuth Managed | `OAuth2` + `connectorName` | Consenting user | Managed OAuth app exists |
| OAuth Custom | `OAuth2` + URLs/scopes | Consenting user | You own the OAuth app registration |
| Agent Identity | `AgenticIdentity` | Agent service principal | MCP server trusts the agent identity |
| Project Managed Identity | `ManagedIdentity` | Project's MI | MCP server expects the project's MI rather than the per-agent identity |
| Entra Passthrough | `UserEntraToken` | Calling user | M365 / WorkIQ / user-delegated tools |

### Each Mode In Practice
Each mode below shows the same toolbox `mcp` tool wired with a different `authType`. The toolbox sits between the agent and the MCP server — the agent only sees the toolbox endpoint; the toolbox does the credential injection.

**No Auth — public MCP server.** No connection needed; the tool points straight at the server.
```yaml
- type: mcp
  server_label: public-docs
  server_url: "{{ mcp_endpoint }}"
```

**CustomKeys (API key or PAT) — static header injected by the toolbox.** Common for GitHub PATs and similar long-lived tokens. Store the **whole header value** (including `Bearer `), not just the token.
```yaml
- kind: connection
  name: github-mcp-conn
  category: RemoteTool
  authType: CustomKeys
  target: https://api.githubcopilot.com/mcp
  credentials:
    type: CustomKeys
    keys:
      Authorization: "Bearer {{ github_pat }}"
- type: mcp
  server_label: github
  server_url: https://api.githubcopilot.com/mcp
  project_connection_id: github-mcp-conn
```

**OAuth Managed** The first time a user invokes this tool, Foundry returns a consent link in the response (as an `oauth_consent_request` output item). Your app surfaces the link, the user signs in once, and from then on the user's token is reused. Add `offline_access` to scopes so the token auto-refreshes.
```yaml
- kind: connection
  name: github-oauth-conn
  category: RemoteTool
  authType: OAuth2
  target: https://api.githubcopilot.com/mcp
  connectorName: foundrygithubmcp
  credentials: { type: OAuth2, clientId: managed, clientSecret: managed }
```

**OAuth Custom — you own the OAuth app registration.** Same runtime flow as OAuth Managed, but you provide the client ID, secret, and OAuth URLs. Foundry returns a redirect URL after configuration that you add to your app registration.
```yaml
- kind: connection
  name: github-oauth-custom-conn
  category: RemoteTool
  authType: OAuth2
  target: https://api.githubcopilot.com/mcp
  credentials: { type: OAuth2, clientId: "{{ your_client_id }}", clientSecret: "{{ your_client_secret }}" }
  authorizationUrl: "https://github.com/login/oauth/authorize"
  tokenUrl: "https://github.com/login/oauth/access_token"
  refreshUrl: "https://github.com/login/oauth/access_token"
  scopes: [repo, read:user, offline_access]
```

**Agent Identity — the MCP server trusts the agent's managed identity.** No user context; the agent acts as itself. The MCP server (or the resource behind it) needs an RBAC assignment on the agent identity before this works.
```yaml
- kind: connection
  name: language-mcp-conn
  category: RemoteTool
  authType: AgenticIdentity
  audience: "{{ entra_audience }}"
  target: "{{ mcp_target_url }}"
```

**Entra Passthrough — the caller's user token is forwarded to the MCP server.** This is how Microsoft 365 MCP servers (Outlook Mail, Calendar, Teams, etc.) work. The `audience` is the **Agent 365 first-party app GUID** (`ea9ffc3e-8a23-4a7d-836d-234d7c7565c1`), not the server URL. Using the URL there will cause the toolbox to return zero tools.
```yaml
- kind: connection
  name: workiq-mail-conn
  category: RemoteTool
  authType: UserEntraToken
  audience: ea9ffc3e-8a23-4a7d-836d-234d7c7565c1
  target: https://agent365.svc.cloud.microsoft/agents/servers/mcp_MailTools
- type: mcp
  server_label: workiq-mail
  server_url: https://agent365.svc.cloud.microsoft/agents/servers/mcp_MailTools
  project_connection_id: workiq-mail-conn
```


### Picking A Mode
The first question is whether you need per-user identity:

- **Shared identity is fine** (every caller hits the MCP server as the same principal) — pick **No Auth** for public servers, **CustomKeys** for static keys, **Agent Identity** for first-party services that can trust the agent, or **Project Managed Identity** when the MCP server expects the project's identity rather than the per-agent one.
- **You need per-user identity** (consent, audit, or downstream permissions follow the actual user) — pick **OAuth Managed** if Foundry already has a connector for the service, **OAuth Custom** if you want your own app registration (control, branding, custom scopes), or **Entra Passthrough** for Microsoft 365 / WorkIQ tools.

When in doubt and the MCP server supports Entra, start with **Agent Identity**. It avoids secret management and rotation entirely.

## Consuming A Toolbox From A Hosted Agent
At runtime, a toolbox is just an MCP server from the agent's point of view. The agent needs the endpoint URL, a Foundry bearer token, the preview header, and an MCP client.
```python
def toolbox_url(project_endpoint: str, toolbox_name: str) -> str:
    return f"{project_endpoint.rstrip('/')}/toolboxes/{toolbox_name}/mcp?api-version=v1"

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
```

In Agent Framework, use `MCPStreamableHTTPTool`. Create an `httpx.AsyncClient` that injects a fresh Foundry bearer token and the `Foundry-Features: Toolboxes=V1Preview` header. Pass that client to `MCPStreamableHTTPTool(name="agent-tools", url=toolbox_endpoint, http_client=http_client)`, then give the tool object to the `Agent`.

1. `httpx.Auth` injects a fresh token on each request.
2. The toolbox preview header is attached to every MCP call.
3. `MCPStreamableHTTPTool` handles the MCP handshake and tool wrapping.
4. The agent receives the toolbox as its tool set.
### Standard `mcp.json` For Other Frameworks
Frameworks that already speak MCP — including the GitHub Copilot SDK — accept a standard `mcp.json` file:
```json
{
  "mcpServers": {
    "toolbox": {
      "type": "http",
      "url": "<toolbox-mcp-endpoint>",
      "headers": {
        "Authorization": "Bearer <fresh-mi-token>",
        "Foundry-Features": "Toolboxes=V1Preview"
      },
      "tools": ["*"]
    }
  }
}
```

Mint the bearer token from `DefaultAzureCredential` at session creation, substitute it into the headers, and hand the config to the SDK. The SDK handles the MCP handshake, discovery, and tool calls. The Daily Standup Agent below uses this pattern.


## Multi-Tool Composition
The real value of Toolbox shows up when you combine tools.
```yaml
- kind: toolbox
  name: agent-tools
  tools:
    - type: web_search
      name: public_web
    - type: code_interpreter
      name: python_sandbox
    - type: mcp
      server_label: github
      server_url: https://api.githubcopilot.com/mcp
      project_connection_id: github-mcp-conn
    - type: azure_ai_search
      name: product_docs
      index_name: "{{ ai_search_index_name }}"
      project_connection_id: aisearch-conn
```
The model chooses tools by name, description, and schema, so naming matters. `github` is better than `mcp1`. `product_docs` is better than `search`. If two tools do similar things, make the descriptions explicit: one reads internal docs, one searches the public web, one reads GitHub issues.


## Putting It Together: A Daily Standup Agent
Let's combine everything into a **Daily Standup Agent**. It pulls today's meetings, overnight email threads, and assigned GitHub work, then turns that into a standup brief.

The sample is here: [ankitbko/hosted-agents-daily-standup](https://github.com/ankitbko/hosted-agents-daily-standup).

It uses the GitHub Copilot SDK as the agent loop, the Invocations protocol with plain-text input, and Foundry Toolbox with three MCP tools. GitHub MCP uses CustomKeys auth. WorkIQ Mail and Calendar use Entra Passthrough. A small `SKILL.md` defines the brief format.

### The Manifest
Here's the full `agent.manifest.yaml` from the sample.
```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/microsoft/AgentSchema/refs/heads/main/schemas/v1.0/AgentManifest.yaml
name: daily-standup-agent
displayName: "Daily Standup Agent"
description: >
  A hosted agent that uses the GitHub Copilot SDK as its loop and connects
  to a Foundry Toolbox with three MCP tools — GitHub MCP, WorkIQ Mail, and
  WorkIQ Calendar — to generate a personalized standup brief from your M365
  and GitHub activity.
metadata:
  tags:
    - AI Agent Hosting
    - GitHub Copilot SDK
    - Foundry Toolbox
    - WorkIQ
    - Invocations Protocol
parameters:
  properties:
    - name: github_pat
      secret: true
      description: GitHub Personal Access Token (fine-grained github_pat_... preferred) with repo + read:user scopes
template:
  name: daily-standup-agent
  kind: hosted
  protocols:
    - protocol: invocations
      version: 1.0.0
  environment_variables:
    - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
      value: "{{AZURE_AI_MODEL_DEPLOYMENT_NAME}}"
    - name: TOOLBOX_NAME
      value: "daily-standup-tools"
resources:
  - kind: model
    id: gpt-5.4
    name: AZURE_AI_MODEL_DEPLOYMENT_NAME
  - kind: connection
    name: github-mcp-conn
    category: RemoteTool
    authType: CustomKeys
    target: https://api.githubcopilot.com/mcp
    credentials:
      type: CustomKeys
      keys:
        Authorization: "Bearer {{ github_pat }}"
  - kind: connection
    name: workiq-mail-conn
    category: RemoteTool
    authType: UserEntraToken
    audience: ea9ffc3e-8a23-4a7d-836d-234d7c7565c1
    target: https://agent365.svc.cloud.microsoft/agents/servers/mcp_MailTools
  - kind: connection
    name: workiq-calendar-conn
    category: RemoteTool
    authType: UserEntraToken
    audience: ea9ffc3e-8a23-4a7d-836d-234d7c7565c1
    target: https://agent365.svc.cloud.microsoft/agents/servers/mcp_CalendarTools
  - kind: toolbox
    name: daily-standup-tools
    tools:
      - type: mcp
        server_label: github
        server_url: https://api.githubcopilot.com/mcp
        project_connection_id: github-mcp-conn
      - type: mcp
        server_label: workiq-mail
        server_url: https://agent365.svc.cloud.microsoft/agents/servers/mcp_MailTools
        project_connection_id: workiq-mail-conn
      - type: mcp
        server_label: workiq-calendar
        server_url: https://agent365.svc.cloud.microsoft/agents/servers/mcp_CalendarTools
        project_connection_id: workiq-calendar-conn
```


### Wiring The Toolbox With `mcp.json`

The Copilot SDK speaks MCP natively. It already knows how to handshake with a remote MCP server, discover tools, and forward tool calls. Our job is to point it at the toolbox endpoint with a valid bearer token.

The simplest way to do that is the standard `mcp.json` file — the same shape every Copilot SDK consumer uses. We declare the toolbox as one MCP server with `${VAR}` placeholders that get substituted at startup.
```json
{
  "mcpServers": {
    "toolbox": {
      "type": "http",
      "url": "${TOOLBOX_ENDPOINT}",
      "headers": {
        "Authorization": "Bearer ${TOOLBOX_BEARER_TOKEN}",
        "Foundry-Features": "Toolboxes=V1Preview"
      },
      "tools": ["*"]
    }
  }
}
```

Two placeholders matter:

- `${TOOLBOX_ENDPOINT}` — the toolbox MCP URL, constructed at runtime from `FOUNDRY_PROJECT_ENDPOINT` + `TOOLBOX_NAME`.
- `${TOOLBOX_BEARER_TOKEN}` — a **fresh Entra token** minted at session creation via the agent's Managed Identity.

Substitution is a small helper:
```python
_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")

def _load_mcp_servers() -> dict:
    raw = _mcp_json_path.read_text(encoding="utf-8")
    substitutions = {
        "TOOLBOX_ENDPOINT": _toolbox_url(),
        "TOOLBOX_BEARER_TOKEN": _foundry_token(),
    }
    def repl(m: re.Match) -> str:
        key = m.group(1)
        return substitutions.get(key, os.environ.get(key, ""))
    return json.loads(_VAR_RE.sub(repl, raw)).get("mcpServers", {})
```

That is the whole integration. The toolbox namespaces tools as `<server_label>___<tool_name>` (e.g., `github___list_pull_requests`, `workiq-mail___GetMessage`), and the Copilot SDK accepts those names directly.

### Wiring The Copilot Session
With the toolbox declared in `mcp.json`, the session-creation code becomes pretty small:
```python
async def _ensure_session() -> None:
    global _client, _session, _session_id
    if _session is not None:
        return
    _session_id = os.environ.get("FOUNDRY_AGENT_SESSION_ID") or str(uuid.uuid4())

    mcp_servers = _load_mcp_servers()
    logger.info("Loaded %d MCP server(s) from mcp.json: %s",
                len(mcp_servers), list(mcp_servers))

    provider, model = _byok_provider()
    _client = CopilotClient(auto_start=False)
    await _client.start()

    common = dict(
        on_permission_request=PermissionHandler.approve_all,
        streaming=True,
        skill_directories=[_skills_dir],
        working_directory=os.environ.get("HOME", "/home"),
        provider=provider,
        model=model,
        mcp_servers=mcp_servers,
    )
    try:
        _session = await _client.resume_session(_session_id, **common)
    except Exception:
        _session = await _client.create_session(session_id=_session_id, **common)
```

### The Skill
The behavior lives in `skills/standup/SKILL.md`. A truncated view:
````markdown
---
name: standup
description: Generate a structured daily standup brief from the user's calendar, mail, and GitHub activity.
---
# Daily Standup Skill
You are an engineering assistant whose only job is to generate a concise daily
standup brief. You have three tool sources via the Foundry Toolbox:
- **WorkIQ Calendar** — today's meetings
- **WorkIQ Mail** — overnight unread / mentioned threads
- **GitHub MCP** — assigned PRs and issues

When the user asks for their standup brief, call each tool, then synthesize a
brief in the documented format. Be concise. Use 24-hour times. If a tool fails,
list it under Blockers and continue.
````
The full skill file with the output format and style rules lives in [the sample repo](https://github.com/ankitbko/hosted-agents-daily-standup/blob/main/skills/standup/SKILL.md). This is one reason I like using the Copilot SDK here: the skill file gives the agent a clear operating procedure without burying behavior in Python strings.

### Invoking It

```bash
azd ai agent invoke "Give me my standup brief"
```

Abbreviated streamed output:
```text
❯ azd ai agent invoke "Give me my standup brief"
data: {"type":"session.created","session_id":"standup-7f1c..."}
data: {"type":"tool.call.started","name":"outlook_calendar_get_events"}
data: {"type":"tool.call.completed","name":"outlook_calendar_get_events"}
data: {"type":"tool.call.started","name":"outlook_mail_search"}
data: {"type":"tool.call.completed","name":"outlook_mail_search"}
data: {"type":"tool.call.started","name":"github_search_issues"}
data: {"type":"tool.call.completed","name":"github_search_issues"}
data: {"type":"message.delta","text":"☀️  Daily Standup — Monday, May 24\n\n"}
event: done
data: {"invocation_id":"inv_...","session_id":"standup-7f1c..."}
```

And the brief follows the skill format:
```text
☀️  Daily Standup — Monday, May 24

🗓️  Today's Schedule
- 09:30  Hosted Agents sync  (30m, Priya)
- 13:00  Agent toolbox review  (60m, Foundry team)

📥  Overnight Threads (most relevant 3-5)
- Toolbox auth review — final question on WorkIQ audience  (Maya, 7h ago)
- Daily standup sample — deployment status and README update  (GitHub, 10h ago)

🔧  GitHub
- PRs awaiting your review: 2
  - #184  hosted-agents-daily-standup — Add retry around tools/list
  - #201  foundry-samples — Document UserEntraToken toolbox scenario
- PRs you authored (open): 1
- Issues assigned to you: 3
  - #87  hosted-agents-blog — Publish tools/toolbox post

⚠️  Blockers / Heads-up
- WorkIQ Mail returned one thread without sender metadata; included subject only.
```

For hosted agents that share tools, Toolbox is the right abstraction: the agent gets one tool surface, and the platform owns credential storage, policy, and discovery.
{% endraw %}

## Conclusion
Tools are what move an agent from a chat window to something useful. Foundry Toolbox is what keeps that surface manageable as more agents and more tools pile up — one MCP endpoint, one place to set auth, one config the agent loads. Once that piece clicks into place, the agent code shrinks back down to what it should be: the agent.

Next up — knowledge and memory. FoundryIQ, WorkIQ, and what it actually means for an agent to remember things worth remembering.
## References
1. [Part 1 — What, Why, Protocols & Your First Deployment]({{ site.baseurl }}/2026/05/hosted-agents-part-1/)
2. [Part 2 — Sessions, State & the Sandbox]({{ site.baseurl }}/2026/05/hosted-agents-part-2/)
3. [Part 3 — Agent Identity, Security & Secrets]({{ site.baseurl }}/2026/05/hosted-agents-part-3/)
4. [Foundry Toolbox documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox)
5. [Agent Framework hosted agent samples](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework)
6. [SUPPORTED_TOOLBOX_SCENARIOS.md](https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/hosted-agents/SUPPORTED_TOOLBOX_SCENARIOS.md)
7. [Daily Standup Agent sample](https://github.com/ankitbko/hosted-agents-daily-standup)
