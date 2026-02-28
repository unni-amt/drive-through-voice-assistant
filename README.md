# drive-through-voice-assistant

Quick instructions to set up and run the project locally.

Prerequisites
- Python 3.10+ (or the version declared in pyproject.toml)

### Setup

Refer this [link](https://docs.astral.sh/uv/getting-started/installation/) for installing uv.

Installing requirements,

```bash
uv sync
uv run python src/agent.py download-files

```

Sign up for [LiveKit Cloud](https://cloud.livekit.io/) then set up the environment by copying `.env.example` to `.env.local` and filling in the required keys:

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

Run the application in console mode

```bash
uv run python src/agent.py console
```


