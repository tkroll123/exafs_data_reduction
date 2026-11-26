# Git cheat sheet for this project

Repository: https://github.com/tkroll123/exafs_data_reduction
Local folder: this folder (`exafs/data_reduction`).

Run all commands in Terminal from this folder:

```bash
cd ~/Library/CloudStorage/Dropbox/uni_dropbox/SSRL/scripts/exafs/data_reduction
```

---

## 1. One-time setup (once per computer)

**Your name and e-mail** (they appear in every commit):

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

**Login to GitHub.** GitHub does not accept your account password for git.
Use a *personal access token* instead:

1. GitHub → your picture (top right) → **Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token**.
2. Repository access: *Only select repositories* → `exafs_data_reduction`.
   Permissions → **Contents: Read and write**. Generate and copy the token.
3. The first time you `git push`, git asks for
   *Username* → your GitHub user name (`tkroll123`),
   *Password* → paste the token.

macOS stores the token in the Keychain (`credential.helper = osxkeychain`),
so you are asked only once. When the token expires, delete the
"github.com" entry in the *Keychain Access* app and push again.

---

## 2. First upload

### a) This folder already has a git repository (current situation)

The code is already committed locally; only the push is missing:

```bash
git status            # should say: "Your branch is ahead of 'origin/main' by 1 commit"
git push origin main
```

### b) Starting from scratch (new folder, no `.git` yet)

```bash
git init -b main
git remote add origin https://github.com/tkroll123/exafs_data_reduction.git
git pull origin main          # fetches what is already on GitHub (e.g. README, LICENSE)
git add -A                    # .gitignore decides what is left out
git status                    # check the list!  no .venv, no xas_worker-master
git commit -m "First version of the EXAFS data reduction app"
git push -u origin main
```

If `git pull` stops with *"untracked working tree files would be overwritten"*
(e.g. both have a `README.md`), move your local file aside, pull, put it back:

```bash
mv README.md README.local.md
git pull origin main
mv README.local.md README.md
```

---

## 3. Every time you changed something

```bash
git pull                      # 1. get changes made on GitHub (web edits, other computers)
git status                    # 2. which files changed?
git diff                      #    what exactly changed? (q to quit)
git add -A                    # 3. stage all changes   (or: git add app.py xas_core.py)
git commit -m "Short description of the change"
git push                      # 4. upload
```

Good commit messages say *what* and *why*, e.g.
`Download only the checked files` or `Fix calibration when foil column is missing`.

After editing `docs/manual.tex`, rebuild the PDF before committing:

```bash
cd docs && latexmk -pdf manual.tex && latexmk -c && cd ..
```

---

## 4. Useful commands

| Command | What it does |
|---|---|
| `git log --oneline` | list of commits |
| `git diff --staged` | what will go into the next commit |
| `git restore <file>` | throw away uncommitted changes to a file (careful!) |
| `git restore --staged <file>` | un-stage a file (keeps your changes) |
| `git commit --amend` | fix the last commit's message / add a forgotten file — **only before pushing** |
| `git rm --cached <file>` | stop tracking a file but keep it on disk (then add it to `.gitignore`) |
| `git clone https://github.com/tkroll123/exafs_data_reduction.git` | get the code on another computer |

---

## 5. What must NOT be uploaded

Handled by `.gitignore` — check `git status` before each commit anyway:

* `.venv/` (the Python environment — recreate it with `pip install -r requirements.txt`)
* `__pycache__/`, `.DS_Store`
* `xas_worker-master/` and `xas_worker-master.zip` (original scripts and beamline data)
* LaTeX build files in `docs/` (`*.aux`, `*.log`, …) — `manual.pdf` **is** uploaded
* passwords, tokens, unpublished measurement data

---

## 6. When something goes wrong

* **`rejected … fetch first`** when pushing: GitHub has commits you don't have
  (e.g. a web edit). Run `git pull`, then `git push` again.
* **Merge conflict** after `git pull`: open the files `git status` lists,
  keep the right version between the `<<<<<<<`, `=======`, `>>>>>>>` markers,
  delete the markers, then `git add <file>` and `git commit`.
* **`could not read Username`**: no login stored yet — see section 1.
* **Mixed web uploads and git**: always `git pull` before you start editing
  locally, so both sides stay in step.
