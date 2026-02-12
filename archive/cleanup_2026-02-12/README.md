# Cleanup 2026-02-12

Contenu archive de nettoyage (deplace depuis la racine du repo):

- `benchmarks_root/`: 39 fichiers de benchmark et reporting (`benchmark_*.json`, `go_live_checklist_report.json`)
- `server_logs/`: 8 logs serveur (`server-8080*.log`)
- `cleaned_csv/`: 2 CSV nettoyes (`cleaned_*.csv`)

Notes securite:

- Les fichiers temporaires secrets (`*.tmp`) ont ete sortis du repo vers:
  `%TEMP%\\lvmh_cleanup_secrets_2026-02-12\\root_tmp` (7 fichiers)
- Ils ne sont plus presents dans l'arborescence du projet.
