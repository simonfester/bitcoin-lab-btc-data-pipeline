# Test adding LTH-SOPR to STRAT-002
# Run this in the notebook after the other cells

print("\n" + "="*100)
print("STRAT-002 + LTH-SOPR ENHANCEMENT TEST")
print("="*100)

# Original STRAT-002
strat002_cond = (df['sopr'] < 1) & (df['sopr_sth'] < 1) & (df['rl_zscore'] > 0.5)
strat002_entry = strat002_cond & ~strat002_cond.shift(1).fillna(False)

# STRAT-002 + LTH-SOPR < 1
strat002_lth_cond = (df['sopr'] < 1) & (df['sopr_sth'] < 1) & (df['rl_zscore'] > 0.5) & (df['sopr_lth'] < 1)
strat002_lth_entry = strat002_lth_cond & ~strat002_lth_cond.shift(1).fillna(False)

# STRAT-002 + LTH-SOPR < 1.05 (looser threshold)
strat002_lth_loose_cond = (df['sopr'] < 1) & (df['sopr_sth'] < 1) & (df['rl_zscore'] > 0.5) & (df['sopr_lth'] < 1.05)
strat002_lth_loose_entry = strat002_lth_loose_cond & ~strat002_lth_loose_cond.shift(1).fillna(False)

# STRAT-002 + Entity-Adjusted < 1 (for comparison)
strat002_adj_cond = (df['sopr'] < 1) & (df['sopr_sth'] < 1) & (df['rl_zscore'] > 0.5) & (df['sopr_adjusted'] < 1)
strat002_adj_entry = strat002_adj_cond & ~strat002_adj_cond.shift(1).fillna(False)

test_entries = {
    'STRAT-002 (baseline)': strat002_entry,
    'STRAT-002 + LTH < 1': strat002_lth_entry,
    'STRAT-002 + LTH < 1.05': strat002_lth_loose_entry,
    'STRAT-002 + Adj < 1': strat002_adj_entry,
}

print(f"\n{'Signal':<25} {'Entries':>8} {'/Year':>8}")
print("-"*50)
for name, entry in test_entries.items():
    print(f"{name:<25} {entry.sum():>8} {entry.sum()/years:>8.1f}")

print("\n" + "-"*120)
print(f"{'Signal':<25} {'Return':>10} {'CAGR':>8} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8} {'WinRate':>8} {'PF':>8}")
print("-"*120)

for name, entry in test_entries.items():
    pf = run_backtest(df, entry, trail=0.30)
    m = get_metrics(pf, years)
    if m:
        print(f"{name:<25} {m['return']:>+9.0f}% {m['cagr']:>+7.1f}% {m['sharpe']:>8.2f} {m['max_dd']:>7.1f}% {m['trades']:>8} {m['win_rate']:>7.0f}% {m['profit_factor']:>8.2f}")
    else:
        print(f"{name:<25} {'NO TRADES':>10}")

print("-"*120)
print(f"{'Buy & Hold':<25} {bh:>+9.0f}%")

# Show which trades are filtered out by adding LTH
print("\n" + "="*100)
print("TRADE COMPARISON: What does adding LTH-SOPR filter out?")
print("="*100)

strat002_dates = df.index[strat002_entry].tolist()
strat002_lth_dates = df.index[strat002_lth_entry].tolist()

print(f"\nSTRAT-002 entries: {len(strat002_dates)}")
print(f"STRAT-002 + LTH entries: {len(strat002_lth_dates)}")

filtered_out = [d for d in strat002_dates if d not in strat002_lth_dates]
print(f"\nFiltered OUT by adding LTH < 1: {len(filtered_out)} entries")
for d in filtered_out:
    price_at_entry = df.loc[d, 'price']
    lth_val = df.loc[d, 'sopr_lth']
    print(f"  {d.date()}: Price=${price_at_entry:,.0f}, LTH-SOPR={lth_val:.3f}")
