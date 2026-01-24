# Repository Organization

**Date**: 2026-01-24
**Status**: Reorganized for clarity and maintainability

## 🎯 Goals

1. **Clean root directory** - Only essential files
2. **Organized documentation** - Logical grouping by purpose
3. **Easy navigation** - Clear structure for new users
4. **Maintainability** - Easy to find and update docs

## 📂 Current Structure

### Root Directory (Clean!)

```
bitcoin-lab-btc-data-pipeline/
├── CLAUDE.md                  # AI assistant instructions
├── README.md                  # Main entry point
├── requirements.txt           # Python dependencies
├── run.py                     # CLI entry point
├── .env                       # API keys (gitignored)
├── .env.example               # API keys template
├── certs/                     # SSL certificates
├── config/                    # Configuration files
├── data/                      # Data storage
├── docs/                      # 📚 All documentation
├── logs/                      # Application logs
├── research/                  # Jupyter notebooks
├── scripts/                   # Executable utilities
├── src/                       # Core library
├── venv/                      # Python virtual environment
├── dashboard.html             # Generated: main dashboard
├── dashboard_signals.html     # Generated: signals dashboard
└── dashboard_quality.html     # Generated: quality report
```

### Documentation Structure

```
docs/
├── README.md                  # Documentation index
├── setup/                     # 🔧 Configuration guides
│   ├── API_KEYS_SETUP.md
│   ├── SECRETS_MANAGEMENT.md
│   └── DATA_SOURCE_CONFIG.md
├── guides/                    # 📖 Usage guides
│   ├── DASHBOARD_WORKFLOW.md
│   ├── QUICK_REFERENCE.md
│   └── EXIT_SIGNALS_GUIDE.md
├── research/                  # 🔬 Strategy development
│   ├── STRATEGY_FRAMEWORK.md
│   ├── RESEARCH_PRINCIPLES.md
│   └── BACKTEST_REPORT.md
└── archive/                   # 📦 Historical reports
    ├── INVESTIGATION_SUMMARY.md
    ├── DATA_QUALITY_RECOMMENDATIONS.md
    ├── BRK_DATA_CORRUPTION_REPORT.md
    ├── BRK_DATA_FORMAT_INVESTIGATION.md
    └── DATA_SOURCE_NOTES.md
```

## 📋 What Was Changed

### Files Moved

#### Setup Documentation → `docs/setup/`
- ✅ `API_KEYS_SETUP.md`
- ✅ `SECRETS_MANAGEMENT.md`
- ✅ `DATA_SOURCE_CONFIG.md`

#### Usage Guides → `docs/guides/`
- ✅ `DASHBOARD_WORKFLOW.md`
- ✅ `QUICK_REFERENCE.md`
- ✅ `EXIT_SIGNALS_GUIDE.md`

#### Research Docs → `docs/research/`
- ✅ `STRATEGY_FRAMEWORK.md`
- ✅ `RESEARCH_PRINCIPLES.md`
- ✅ `BACKTEST_REPORT.md`

#### Archive Reports → `docs/archive/`
- ✅ `INVESTIGATION_SUMMARY.md`
- ✅ `DATA_QUALITY_RECOMMENDATIONS.md`
- ✅ `data/BRK_DATA_CORRUPTION_REPORT.md`
- ✅ `data/BRK_DATA_FORMAT_INVESTIGATION.md`
- ✅ `data/claude.md` → `DATA_SOURCE_NOTES.md`

### Files Created

- ✅ `docs/README.md` - Documentation index
- ✅ `docs/ORGANIZATION.md` - This file
- ✅ `.env` - API keys (gitignored)
- ✅ `.env.example` - API keys template
- ✅ `src/secrets.py` - Secrets manager

### Files Updated

- ✅ `README.md` - Added docs references
- ✅ `src/data_loader.py` - Uses secrets manager
- ✅ `scripts/dashboard.py` - Uses secrets manager

