#!/bin/bash

for file in ./*.fits; do
  # Extract the unpadded number using parameter expansion and remove leading zeros
  base=$(basename "$file")
  newname=$(echo "$base" | sed -E 's/^(.*_)(0*)([1-9][0-9]*)\.fits$/\1\3.fits/')
  echo $file = $newname
  # Rename the file only if the name changed
  if [[ "$base" != "$newname" ]]; then
    mv $file $newname
  fi
done
