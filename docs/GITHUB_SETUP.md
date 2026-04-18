# 📤 How to Push This Project to GitHub

Complete guide to push Mira to your GitHub repository.

## Prerequisites

- Git installed (`git --version` to check)
- GitHub account
- This project extracted on your local machine

## Step 1: Create a Personal Access Token (PAT)

> **⚠️ NEVER share your token with anyone — including AI assistants!**

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Settings:
   - **Note:** "Mira Project"
   - **Expiration:** 30 days (or longer)
   - **Scopes:** Check **`repo`** only
4. Click **"Generate token"** at the bottom
5. **Copy the token** (starts with `ghp_...`)
6. **Save it securely** — you won't see it again!

## Step 2: Open Terminal in Project Folder

```bash
# Navigate to the extracted mira folder
cd path/to/mira

# Verify you're in the right place
ls
# Should see: README.md, docker-compose.yml, backend/, etc.
```

## Step 3: Initialize Git & Push

Copy-paste these commands one by one:

```bash
# Initialize git repository
git init

# Add all files (respects .gitignore — .env won't be included!)
git add .

# Create first commit
git commit -m "Initial commit: Mira foundation with Telegram bot + Docker"

# Set main branch
git branch -M main

# Add your GitHub repository as remote
git remote add origin https://github.com/apolloS125/Mira.git

# Push to GitHub
git push -u origin main
```

## Step 4: Authenticate

When prompted:

```
Username for 'https://github.com': apolloS125
Password for 'https://apolloS125@github.com': [paste your token here]
```

> **Note:** When you paste the token, you won't see any characters — that's normal for security. Just paste and press Enter.

## Step 5: Verify

Go to https://github.com/apolloS125/Mira

You should see all your files! 🎉

## Saving Credentials (Optional)

To avoid typing the token every time:

### macOS
```bash
git config --global credential.helper osxkeychain
```

### Windows
```bash
git config --global credential.helper manager
```

### Linux
```bash
git config --global credential.helper store
# Token will be stored in plain text at ~/.git-credentials
# Or use cache instead:
git config --global credential.helper 'cache --timeout=3600'
```

## Future Updates

After your first push, updating is easy:

```bash
# Make changes to files...

git add .
git commit -m "Describe what you changed"
git push
```

## Using SSH Instead (More Secure)

If you prefer SSH keys over tokens:

```bash
# 1. Generate SSH key
ssh-keygen -t ed25519 -C "your.email@example.com"

# 2. Copy public key
cat ~/.ssh/id_ed25519.pub
# On macOS: pbcopy < ~/.ssh/id_ed25519.pub
# On Windows: clip < ~/.ssh/id_ed25519.pub

# 3. Add to GitHub
# Go to https://github.com/settings/keys
# Click "New SSH key", paste, save

# 4. Change remote URL
git remote set-url origin git@github.com:apolloS125/Mira.git

# 5. Push
git push
```

## Troubleshooting

### "remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/apolloS125/Mira.git
```

### "failed to push some refs"
```bash
# Fetch remote changes first
git pull origin main --rebase
git push
```

### "Permission denied" with SSH
```bash
# Test SSH connection
ssh -T git@github.com
# Should say: "Hi apolloS125! You've successfully authenticated..."
```

### ".env was committed by accident"

Serious! Follow these steps:

```bash
# 1. Immediately revoke all API keys in .env
# 2. Remove from git
git rm --cached .env
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Remove .env from tracking"
git push

# 3. Remove from history (if already pushed)
# Install git-filter-repo first
git filter-repo --path .env --invert-paths
git push --force
```

## Security Checklist

Before pushing, verify:

- [ ] `.env` is in `.gitignore`
- [ ] No API keys in any committed file
- [ ] No passwords in code
- [ ] `.env.example` has placeholder values only

Run this to check:
```bash
grep -r "sk-ant-" . --exclude-dir=.git
grep -r "ghp_" . --exclude-dir=.git
# Should return nothing (or only in .env which is gitignored)
```

## You're Done! 🎊

Your project is now on GitHub. Next:

1. Add a description on GitHub repo page
2. Add topics: `ai`, `telegram-bot`, `langgraph`, `llm`, `rag`
3. Star your own repo (why not 😄)
4. Share on LinkedIn/Twitter!
