---
layout: post
title: Foundry Hosted Agents - Agent Identity, Security & Secrets
comments: true
categories: [Azure, AI, Foundry, Hosted Agents, Identity, Security, Secrets, Entra ID]
description: Understanding agent identity in Foundry Hosted Agents — how agents authenticate, access Azure resources via RBAC, and securely manage secrets using project connections.
image: images/previews/ai-icon.png
author: <a href='https://twitter.com/ankitbko', target='_blank'>Ankit Sinha</a>
---


In [Part 1]({{ site.baseurl }}/2026/05/hosted-agents-part-1/) we deployed an agent and in [Part 2]({{ site.baseurl }}/2026/05/hosted-agents-part-2/) we explored the sandbox — sessions, persistence, and isolation. But our agents so far have only done one thing: call a Foundry model. What if your agent needs to read files from Azure Storage, query a Cosmos DB database, or call a third-party API that requires an API key? How does authentication work when your code runs inside an isolated microvm managed by the platform?

The answer is **agent identity**. Every hosted agent gets its own identity in Microsoft Entra ID, and the platform handles the entire authentication chain for you. No hardcoded credentials, no manual token management, no certificate rotation. For external services that need API keys, Foundry provides **project connections** — a secure, first-class way to inject secrets into your agent at runtime.

This is Part 3 of the series. We'll cover how agent identity works, how to assign permissions to your agent, and how to securely manage secrets for third-party services.

> Hosted Agents and `azd` are in active development. Command surfaces are expected to evolve and new features will be added. If you see any discrepancies with the commands mentioned in this post, please comment below and I will update accordingly.

## Agent Identity — What Your Agent Runs As

Every Foundry project gets an **agent identity** — a service principal in Microsoft Entra ID, created automatically by the platform. This is what your agent code authenticates as at runtime. It's important to understand: this is **not** the project's managed identity — it's a separate, agent-specific identity purpose-built for your agent workloads.

There are two concepts to understand here:

- **Agent Identity Blueprint** — a governing template for a *class* of agents. Think of it as a lifecycle and management construct. It defines the shape of identities that agents in your project will use.
- **Agent Identity** — the actual service principal your agent code authenticates as at runtime. This is what gets RBAC role assignments and shows up in audit logs.

We are going to ignore the blueprint for now and focus on the agent identity itself, since that's what your code interacts with. Blueprints are for advanced use cases and as we build more features around it, we'll cover it in a future post.

### How Your Code Uses It

From your agent code's perspective, this is remarkably simple:

```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
```

That's it. `DefaultAzureCredential()` just works. The platform handles token delivery to your agent's sandbox — no configuration needed. The token identifies your agent (the service principal), not a human user. What your agent can actually access is controlled by RBAC role assignments on the target resources.

## Assigning Permissions to Your Agent

Now that you know your agent has an identity, you need to grant it access to the resources it needs. This is standard Azure RBAC — you assign roles on target resources to your agent's service principal.

### Finding Your Agent Identity

First, get the principal ID of your agent's identity:

```bash
AGENT_IDENTITY=$(az rest --method GET \
    --url "${BASE_URL}/agents/${AGENT_NAME}?api-version=v1" \
    --resource "https://ai.azure.com" \
    --query "instance_identity.principal_id" \
    --output tsv)

echo "Agent identity principal ID: ${AGENT_IDENTITY}"
```

1. We use `az rest` to call the Foundry API and retrieve the agent's metadata.
2. The `instance_identity.principal_id` field contains the Entra object ID of the agent's service principal.
3. This is the principal you'll use for all RBAC role assignments.

Or you can also use `azd ai agent show` to get the same information. The output includes `Instance Identity Principal ID` which is your agent identity.

```bash
azd ai agent show
```

### Assigning RBAC Roles

With the principal ID in hand, assign roles the same way you would for any Azure service principal:

```bash
az role assignment create \
    --assignee-object-id "$AGENT_IDENTITY" \
    --assignee-principal-type ServicePrincipal \
    --role "Storage Blob Data Reader" \
    --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>"
```

### What `azd` Does Automatically

When you deploy an agent with `azd deploy`, it automatically assigns the `Foundry User` role at the Foundry account scope — this is what lets your agent call Foundry models. For any other resources (storage, databases, etc.), you need to assign RBAC roles manually.

One thing to note: `ACRPull` (used to pull your container image) is assigned to the **project managed identity**, not your agent identity. Don't confuse the two — they serve different purposes.

## Using the Agent Identity in Code

Let's see this in practice. Say your agent needs to list containers in an Azure Storage account:

```python
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

credential = DefaultAzureCredential()
blob_client = BlobServiceClient(
    account_url="https://mystorageaccount.blob.core.windows.net",
    credential=credential,
)

for container in blob_client.list_containers():
    print(container.name)
```

