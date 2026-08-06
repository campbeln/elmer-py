# Elmer (Python) — Quick Start

Get the API running locally in about five minutes, on Ubuntu, macOS, or
Windows. Each OS section is self-contained — jump to yours and follow it
top to bottom.

**What you need before starting:** Python 3.9+, and the `elmer-python.zip`
project archive.

---

## Ubuntu Linux

### 1. Check Python

Ubuntu 22.04+ ships Python 3.10 or newer, which is enough. Confirm it:

```bash
python3 --version
```

If that prints `Python 3.9` or higher, skip to step 2. If it's missing or
older:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip
```

### 2. Unzip the project

```bash
unzip elmer-python.zip -d ~/elmer
cd ~/elmer/elmer-py
```

### 3. Create a virtual environment

Keeps Elmer's dependencies isolated from anything else on the machine.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run it

```bash
python3 _index.py dev
```

You should see a JSON status block print to the terminal, ending with a
`routes` list. The server is now listening on **port 3001** (the `dev`
config; `prod` uses port 3000 — see [Dev vs. prod](#dev-vs-prod-which-port)
below).

### 6. Confirm it's alive

Open a second terminal (leave the server running in the first) and:

```bash
curl http://localhost:3001/
```

You should get back a JSON heartbeat: `{"ok": true, "message": "Hi 👋 from api", ...}`.

To stop the server, go back to the first terminal and press `Ctrl+C`.

---

## macOS

### 1. Check Python

macOS does **not** reliably ship a usable Python 3 by default. Check first:

```bash
python3 --version
```

If that fails or shows something older than 3.9, install Python via
[Homebrew](https://brew.sh):

```bash
# If you don't have Homebrew yet:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Then:
brew install python@3.12
```

### 2. Unzip the project

Double-click `elmer-python.zip` in Finder, or from Terminal:

```bash
unzip elmer-python.zip -d ~/elmer
cd ~/elmer/elmer-py
```

### 3. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run it

```bash
python3 _index.py dev
```

You'll see a JSON status block print out; the server listens on **port
3001** for the `dev` config.

### 6. Confirm it's alive

In a second Terminal tab (`Cmd+T`):

```bash
curl http://localhost:3001/
```

Expect `{"ok": true, "message": "Hi 👋 from api", ...}`.

Stop the server with `Ctrl+C` in the first tab.

> **Gatekeeper note:** macOS may flag Terminal's network access the first
> time you run this — click **Allow** if prompted.

---

## Windows

These steps use **PowerShell**. Open it via Start → type "PowerShell" →
Enter — you do not need Administrator rights for any of this.

### 1. Install Python

Check first, in case it's already there:

```powershell
python --version
```

If that errors, or Windows opens the Microsoft Store instead of printing a
version, install Python properly:

1. Go to [python.org/downloads](https://www.python.org/downloads/) and
   download the latest **Python 3.x** Windows installer.
2. Run it. **Check the box "Add python.exe to PATH"** on the first screen —
   this step is the one people miss, and skipping it breaks every command
   below.
3. Click **Install Now**.
4. Close and reopen PowerShell, then re-check:
   ```powershell
   python --version
   ```

### 2. Unzip the project

Right-click `elmer-python.zip` → **Extract All…**, choose a destination
(e.g. `C:\elmer`), then in PowerShell:

```powershell
cd C:\elmer\elmer-py
```

(Adjust the path to wherever you extracted it.)

### 3. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)`.

> **If you see an error about "running scripts is disabled on this
> system"**, PowerShell's execution policy is blocking the activation
> script. Fix it for your user only (no admin needed):
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> Then re-run the `Activate.ps1` line above.

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

### 5. Run it

```powershell
python _index.py dev
```

You'll see a JSON status block print out; the server listens on **port
3001** for the `dev` config.

### 6. Confirm it's alive

Open a second PowerShell window and run:

```powershell
Invoke-RestMethod http://localhost:3001/
```

