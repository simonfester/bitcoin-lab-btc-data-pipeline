import pandas as pd

# Check existing SOPR start date
sopr = pd.read_parquet("sopr.parquet")
print("Existing sopr.parquet:")
print(f"  Start: {sopr.index.min()}")
print(f"  End: {sopr.index.max()}")
print(f"  Rows: {len(sopr)}")
print(f"  Columns: {list(sopr.columns)}")
