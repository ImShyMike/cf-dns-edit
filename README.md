# cf-dns

Simple TUI to edit DNS records for cloudflare managed domains 

## Installation

Using pip:

```bash
pip install cf-dns-edit
```

Using uv:

```bash
uv tool install cf-dns-edit
```

## Usage

After installing, simply run

```bash
cf-dns-edit
```

## Setup

To get your API token, head over to [this page](https://dash.cloudflare.com/profile/api-tokens).

In "API Tokens" click "Create Token".

![alt text](images/image-3.png)

Scroll down and click "Create Custom Token".

![alt text](images/image-4.png)

Give it a name and then in "Permissions" add the following:

![alt text](images/image.png)

* Zone.DNS.Read
* Zone.DNS.Write
* Zone.Zone.Read

Scroll down to "Continue to summary" and click it:

![alt text](images/image-1.png)

Then click "Create Token":

![alt text](images/image-2.png)

Copy the token.

Launch the program and then just paste in your key!

## FAQ

### Q: I am unable to paste in my key!

A: Set an environment variable named `CLOUDFLARE_API_TOKEN` to your key and rerun it

> How to set the environment variable:
>
> * Windows: `set CLOUDFLARE_API_TOKEN=token`
> * Linux/MacOS: `export CLOUDFLARE_API_TOKEN=token`
