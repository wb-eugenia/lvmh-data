"""
Test CSV via Cloud Run API - 50 notes
"""
import requests
import time
import csv
import sys
import json

API_BASE = "https://lvmh-api-570069708764.europe-west9.run.app"

print("=== Connexion ===")
login_resp = requests.post(
    f"{API_BASE}/api/auth/login",
    data={"username": "manager@lvmh.com", "password": "lvmh"}
)
if login_resp.status_code != 200:
    print(f"Login echoue: {login_resp.status_code}")
    exit(1)

token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("Connecte!")

# Test file
csv_file = "LVMH_Realistic_Merged_CA001-100.csv"
max_notes = 50

print(f"\n=== Test: {csv_file} ({max_notes} notes) ===")

# Read CSV
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)[:max_notes]

print(f"Nb notes: {len(rows)}")

start_time = time.time()
success = 0
errors = 0
results_list = []

for i, row in enumerate(rows):
    text = row.get('Transcription', row.get('text', ''))
    if not text:
        continue
    
    lang = row.get('Language', 'FR')
    
    try:
        resp = requests.post(
            f"{API_BASE}/api/analyze",
            headers=headers,
            json={"text": text, "language": lang},
            timeout=30
        )
        
        if resp.status_code == 200:
            success += 1
            result = resp.json()
            results_list.append({
                "id": result.get('id'),
                "tier": result.get('routing', {}).get('tier'),
                "tags": result.get('tags', []),
                "confidence": result.get('routing', {}).get('confidence'),
                "processing_time_ms": result.get('processing_time_ms'),
            })
        else:
            errors += 1
            print(f"   Erreur {i}: {resp.status_code}")
    except Exception as e:
        errors += 1
        print(f"   Exception {i}: {e}")
    
    if (i + 1) % 10 == 0:
        elapsed = time.time() - start_time
        print(f"   Progression: {i+1}/{len(rows)} - {elapsed:.1f}s")

elapsed_total = time.time() - start_time

print(f"\n=== Resultats ===")
print(f"Temps total: {elapsed_total:.1f}s")
print(f"Temps/note: {elapsed_total/len(rows):.2f}s")
print(f"Reussis: {success}, Erreurs: {errors}")

# Stats
tier_counts = {}
for r in results_list:
    tier = r['tier']
    tier_counts[tier] = tier_counts.get(tier, 0) + 1

print(f"\nDistribution tiers:")
for tier, count in sorted(tier_counts.items()):
    print(f"   Tier {tier}: {count}")

# Save results
with open("output/test_cloudrun_50.json", 'w', encoding='utf-8') as f:
    json.dump(results_list, f, indent=2, ensure_ascii=False)
print(f"\nResultats sauvegardes: output/test_cloudrun_50.json")
