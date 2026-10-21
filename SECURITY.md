# Security Policy

## Scope

SegCraft is a local toolkit for one person on their own machine. The web app (`segcraft-web`)
listens on `127.0.0.1` by default (`SEGCRAFT_HOST` or `--host` changes that) and has no
authentication, user accounts, TLS, or rate limiting. Do not expose it to a network or the
internet, and do not put it behind a public proxy or tunnel.

The provided Docker Compose file publishes the port on `127.0.0.1` only. Inside the container the
server binds to `0.0.0.0`, so changing that host mapping changes the security boundary.

## What it processes

- **Uploaded videos and YouTube URLs.** An uploaded file is decoded on your machine by OpenCV and
  FFmpeg libraries. A YouTube URL is downloaded with `yt-dlp`. Treat video from untrusted sources
  like any other untrusted media file, and keep media libraries and `yt-dlp` up to date.
- **Model weights.** Presets download weights from their upstream hosts (torchvision, Hugging
  Face, segmentation-models-pytorch) the first time they are needed. SegCraft's own code makes no
  other network requests and does not upload your videos or results.
- **Configuration.** The merged YAML configuration can name any file path the process can read or
  write. Only load configuration files you trust.

Outputs (videos, summaries, checkpoints) are written under the configured output directory. They
can contain frames from your input video, so handle them like the input.

## Known limits

| Limit | Why it matters |
|---|---|
| No authentication on the web app | Anyone who can reach the port can upload media, start jobs, and download results. |
| Plain HTTP | Nothing on the connection is protected if it crosses a network. |
| No quotas | A caller can fill the disk or keep the GPU busy with large jobs. |
| Alpha software | The Python API and configuration schema can still change. |

## Reporting a vulnerability

Use the **Report a vulnerability** button on the repository's Security tab if it is shown, instead
of opening a public issue.

If that button is not available, open a minimal issue asking for a private contact method. Do not
put exploit details, private video, or local paths in the public issue.

## Disclaimer

SegCraft is provided without warranty under the [MIT License](LICENSE.md). It reads and writes
files and uses your GPU. Review the configuration you run and keep copies of anything important.
