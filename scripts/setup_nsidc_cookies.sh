#!/usr/bin/env bash
set -euo pipefail

read -r -p "Enter your NSIDC/earthdata.nasa.gov user name: " nsidc_uid

wget -O tmp.zip \
  --save-cookies .nsidc_cookies \
  --keep-session-cookies \
  --http-user="$nsidc_uid" \
  --ask-password \
  --no-check-certificate \
  --auth-no-challenge=on \
  -e robots=off \
  "https://daacdata.apps.nsidc.org/pub/DATASETS/nsidc0770_rgi_v7/README.txt"

rm -f tmp.zip