1. `DefaultAzureCredential()` picks up the agent identity automatically — no client IDs, no secrets, no configuration.
2. `BlobServiceClient` uses that credential to authenticate against Azure Storage.
3. The call succeeds only if your agent identity has the appropriate RBAC role (e.g., `Storage Blob Data Reader`) on the storage account.
4. The same code works locally (using your developer credentials) and in the hosted sandbox (using the agent identity). No code changes needed for either environment.

This is the beauty of the model — identity-based access with zero secrets in your code.

## Secrets Management — Project Connections

Your agent might need to call a third-party API — a weather service, a payment gateway, a CRM — that requires an API key. Where do you put that key?

Don't put it as environment variables in `agent.yaml` nor in your source code. All of those are discoverable, unauditable, and a rotation nightmare.

Foundry projects have **connections** — a first-class concept for storing credentials securely. Connections are backed by Azure Key Vault behind the scenes, so you get enterprise-grade secret management without managing a Key Vault yourself. You can also bring your own key vault if you want.

The key idea is you **reference** connections in your `agent.yaml` using a template syntax, and the platform resolves them when the container starts. Your agent definition never contains the actual secret values — only template references.

### Connection Types

Two connection types are most relevant for secret injection:

**ApiKey connections** is for services that use API key authentication. Each ApiKey connection stores a `target` (endpoint URL) and a `key` (the secret).

**CustomKeys connections** is the flexible option. You define arbitrary key-value pairs, and for each key you choose whether it's a **secret** or **plain** (non-secret). Secret keys land in `credentials`; plain keys land in `metadata` visible in plain text. A single CustomKeys connection can hold any mix of both.

### The Template Syntax

The resolver supports three template paths, mapped to the three parts of a connection:

| Path | Template Syntax | What It Resolves To |
|------|----------------|---------------------|
| `credentials.<field>` | `${{connections.<name>.credentials.key}}` (ApiKey)<br>`${{connections.<name>.credentials.<key-name>}}` (CustomKeys secret) | The secret value from the connection's secret store |
| `target` | `${{connections.<name>.target}}` | The connection's endpoint URL |
| `metadata.<key>` | `${{connections.<name>.metadata.<key-name>}}` | A plain (non-secret) value from the connection's metadata |

### How It Works

The flow has three pieces — create the connection, reference it in your `agent.yaml`, and read it in code. Let's walk through it.

Say we want our agent to call two things: an external API that needs a key, and a database that needs a password and a (non-secret) region setting. That's two connections — an **ApiKey** connection for the external API, and a **CustomKeys** connection for the database config.

Until recently, you had to create connections through the Foundry portal or Bicep. The `azd ai agent connection` commands now give us a much faster path. Let's create both connections from the CLI:

```bash
# ApiKey connection — for the external API
azd ai agent connection create my-api \
    --kind cognitive-search \
    --target "https://api.example.com" \
    --auth-type api-key \
    --key "ab12-fake-test-key-value-xyz"

# CustomKeys connection — for the database config
azd ai agent connection create my-config \
    --kind remote-tool \
    --target "https://db.example.com" \
    --auth-type custom-keys \
    --custom-key "db-password=p@ssw0rd-test-value" \
    --metadata "region=westus2"
```

A couple of things worth pointing out:

1. The `--key` value on the ApiKey connection lands in the connection's secret store. It will be reachable later via `credentials.key`.
2. On the CustomKeys connection, `--custom-key` lands secret values in `credentials` (where `db-password` goes), while `--metadata` lands non-secret values in `metadata` (where `region` goes). Both flags are repeatable, so you can have any combination of secret and plain keys on a single connection.
3. `--kind` describes what the connection points at (a remote tool, a search index, etc.) — it doesn't change the template syntax. You reference connections by name and field path regardless of kind.

Let's verify the connections landed:

```bash
$ azd ai agent connection list
Name           Kind             Auth Type   Target
----           ----             ---------   ------
my-api         CognitiveSearch  ApiKey      https://api.example.com
my-config      RemoteTool       CustomKeys  https://db.example.com
```

With the connections in place, we reference them in `agent.yaml`:

```yaml
environment_variables:
  - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
    value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
  # ApiKey connection — secret credential + non-secret target
  - name: API_KEY
    value: ${{connections.my-api.credentials.key}}
  - name: API_ENDPOINT
    value: ${{connections.my-api.target}}
  # CustomKeys connection — secret key + plain metadata key
  - name: DB_PASSWORD
    value: ${{connections.my-config.credentials.db-password}}
  - name: REGION
    value: ${{connections.my-config.metadata.region}}
```

Each line maps cleanly to one part of one connection:

1. `${{connections.my-api.credentials.key}}` — resolves the API key from the ApiKey connection's secret store.
2. `${{connections.my-api.target}}` — resolves the endpoint URL (not a secret, but kept portable via the template).
3. `${{connections.my-config.credentials.db-password}}` — resolves a secret custom key from a CustomKeys connection.
4. `${{connections.my-config.metadata.region}}` — resolves a plain (non-secret) custom key from the same connection.

