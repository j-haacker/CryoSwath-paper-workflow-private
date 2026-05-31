#!/bin/usr/env bash

wget --load-cookies .nsidc_cookies --no-check-certificate --auth-no-challenge=on -e robots=off -nH -nd -r -np --accept-regex "RGI2000-v7.0-G-0[13456789]_.*.zip" --reject "index.html*" "https://daacdata.apps.nsidc.org/pub/DATASETS/nsidc0770_rgi_v7/regional_files/RGI2000-v7.0-G/"
for zip in RGI2000-v7.0-G-0*.zip
do
    unzip -d $(pwd)"/resources/auxiliary/RGI/"${zip%.zip} $zip
    rm $zip
done