(or, if you have `curl` available — Windows 10/11 include a real `curl.exe` —
`curl http://localhost:3001/` works too.) Expect a JSON heartbeat back.

Stop the server with `Ctrl+C` in the first window.

> **Windows Firewall note:** the first time you run the server, Windows may
> pop up a firewall prompt asking whether to allow Python to accept
> connections. Click **Allow access** — otherwise other devices on your
> network won't be able to reach the API (localhost access is unaffected
> either way).

---

## Common to all platforms

### Dev vs. prod: which port?

`_index.py` takes one argument selecting the config overlay:

```bash
python3 _index.py dev    # port 3001 — app/config/dev.json
python3 _index.py prod   # port 3000 — app/config/prod.json
```

Both merge on top of `app/config/base.json`. Omitting the argument, or
passing anything else, defaults to `prod`.

### Trying the other endpoints

With the server running:

```bash
# Heartbeat
curl http://localhost:3001/

# Log in and get a JWT (default demo credentials from base.json)
curl -X POST http://localhost:3001/login/admin \
     -H 'Content-Type: application/json' \
     -d '{ "username":"cn", "password":"secret" }'

# Static content
curl http://localhost:3001/www/index.html
```

If you've added the support-ticket routes (`app/routes/tickets.py`), also
see the [Supabase setup](#connecting-support-tickets-to-supabase) section
below.

### Connecting support tickets to Supabase

The ticket API (`/tickets`) needs two credentials before it can save
anything: your Supabase project URL and its **service-role** key (Project
Settings → API in the Supabase dashboard — not the `anon` key).

Apply the schema once, via the Supabase SQL editor:

```
supabase/migrations/0001_tickets.sql
```

Then provide credentials as environment variables before starting the
server (preferred, since it keeps the key out of any config file you might
commit):

**Ubuntu / macOS:**
```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_KEY="your-service-role-key"
python3 _index.py dev
```

**Windows (PowerShell):**
```powershell
$env:SUPABASE_URL = "https://your-project.supabase.co"
$env:SUPABASE_SERVICE_KEY = "your-service-role-key"
python _index.py dev
```

Until these are set, `POST /tickets` responds `503 Ticket storage is not
configured` — every other route works normally.

Once set, open the web form in a browser:

```
http://localhost:3001/www/tickets.html
```

### Stopping and restarting later

Stop the server any time with `Ctrl+C`. To come back to it later, from the
`elmer-py` directory:

```bash
# Ubuntu / macOS
source .venv/bin/activate
python3 _index.py dev
```

```powershell
# Windows
.venv\Scripts\Activate.ps1
python _index.py dev
```

You only need to `pip install -r requirements.txt` again if the
requirements file changes.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `command not found: python3` (macOS/Ubuntu) | Python isn't installed | See step 1 for your OS above |
| `'python' is not recognized...` (Windows) | Python wasn't added to PATH | Reinstall Python and check "Add python.exe to PATH" |
| `ModuleNotFoundError: No module named 'flask'` | Dependencies installed outside the virtual environment, or the venv isn't activated | Re-run the `activate` command for your OS, then `pip install -r requirements.txt` again |
| `Address already in use` / `port 3001 is already allocated` | Another process (maybe a previous run) is already bound to that port | Find and stop it, or run with `prod` instead of `dev` to use port 3000 |
| Server starts but `curl` / browser can't reach it | Firewall blocking the connection | See the OS-specific firewall notes above; confirm you're hitting `localhost`, not a different hostname |
| `POST /tickets` returns `503` | Supabase credentials not set | See [Connecting support tickets to Supabase](#connecting-support-tickets-to-supabase) |
| PowerShell: "running scripts is disabled on this system" | Default execution policy blocks venv activation | See the note under Windows step 3 |

If something's still stuck, the full JSON status block printed at startup
(under `"routes"`) lists every route Elmer discovered — a good first check
that your route files are where they should be.