When the container starts, the platform reads each named connection, resolves each placeholder, and injects the resulting values as environment variables. Your agent code never sees the template syntax — only the resolved values:

```python
import os

api_key = os.environ["API_KEY"]
api_endpoint = os.environ["API_ENDPOINT"]
db_password = os.environ["DB_PASSWORD"]
region = os.environ["REGION"]
```

### Rotating Secrets

When a secret needs to change — and they always do — you don't redeploy your agent. You update the connection and the next session picks up the new value:

```bash
azd ai agent connection update my-api --key "new-rotated-key-value"
```

That's the whole rotation story. The connection is the single source of truth for the secret. No image rebuilds, no environment variable churn, no restarting the agent. Just update the connection and move on.

`azd ai agent connection` also has `show` for inspecting a single connection's details and `delete` for cleanup when you're done.

### A Few Things Worth Remembering

- **Secrets are resolved at container start.** Every new session picks up the latest values, which is what makes rotation seamless.
- **Template syntax is validated at agent creation.** Typos in connection names or field paths fail fast, not at runtime.
- **Plain environment variables still work.** Templates are opt-in. You can mix `${VAR}` (azd-resolved) and `${{connections...}}` (platform-resolved) in the same `agent.yaml`.
- **Connection values are never stored in the agent definition.** Only the template reference is persisted. The actual secret lives in the connection (backed by Key Vault).
- **CustomKeys can mix secret and non-secret keys.** Secret keys go to `credentials`, non-secret keys go to `metadata`. Both are reachable via templates from the same connection.

For more details on creating connections, see [Add Connections in Foundry](https://learn.microsoft.com/en-us/azure/foundry/how-to/connections-add?tabs=foundry-portal).

## Putting It Together

Here's a complete `agent.yaml` combining both patterns — agent identity for Azure resources and project connections for external secrets:

```yaml
kind: hosted
name: my-secure-agent
protocols:
  - protocol: responses
    version: 1.0.0
resources:
  cpu: "0.25"
  memory: 0.5Gi
environment_variables:
  - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
    value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
  - name: API_KEY
    value: ${{connections.my-api.credentials.key}}
  - name: API_ENDPOINT
    value: ${{connections.my-api.target}}
```

And the corresponding code:

```python
import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import requests

# Azure resources → agent identity + RBAC (no secrets)
credential = DefaultAzureCredential()
blob_client = BlobServiceClient(
    account_url="https://mystorageaccount.blob.core.windows.net",
    credential=credential,
)

# External services → project connections (secrets injected as env vars)
api_key = os.environ["API_KEY"]
api_endpoint = os.environ["API_ENDPOINT"]
response = requests.get(
    f"{api_endpoint}/data",
    headers={"Authorization": f"Bearer {api_key}"},
)
```

Notice the two distinct patterns:

1. **Azure resources** → `DefaultAzureCredential()` + RBAC. No secrets anywhere. The platform delivers tokens automatically, and RBAC controls access.
2. **External services** → Project connections with `${{connections...}}` template injection. Secrets live in Key Vault (via connections), get resolved at container start, and arrive as plain environment variables. Your code and container image never contain the actual secret.

## Security Best Practices

- **Never put secrets in images or plain environment variables** — use project connections with `${{connections...}}` templates.
- **Use `DefaultAzureCredential` for Azure resources** — RBAC-based access is always better than connection strings or shared keys.
- **Assign least-privilege roles** — give your agent only the permissions it needs, at the narrowest scope possible.
- **Rotate secrets by updating connections** — new sessions pick up changes automatically. No redeployment needed.

## Conclusion

In this post we covered the two pillars of agent security in Foundry Hosted Agents:

- **Agent identity** is a service principal in Entra ID, managed entirely by the platform. `DefaultAzureCredential()` just works — the platform handles token delivery to your sandbox.
- **Azure resources** are accessed via RBAC roles assigned to the agent identity. No secrets needed.
- **External secrets** are managed through project connections with `${{connections...}}` templates. Secrets are resolved at session creation and injected as environment variables.

In the next post, we'll explore tool integration — how to give your agent the ability to execute code, search the web, and interact with external systems using Foundry's built-in and custom tool framework.

## References

1. [Agent Identity Concepts](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity)
2. [Add Connections in Foundry](https://learn.microsoft.com/en-us/azure/foundry/how-to/connections-add?tabs=foundry-portal)
3. [Manage Hosted Agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-agent)
4. [Azure RBAC in Foundry](https://learn.microsoft.com/en-us/azure/foundry/concepts/rbac-foundry)
5. [Part 1 — What, Why, Protocols & Your First Deployment]({{ site.baseurl }}/2026/05/hosted-agents-part-1/)
6. [Part 2 — Sessions, State & the Sandbox]({{ site.baseurl }}/2026/05/hosted-agents-part-2/)