## 🎨 Design Principles

### Root Directory
- **Minimal** - Only essential files and directories
- **Functional** - CLI, config, data, code
- **Generated files** - HTML dashboards stay in root (frequently accessed)

### Documentation (`docs/`)
- **Organized by purpose** - Setup, guides, research, archive
- **Index at top** - `docs/README.md` for navigation
- **Linked from main README** - Easy discovery

### Data (`data/`)
- **No documentation** - Keep it clean, only data files
- **Subdirectories by source** - `brk/`, `glassnode/`, `signals/`
- **Generated outputs** - `results/`, `signals/`

### Code (`src/`, `scripts/`)
- **Source library** - `src/` for importable modules
- **Executables** - `scripts/` for runnable utilities
- **Clear separation** - Library vs. scripts

## 🔍 Finding Things

### "Where is the documentation for...?"

| Topic | Location |
|-------|----------|
| Setting up API keys | `docs/setup/API_KEYS_SETUP.md` |
| Running dashboards | `docs/guides/DASHBOARD_WORKFLOW.md` |
| Common commands | `docs/guides/QUICK_REFERENCE.md` |
| Strategy development | `docs/research/STRATEGY_FRAMEWORK.md` |
| Data source config | `docs/setup/DATA_SOURCE_CONFIG.md` |
| Historical investigations | `docs/archive/` |

### "Where should I put...?"

| Content Type | Location |
|--------------|----------|
| New setup guide | `docs/setup/` |
| New usage guide | `docs/guides/` |
| Research notes | `docs/research/` |
| One-time report | `docs/archive/` |
| Source code | `src/` |
| Executable script | `scripts/` |
| Jupyter notebook | `research/` |

## ✅ Benefits

### Before Reorganization
- ❌ 12 markdown files in root
- ❌ Hard to find documentation
- ❌ No clear organization
- ❌ API keys hardcoded in source

### After Reorganization
- ✅ Clean root directory (4 files + dirs)
- ✅ All docs in `docs/` with clear structure
- ✅ Easy to navigate via `docs/README.md`
- ✅ Secure API key management
- ✅ Better discoverability
- ✅ Professional appearance

## 🚀 Next Steps

### For New Users
1. Start at main `README.md`
2. Follow setup guide: `docs/setup/API_KEYS_SETUP.md`
3. Learn daily workflow: `docs/guides/DASHBOARD_WORKFLOW.md`

### For Contributors
1. Check existing docs before creating new ones
2. Use appropriate `docs/` subdirectory
3. Update `docs/README.md` index when adding docs
4. Keep root directory minimal

### For Maintenance
1. Archive old investigations to `docs/archive/`
2. Keep guides up-to-date in `docs/guides/`
3. Document new features in appropriate section
4. Review and prune archive periodically

## 📝 Maintenance Policy

### What Stays in Root
- ✅ Entry points (`README.md`, `run.py`)
- ✅ Configuration templates (`.env.example`)
- ✅ Generated dashboards (`*.html`)
- ✅ Essential project files (`CLAUDE.md`, `requirements.txt`)

### What Goes in `docs/`
- ✅ All markdown documentation
- ✅ Setup and configuration guides
- ✅ Usage tutorials and workflows
- ✅ Research documentation
- ✅ Historical reports and investigations

### What's Not Allowed in Root
- ❌ Loose documentation files
- ❌ One-off reports
- ❌ Investigation notes
- ❌ Temporary files
- ❌ API keys or secrets

## 🎯 Success Metrics

- **Root files**: Target < 10 markdown files (currently: 2)
- **Documentation findability**: < 2 clicks to any doc
- **Onboarding time**: New user to first dashboard < 10 minutes
- **Maintainability**: Can find and update any doc quickly

---

**Reorganized by**: Claude Code
**Maintained by**: Bitcoin Lab Data Pipeline Team
**Last Updated**: 2026-01-24
