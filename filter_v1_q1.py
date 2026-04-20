"""
One-off script to filter v1_dev files to only Q1 (October 2025) data,
so they can be compared against V2_preprod which only has Q1.
"""
import os
import pandas as pd

V1_DIR = "raw_data/aleph_apr/v1_dev"
V2_DIR = "raw_data/aleph_apr/V2_preprod"
OUTPUT_DIR = "raw_data/aleph_apr/v1_dev_q1"
FILTER_COL = "Month of Revenue Date"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Get Q1 filter values from a V2 file (should be "October 2025")
sample_v2 = os.listdir(V2_DIR)[0]
v2_df = pd.read_csv(os.path.join(V2_DIR, sample_v2))
q1_values = v2_df[FILTER_COL].dropna().unique().tolist()
print(f"Filtering v1_dev to: {q1_values}")

for fname in sorted(os.listdir(V1_DIR)):
    if not fname.endswith(".csv"):
        continue
    src = os.path.join(V1_DIR, fname)
    df = pd.read_csv(src)
    before = len(df)
    df_filtered = df[df[FILTER_COL].isin(q1_values)]
    after = len(df_filtered)
    out_path = os.path.join(OUTPUT_DIR, fname)
    df_filtered.to_csv(out_path, index=False)
    print(f"  {fname}: {before} -> {after} rows")

print(f"\nFiltered files saved to {OUTPUT_DIR}/")
