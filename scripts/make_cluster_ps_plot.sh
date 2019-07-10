#!/usr/local/bin/bash

set -e

DIR="userdata/s4/prefisher"

FIGNAME="$1"

UP="$DIR/S4-1.0-CDT_grid-owl2_v1.1_psups_2019-06-17-11-42-23-EDT_1e-2photoz_abias.npy"
DOWN="$DIR/S4-1.0-CDT_grid-owl2_v1.1_psdowns_2019-06-17-11-42-23-EDT_1e-2photoz_abias.npy"
PREF="$DIR/S4-1.0-CDT_grid-owl2_v1.1_fish_factor_2019-06-17-11-42-23-EDT_1e-2photoz_abias.npy"
PARAM="$DIR/S4-1.0-CDT_grid-owl2_v1.1_params_2019-06-17-11-42-23-EDT_1e-2photoz_abias.npy"

python bin/plotClusterSpectra.py $FIGNAME -u $UP -d $DOWN -p $PREF -par $PARAM
