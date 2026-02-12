param(
    [string]$DeckInput = "docs/JURY_DECK_15_SLIDES.md",
    [string]$DeckOutput = "docs/JURY_DECK_15_SLIDES.pdf"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $DeckInput)) {
    throw "Input deck not found: $DeckInput"
}

Write-Host "Exporting deck to PDF..."
Write-Host "Input : $DeckInput"
Write-Host "Output: $DeckOutput"

# Requires Node + Marp CLI:
# npm i -g @marp-team/marp-cli
npx @marp-team/marp-cli@latest $DeckInput --pdf --allow-local-files --output $DeckOutput

Write-Host "Deck exported: $DeckOutput"
