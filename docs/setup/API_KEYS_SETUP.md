# API Keys Setup - Quick Start

## ✅ Current Status

Your API keys are now securely stored in `.env` file and properly gitignored.

## 🔑 Your API Keys

### Bitcoin Lab
- **Key**: `ae92658e-373f-4fce-a5b3-1cfc1ffb4da6`
- **URL**: https://api.researchbitcoin.net
- **Stored in**: `.env` as `BITCOIN_LAB_API_KEY` and `BITCOIN_LAB_TOKEN`

### Glassnode
- **Key**: `1vQgbCQeHhEaY0YJAxNY90YB25H`
- **URL**: https://studio.glassnode.com
- **Stored in**: `.env` as `GLASSNODE_API_KEY`

## 📁 Files Created

1. **`.env`** - Your actual API keys (✅ gitignored)
2. **`.env.example`** - Template for other developers (safe to commit)
3. **`src/secrets.py`** - Secrets manager utility
4. **`SECRETS_MANAGEMENT.md`** - Complete documentation

## 🚀 What Changed

### Before (❌ Insecure)
```python
# Hardcoded in source files
BITCOIN_LAB_API_TOKEN = "ae92658e-373f-4fce-a5b3-1cfc1ffb4da6"
GLASSNODE_API_KEY = "1vQgbCQeHhEaY0YJAxNY90YB25H"
```

### After (✅ Secure)
```python
# Loaded from .env file
from src.secrets import get_bitcoin_lab_key, get_glassnode_key
```

## 🔍 Updated Files

The following files were updated to use the secrets manager:
- ✅ `src/data_loader.py` - Now loads from `.env`
- ✅ `scripts/dashboard.py` - Now loads from `.env`
- ✅ `src/downloader.py` - Already used env vars (no change needed)
- ✅ `.env` - Created with your keys
- ✅ `.env.example` - Created as template

## ✔️ Verify Setup

```bash
# Test secrets manager
python src/secrets.py

# Should output:
# ✅ Bitcoin Lab API Key: Found
# ✅ Glassnode API Key: Found
# ✅ All API keys configured correctly!
```

## 🛡️ Security Checklist

- [x] API keys moved to `.env` file
- [x] `.env` added to `.gitignore`
- [x] `.env.example` created for sharing
- [x] Code updated to use secrets manager
- [x] Secrets manager tested and working

## 📝 Daily Usage

You don't need to do anything different! The scripts automatically load keys from `.env`:

```bash
# All these work automatically
python run.py dashboard
python run.py brk-sync
python scripts/calculate.py
```

## 🔄 Updating Keys

If you get new API keys:

1. **Edit `.env` file**:
   ```bash
   nano .env
   ```

2. **Update the keys**:
   ```bash
   BITCOIN_LAB_API_KEY=your_new_key_here
   GLASSNODE_API_KEY=your_new_key_here
   ```

3. **Verify**:
   ```bash
   python src/secrets.py
   ```

## 🚨 Important Security Rules

### ✅ DO
- Keep `.env` file secure (600 permissions)
- Use different keys for dev/production
- Rotate keys periodically
- Share `.env.example` (not `.env`)

### ❌ DON'T
- Never commit `.env` to git
- Never share keys in chat/email
- Never hardcode keys in source code
- Never push `.env` backups

## 🐛 Troubleshooting

### "API key not found" Error
```bash
# 1. Check .env exists
ls -la .env

# 2. Check contents
cat .env

# 3. Test loading
python src/secrets.py
```

### Keys Not Loading
```bash
# Verify .env file format
cat .env

# Should look like:
# BITCOIN_LAB_API_KEY=ae92658e-373f-4fce-a5b3-1cfc1ffb4da6
# No quotes, no spaces around =
```

## 📚 More Information

See `SECRETS_MANAGEMENT.md` for:
- Production deployment
- Multiple environments
- Advanced configuration
- Full API reference

## ✅ You're All Set!

Your API keys are now secure and your pipeline will work exactly as before, just more securely!

```bash
# Test the full pipeline
python run.py dashboard
```

---

**Created**: 2026-01-24
**Next Steps**: Use your pipeline normally - keys load automatically!
