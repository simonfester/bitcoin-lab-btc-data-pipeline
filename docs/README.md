# Documentation Index

Complete documentation for the Bitcoin Lab BTC Data Pipeline.

## 📚 Quick Navigation

| Category | Description | Location |
|----------|-------------|----------|
| **Setup** | Installation, configuration, API keys | [`setup/`](setup/) |
| **Guides** | How-to guides and workflows | [`guides/`](guides/) |
| **Research** | Strategy frameworks and analysis | [`research/`](research/) |
| **Archive** | Historical investigations and reports | [`archive/`](archive/) |

---

## 🚀 Getting Started

**New to this project?** Start here:

1. 📖 [Main README](../README.md) - Project overview
2. 🔑 [API Keys Setup](setup/API_KEYS_SETUP.md) - Configure your credentials
3. 📊 [Dashboard Workflow](guides/DASHBOARD_WORKFLOW.md) - Generate dashboards
4. 📋 [Quick Reference](guides/QUICK_REFERENCE.md) - Common commands

---

## 📂 Documentation Structure

### [setup/](setup/) - Setup & Configuration

Configure the pipeline and manage credentials.

| File | Description |
|------|-------------|
| [`API_KEYS_SETUP.md`](setup/API_KEYS_SETUP.md) | Quick start guide for API key configuration |
| [`SECRETS_MANAGEMENT.md`](setup/SECRETS_MANAGEMENT.md) | Complete secrets management guide |
| [`DATA_SOURCE_CONFIG.md`](setup/DATA_SOURCE_CONFIG.md) | Data source configuration (BRK, Bitcoin Lab, Glassnode) |

---

### [guides/](guides/) - Usage Guides

Learn how to use the pipeline for daily trading analysis.

| File | Description |
|------|-------------|
| [`DASHBOARD_WORKFLOW.md`](guides/DASHBOARD_WORKFLOW.md) | Complete dashboard generation workflow |
| [`QUICK_REFERENCE.md`](guides/QUICK_REFERENCE.md) | Common commands cheat sheet |
| [`EXIT_SIGNALS_GUIDE.md`](guides/EXIT_SIGNALS_GUIDE.md) | Understanding exit signals |

---

### [research/](research/) - Research & Strategy

Framework for developing and testing trading strategies.

| File | Description |
|------|-------------|
| [`STRATEGY_FRAMEWORK.md`](research/STRATEGY_FRAMEWORK.md) | James Check framework implementation |
| [`RESEARCH_PRINCIPLES.md`](research/RESEARCH_PRINCIPLES.md) | Research methodology and principles |
| [`BACKTEST_REPORT.md`](research/BACKTEST_REPORT.md) | Backtesting results and analysis |

---

### [archive/](archive/) - Historical Reports

Past investigations and one-time analyses.

| File | Description |
|------|-------------|
| [`INVESTIGATION_SUMMARY.md`](archive/INVESTIGATION_SUMMARY.md) | Data source investigation (2026-01-23) |
| [`DATA_QUALITY_RECOMMENDATIONS.md`](archive/DATA_QUALITY_RECOMMENDATIONS.md) | Quality improvement recommendations |

---

## 🎯 Common Tasks

### Daily Trading Workflow
```bash
# 1. Sync all data and generate dashboards
python run.py dashboard

# 2. View signals
open dashboard_signals.html

# 3. View on-chain metrics
open dashboard.html
```

**Guide**: [Dashboard Workflow](guides/DASHBOARD_WORKFLOW.md)

---

### First-Time Setup
```bash
# 1. Configure API keys
cp .env.example .env
nano .env  # Add your keys

# 2. Verify setup
python src/secrets.py

# 3. Run first sync
python run.py dashboard
```

**Guide**: [API Keys Setup](setup/API_KEYS_SETUP.md)

---

### Data Management
```bash
# Check data freshness
python run.py dashboard-quality

# Manual sync
python run.py brk-sync

# Check quota
python run.py quota
```

**Guide**: [Data Source Config](setup/DATA_SOURCE_CONFIG.md)

---

### Strategy Development
```bash
# Run backtest
python scripts/backtest.py

# Calculate signals
python scripts/calculate.py

# Analyze results
jupyter notebook research/
```

**Guide**: [Strategy Framework](research/STRATEGY_FRAMEWORK.md)

---

## 📊 Dashboard Types

### Main Dashboard (`dashboard.html`)
6-pillar on-chain analysis:
1. **Valuation** - MVRV, MVRV-Z, AVIV
2. **Profitability** - NUPL, Supply in Profit/Loss
3. **Spending Behavior** - SOPR (all cohorts)
4. **Supply Distribution** - LTH/STH metrics
5. **Activity** - Liveliness, Vaultedness
6. **Miner Health** - Puell Multiple, Difficulty

### Signals Dashboard (`dashboard_signals.html`)
Actionable trading signals:
- **Entry Signals** - Checkmate, Buy The Dip
- **Exit Signals** - 8-Metric Detector, LTH Distribution
- **Local Tops** - STH-MVRV Zones

---

## 🔧 Technical Reference

### Command Line Interface
```bash
python run.py --help
```

### Data Sources
- **BRK** (FREE) - Primary on-chain metrics
- **Bitcoin Lab** (Paid) - Backup, hourly data
- **Glassnode** (Paid) - Derivatives (funding, liquidations)

### File Structure
```
bitcoin-lab-btc-data-pipeline/
├── docs/              # This directory
│   ├── setup/         # Configuration guides
│   ├── guides/        # Usage guides
│   ├── research/      # Strategy docs
│   └── archive/       # Historical reports
├── data/              # Data storage
│   ├── brk/daily/     # BRK on-chain data
│   ├── glassnode/     # Derivatives data
│   └── signals/       # Computed signals
├── scripts/           # Executables
├── src/               # Source code
├── research/          # Jupyter notebooks
└── config/            # Configuration files
```

---

## 📖 External Resources

### James Check Framework
- [Checkonchain Newsletter](https://www.checkonchain.com/)
- Masterclass Series (in `research/check/`)

### Data Providers
- [Bitcoin Lab API](https://api.researchbitcoin.net)
- [Glassnode Studio](https://studio.glassnode.com)
- [BRK (Bitcoin Research Kit)](https://next.bitview.space)

### Community
- File issues: [GitHub Issues](https://github.com/your-repo/issues)
- Discussions: [GitHub Discussions](https://github.com/your-repo/discussions)

---

## 🆘 Getting Help

1. **Check the guides** - Most common tasks are documented
2. **Run with `--help`** - All commands support help flags
3. **Check logs** - `logs/` directory for detailed errors
4. **File an issue** - For bugs or feature requests

---

## 📝 Contributing

Want to improve the docs?

1. Edit the relevant markdown file
2. Keep it concise and practical
3. Include code examples
4. Test all commands before documenting

---

**Last Updated**: 2026-01-24
**Version**: 1.0
**Maintained By**: Bitcoin Lab Data Pipeline Project
