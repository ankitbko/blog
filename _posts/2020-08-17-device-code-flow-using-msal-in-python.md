---
layout: post
title: Device Code Flow in Azure AD using Python's requests module and MSAL
comments: true
categories: [Python, azure, oauth, msal, requests, device code]
description: Sample on how to integrate requests with MSAL to achieve device code flow
---

> Repo: [https://github.com/ankitbko/python-requests-msal](https://github.com/ankitbko/python-requests-msal).

If you have created any Python application that required integration with Azure Active Directory you would have most likely used an excellent library from Azure AD team called [MSAL for Python](https://github.com/AzureAD/microsoft-authentication-library-for-python). However there is no easy way to integrate it with [requests](https://requests.readthedocs.io/en/master/) library which is a very popular HTTP library for Python.

I have written a sample application and reusable class to integrate Python requests library with MSAL to get AD token using [Device Code Flow](https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-device-code). Device Code Flow is typically used in a client side applications such as CLI. Therefore I have also implemented a *TokenCache* serialization/deserialization logic to persist the token in file system. This is similar to how [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/get-started-with-azure-cli) persists the token in `~/.azure` folder.

Feel free to copy and use `auth.py` and `rest_service.py` in your own project. The files depends upon following PyPI -
- [msal](https://pypi.org/project/msal/)
- [requests](https://pypi.org/project/requests/)

Initialize `DeviceCodeFlowTokenAuth` by passing `auth_config` object to it. `auth_config` must have
- client_id: Azure AD Application ID
- authority: Azure AD authority
- scope: Scope to send while requesting for token

Pass the initialized `DeviceCodeFlowTokenAuth` to `RestService`. `RestService` will use it to set Authorization token before sending request.

In addition to above, change *_DEFAULT_TOKEN_CACHE_DIR* in `DeviceCodeFlowTokenAuth` to any folder of your choosing where you would like the token to be chached. More details below.

## How does it work

`DeviceCodeFlowTokenAuth` accepts configuration which contains client_id, authority and scope to get access token. It first checks if a valid access token or refresh token is present in cache. The in-memory cache is serialized and stored as a file named *token* in a folder specified by `_DEFAULT_TOKEN_CACHE_DIR` variable in home folder (default *~/.myapp*).

The code will try to read the token from the folder above and populate its *TokenCache*. If valid access token exist it will use it. Otherwise if a valid refresh token exists it will use it to get a fresh access token and save it in the cache. If neither of them are valid it will initiate **device code flow** to fetch fresh tokens. The **device code flow** will print the code generated to console.
