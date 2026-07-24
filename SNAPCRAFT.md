# Publishing hlsget in the Snap Store

This guide walks through the first release. You do not need to run an APT
repository or manage PGP keys yourself.

## Before you begin

You will need:

- an Ubuntu One / Snapcraft developer account;
- a GitHub repository containing this project;
- a Snap Store name that you have registered;
- a build tested with an HLS stream you are authorized to download.

If the account owner is between 13 and 18 years old, the Snap Store terms
require permission from a parent or legal guardian.

The package currently uses the name `hlsget`. If that name is unavailable,
choose a unique name and update `name` in `snap/snapcraft.yaml` before building.
Do not use another service's brand in the package name.

## 1. Put the project on GitHub

Create a repository, then push the project:

```bash
git init
git add .
git commit -m 'Prepare hlsget for the Snap Store'
git branch -M main
git remote add origin https://github.com/USERNAME/hlsget.git
git push -u origin main
```

After the repository exists, add these optional metadata fields to
`snap/snapcraft.yaml` with your real URL:

```yaml
website: https://github.com/USERNAME/hlsget
source-code: https://github.com/USERNAME/hlsget
issues: https://github.com/USERNAME/hlsget/issues
contact: https://github.com/USERNAME/hlsget/issues
```

Do not publish placeholder URLs.

## 2. Register the Snap name

Sign in at [dashboard.snapcraft.io](https://dashboard.snapcraft.io/) and request
the name you want to publish. A clear request description is:

> A strictly confined command-line utility for downloading direct HLS
> playlists that the user owns or is authorized to download. It does not
> extract links from websites, bypass DRM, or collect user data.

A new name request may be reviewed manually. The name in the Store and the
`name` field in `snap/snapcraft.yaml` must match.

## 3. Install the build tools

```bash
sudo snap install snapcraft --classic
sudo snap install lxd
sudo usermod -aG lxd "$USER"
newgrp lxd
lxd init --auto
```

Snapcraft uses LXD as a clean build environment. If LXD is already configured,
you do not need to initialize it again.

## 4. Build the Snap

Run this from the repository root:

```bash
snapcraft
```

A successful build creates a file similar to:

```text
hlsget_0.1.0_amd64.snap
```

The package includes Python, the Python dependencies, and FFmpeg. End users do
not need to install them separately.

## 5. Test the local package

A local Snap has not been signed by the Store, so install it with `--dangerous`:

```bash
sudo snap install --dangerous ./hlsget_0.1.0_amd64.snap
hlsget --version
hlsget --help
```

Run a legal test download into your home directory:

```bash
hlsget 'TEST_M3U8_URL' -o "$HOME/Downloads/hlsget-test.mp4"
```

Check the resulting media:

```bash
ffprobe -v error \
  -show_entries stream=codec_type,codec_name \
  -show_entries format=duration,size \
  "$HOME/Downloads/hlsget-test.mp4"
```

Also verify:

- best and explicit quality selection;
- interruption with `Ctrl+C` followed by resume;
- useful errors for 401, 403, 404, and 429 responses;
- output in `~/Downloads`;
- no access outside the permissions declared by the Snap;
- no secrets printed in logs.

Inspect the connected interfaces:

```bash
snap connections hlsget
```

The application should only need `network` and `home`.

Remove the local build when testing is complete:

```bash
sudo snap remove hlsget
```

## 6. Run the automated review tools

```bash
sudo snap install review-tools
snap-review ./hlsget_0.1.0_amd64.snap
```

Fix errors before uploading. Review warnings should also be understood rather
than ignored blindly.

## 7. Publish to the edge channel first

Authenticate the Snapcraft CLI:

```bash
snapcraft login
```

Upload the tested package to `edge`:

```bash
snapcraft upload --release=edge ./hlsget_0.1.0_amd64.snap
```

Test the Store build on another machine:

```bash
sudo snap install hlsget --edge
hlsget --version
```

If you registered a different package name, use that name in these commands.

## 8. Complete the Store listing

In the Snapcraft dashboard, provide:

- a short, factual summary;
- the description from `snap/snapcraft.yaml`;
- the MIT license;
- the GitHub, Issues, and contact links;
- the Utilities category;
- a simple icon;
- optionally, a terminal screenshot using a public test stream;
- a link to `PRIVACY.md`.

Do not use a third-party streaming service's logo, screenshots, or name without
permission. Do not use copyrighted films as Store screenshots or test examples.
Do not describe the application as a way to bypass access controls.

## 9. Release to stable

After the edge build has passed your tests, promote that revision to `stable`
from the Snapcraft dashboard. You can also upload the same verified build
straight to stable:

```bash
snapcraft upload --release=stable ./hlsget_0.1.0_amd64.snap
```

Users can then install it with:

```bash
sudo snap install hlsget
```

Snap will deliver future stable updates automatically.

## Releasing the next version

For every release:

1. update `__version__` in `src/hlsget/__init__.py`;
2. update `version` in `pyproject.toml` and `snap/snapcraft.yaml`;
3. run the tests and build a local Snap;
4. publish to `edge`;
5. test the Store build on a second machine;
6. promote the tested revision to `stable`.

Build ARM64 separately and test it on ARM hardware before advertising support.

## Why the package uses strict confinement

The application only needs two standard interfaces:

- `network` to download playlists, media segments, and ordinary AES-128 keys;
- `home` to save the resulting video in a normal home-directory folder.

FFmpeg is bundled inside the Snap, so the application does not need access to
the host's `/usr/bin/ffmpeg`. Strict confinement avoids an unnecessary classic
confinement review and keeps the installation command simple.
