# ARIA on Oracle Cloud Always Free (no third-party tunnels)

Self-host ARIA on a free Ampere ARM VM: 4 OCPUs + 24 GB RAM + 200 GB disk,
free forever. Everything runs on your box — Caddy login screen included,
no Cloudflare/Tailscale in the path.

**Honest expectations:** CPU-only 12B inference on 4 Ampere cores is roughly
10x slower than your M4 Mac (tens of seconds per answer). Your Mac stays the
fast daily driver; this box is the always-on copy.

## What I can't do for you

I can't click through Oracle's signup for you — it needs your account, your
phone number, and your SSH key. Steps 1–2 are manual; steps 3+ are scripted.

## 1. Create the free VM (Oracle console, ~15 min)

1. Sign up at Oracle Cloud, open **Instances → Create instance**.
2. Image: **Ubuntu 24.04**, shape series **Ampere**, shape
   **VM.Standard.A1.Flex** with **4 OCPUs / 24 GB RAM**, boot volume 100 GB.
   - If it says "out of capacity", retry later or another home region —
     Ampere free capacity comes and goes.
3. Add your SSH public key (`~/.ssh/id_ed25519.pub` — `ssh-keygen -t ed25519`
   if you have none).
4. Create, note the **public IP**.
5. VCN → subnet **security list** → add Ingress rules: TCP **22** and TCP
   **80** from `0.0.0.0/0`.

## 2. Ship the code + run setup (~1–2 h, mostly downloads)

On your Mac:

```bash
cd ~/Projects/ARIA
tar -czf /tmp/aria.tar.gz \
  --exclude=aria-2/.venv --exclude=aria-2/frontend/node_modules \
  --exclude=aria-2/frontend/dist --exclude=aria-2/.git aria-2
scp /tmp/aria.tar.gz ubuntu@<VM-IP>:/tmp/
ssh ubuntu@<VM-IP>
```

On the VM:

```bash
sudo bash /tmp/setup.sh  # see below — copy deploy/oracle-setup.sh first
```

Simpler — one scp for both, then:

```bash
scp /tmp/aria.tar.gz deploy/oracle-setup.sh ubuntu@<VM-IP>:/tmp/
ssh ubuntu@<VM-IP>
sudo bash /tmp/oracle-setup.sh /tmp/aria.tar.gz
```

The script installs Docker, locks the firewall to 22+80, asks for a login
password, builds, starts everything, and pulls `gemma3:12b` +
`nomic-embed-text`. Then open `http://<VM-IP>` and log in.

## 3. Notes

- Model: **gemma3:12b** (GGUF CPU build) — the MLX build only runs on Apple
  Silicon, so the whole repo now defaults to gemma3:12b everywhere.
- Data (chats, memory, KB) lives in the `aria_data` docker volume; models in
  `ollama_models`. Your chats are the valuable part — back them up with:
  `docker run --rm -v aria_aria_data:/d ubuntu tar -czf - -C /d . > aria-backup.tgz`
- Agent terminal/file tools refuse non-loopback callers, so on this box they
  are safely inert.
- Plain HTTP + password: fine on trusted networks, don't reuse the password.
  Proper TLS needs a domain (Let's Encrypt) — say the word and I'll add it.
