#!/usr/bin/env bash
# Rebuild the evaluation excerpts listed in eval/clips.json from their public sources (run from backend/).
set -euo pipefail
RAW=data/eval/raw; OUT=data/eval/clips; UA="Unsaid-eval/0.1"
mkdir -p "$RAW" "$OUT"
get() { [ -f "$RAW/$2" ] || curl -sSL -A "$UA" -o "$RAW/$2" "$1"; }
cut() { ffmpeg -y -v error -ss "$2" -to "$3" -i "$RAW/$1" -c:v libx264 -preset veryfast -crf 23 -c:a aac -b:a 128k -movflags +faststart "$OUT/$4.mp4"; }
get "https://upload.wikimedia.org/wikipedia/commons/2/27/3_of_4_-_Analysis_-_Explaining_Fourier_analysis_with_a_machines.webm" fourier.webm
get "https://upload.wikimedia.org/wikipedia/commons/4/4c/A-level_Physics_Core_Practical-_Capacitor_Discharge.webm" capacitor.webm
get "https://upload.wikimedia.org/wikipedia/commons/0/02/How_a_Laser_Works.webm" laser.webm
get "https://upload.wikimedia.org/wikipedia/commons/3/35/CCD_-_The_heart_of_a_digital_camera_%28how_a_charge-coupled_device_works%29.webm" ccd.webm
cut fourier.webm 0 100 fourier-a
cut fourier.webm 125 225 fourier-b
cut capacitor.webm 60 175 capacitor
cut laser.webm 120 230 laser
cut ccd.webm 40 155 ccd
echo "clips ready in $OUT"
