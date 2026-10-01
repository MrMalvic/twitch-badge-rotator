# twitch-badge-rotator

Rotates your Twitch global chat badge every time you send a message. If you've collected a pile of global badges and can't pick one, this cycles through all of them.

> [!WARNING]
> **Use at your own risk.** This talks to Twitch's private GraphQL API with your account's session token. That API is undocumented and not meant for third-party use, so this likely goes against Twitch's [Terms of Service](https://www.twitch.tv/p/legal/terms-of-service/). Twitch could break it at any time, and in the worst case act against your account. The author takes no responsibility for what happens to your account.

## Requirements

Python 3.8+. No dependencies.

## Setup

1. Log in on [twitch.tv](https://www.twitch.tv) in your browser.
2. Open DevTools (F12) → **Application** (Chrome/Edge) or **Storage** (Firefox) → **Cookies** → `https://www.twitch.tv`.
3. Copy the value of the `auth-token` cookie.
4. Put it in the `TWITCH_AUTH_TOKEN` environment variable:

   ```sh
   # macOS / Linux
   export TWITCH_AUTH_TOKEN=yourtoken

   # Windows PowerShell
   $env:TWITCH_AUTH_TOKEN="yourtoken"
   ```

**That token is a full login for your account.** Don't share it, don't commit it, and don't paste it into chat. Logging out of Twitch invalidates it.

## Usage

Pass the channels you chat in:

```sh
python badge_rotator.py xqc forsen
```

```
14:02:11 yourname: 243 badges, watching forsen, xqc
14:02:30 -> Gone Bananas Badge (182 ms)
14:02:41 -> 007 Gun Barrel (176 ms)
```

Badges are shuffled at startup. Use `--in-order` to cycle them alphabetically.

## How it works

The script joins the given channels as an anonymous chat viewer and watches for messages from your account. Each time you send one, it switches your global badge to the next one through the same GraphQL call the twitch.tv chat settings menu makes.

The switch happens *after* your message is sent, so the new badge shows on your next message.

## Troubleshooting

**`auth token rejected`**: the token expired or you logged out. Copy a fresh `auth-token` cookie.

**Nothing happens when you chat**: check the channel names are spelled as in the URL. The script connects to chat on port 443, so it should work on networks that block normal IRC ports.

**Badges switch slowly**: each switch is one round trip to Twitch. Running the script on a server in the US (close to Twitch's infrastructure) cuts that down a lot.

## License

[MIT](LICENSE)
