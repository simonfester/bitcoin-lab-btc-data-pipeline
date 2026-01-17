import pandas as pd
from backtesting import Backtest, Strategy
import os

# --- 1. DATA LOADING ENGINE ---
def load_and_merge_data(directory="."):
    """Stitches individual parquet files into a single strategy-ready DataFrame."""
    
    # Load Price first (The anchor)
    price = pd.read_parquet(os.path.join(directory, 'price.parquet'))
    if 'time' in price.columns: price = price.set_index('time')
    price = price.rename(columns={'value': 'Close'})
    
    # Define metrics to join
    metrics = {
        'mvrv_z.parquet': 'mvrv_z',
        'sopr_lth.parquet': 'sopr_lth',
        'sopr_sth.parquet': 'sopr_sth',
        'realized_price.parquet': 'realized_price'
    }
    
    for filename, metric_name in metrics.items():
        m_df = pd.read_parquet(os.path.join(directory, filename))
        if 'time' in m_df.columns: m_df = m_df.set_index('time')
        m_df = m_df.rename(columns={'value': metric_name})
        # Join only the specific metric column to avoid 'value' collisions
        price = price.join(m_df[[metric_name]], how='inner')

    # Convert to μBTC to handle fractional trading issue in Backtesting.py
    # This divides price by 1,000,000 so $100k cash can buy 1,000,000 units
    price['Close'] = price['Close'] / 1e6
    price['realized_price'] = price['realized_price'] / 1e6
    
    # Backtesting.py OHLC Requirements
    price['Open'] = price['High'] = price['Low'] = price['Close']
    price.index = pd.to_datetime(price.index)
    
    return price.sort_index().dropna()

# --- 2. THE STRATEGY LOGIC ---
class CycleGuardPro(Strategy):
    # Parameters for optimization
    mvrv_bottom = 0.1
    mvrv_top = 7.0
    sopr_exit = 2.0
    sth_dip_buy = 1.0

    def init(self):
        # Indicators
        self.mvrv = self.I(lambda x: x, self.data.mvrv_z)
        self.sopr_lth = self.I(lambda x: x, self.data.sopr_lth)
        self.sopr_sth = self.I(lambda x: x, self.data.sopr_sth)
        self.realized_price = self.I(lambda x: x, self.data.realized_price)

    def next(self):
        current_price = self.data.Close[-1]
        
        # --- ENTRY LOGIC ---
        # Buy 1: Macro Capitulation (High Conviction)
        if not self.position:
            if self.mvrv[-1] < self.mvrv_bottom:
                self.buy(size=0.9) # Allocate 90% of equity
        
        # Buy 2: Bull Market Dip (STH Panic)
        # If we are in a mid-cycle bull (MVRV 1-3) and STHs sell at a loss
        elif 1.0 < self.mvrv[-1] < 3.0 and self.sopr_sth[-1] < self.sth_dip_buy:
            if self.position.size < 1000: # Simple check to prevent over-stacking
                self.buy(size=0.1)

        # --- EXIT LOGIC ---
        # Exit 1: Macro Overheat (Profit taking)
        if self.mvrv[-1] > self.mvrv_top or self.sopr_lth[-1] > self.sopr_exit:
            self.position.close()
            
        # Exit 2: Dynamic Stop Loss (Price falls below Net Realized Price)
        elif current_price < self.realized_price[-1]:
            self.position.close()

# --- 3. EXECUTION ---
if __name__ == "__main__":
    data = load_and_merge_data()
    
    # Increase cash to 1M for buffer, finalize_trades closes open positions at end
    bt = Backtest(data, CycleGuardPro, cash=1_000_000, commission=.001, finalize_trades=True)
    
    stats = bt.run()
    print(stats)
    
    # Save the chart to an HTML file
    bt.plot(filename="btc_onchain_backtest.html")