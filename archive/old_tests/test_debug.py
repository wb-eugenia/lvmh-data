import pandas as pd
import io

# Read the test file
df = pd.read_csv('test_dup.csv')
print("Original DataFrame:")
print(df)
print(f"\nShape: {df.shape}")
print(f"\nTranscription column: {df['Transcription'].tolist()}")

# Check for duplicates
dups = df.duplicated(subset=['Transcription', 'Language'], keep='first')
print(f"\nDuplicates mask: {dups.tolist()}")
print(f"Number of duplicates: {dups.sum()}")

# After cleaning
df['Transcription'] = df['Transcription'].astype(str).str.strip()
df['Transcription'] = df['Transcription'].str.replace(r'\s+', ' ', regex=True)
print("\nAfter cleaning:")
print(df['Transcription'].tolist())

# Check for duplicates again
dups_clean = df.duplicated(subset=['Transcription', 'Language'], keep='first')
print(f"\nDuplicates after cleaning: {dups_clean.sum()}")
