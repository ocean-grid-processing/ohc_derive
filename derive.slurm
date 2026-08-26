#!/bin/bash
#SBATCH --qos=blanca-giglio
#SBATCH --account=blanca-giglio
#SBATCH --partition=blanca-giglio
#SBATCH --export=NONE
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --time=12:00:00
#SBATCH --job-name=ohc_derive
#SBATCH --output=%x.%j.out
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=katie.mills@colorado.edu
#SBATCH --mem=256GB
#SBATCH --exclude=blanca-g6-u21

module purge
module load anaconda/2023.09
conda activate ohc_crosscheck

cd $SLURM_SUBMIT_DIR
python run.py \
/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev15_20_expC_prod_260824.nc \
/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev15_300_expC_prod_260824.nc \
/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev300_700_expC_prod_260824.nc \
/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev700_1000_expC_prod_260824.nc \
/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev700_1850_expC_prod_260824.nc \
/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev1800_1850_expC_prod_260824.nc \
    --level 0_2000 \
    --bathy /scratch/alpine/wimi7695/ohc_prod/params/etopo60.cdf \
    --quantities ohca,ohu,ohca_trend,ohu_trend \
    --mask contiguous_from_top \
    --tag  260824-OP20260507 \
    --provenance-link https://github.com/argovis/ohc_derive/releases/tag/prod_260824-ohca-ohu \
    --out /scratch/alpine/wimi7695/ohc_prod/results_260824


# zenodo 4.0.0 (ohc_ohu)
#    /scratch/alpine/wimi7695/ohc_validation/ohca/results_260824/OHC_2004_2024_lev15_20_expC_validation_260810.nc \
#    /scratch/alpine/wimi7695/ohc_validation/ohca/results_260824/OHC_2004_2024_lev15_300_expC_validation_260810.nc \
#    /scratch/alpine/wimi7695/ohc_validation/ohca/results_260824/OHC_2004_2024_lev300_700_expC_validation_260810.nc \
#    /scratch/alpine/wimi7695/ohc_validation/ohca/results_260824/OHC_2004_2024_lev700_1850_expC_validation_260810.nc \
#    /scratch/alpine/wimi7695/ohc_validation/ohca/results_260824/OHC_2004_2024_lev1800_1850_expC_validation_260810.nc \

# zenodo 4.0.1 (gcos)
# /scratch/alpine/wimi7695/ohc_validation/gcos/results_260824/OHC_2004_2025_lev15_20_expC_validation_260810.nc \
# /scratch/alpine/wimi7695/ohc_validation/gcos/results_260824/OHC_2004_2025_lev15_300_expC_validation_260810.nc \
# /scratch/alpine/wimi7695/ohc_validation/gcos/results_260824/OHC_2004_2025_lev300_700_expC_validation_260810.nc \
# /scratch/alpine/wimi7695/ohc_validation/gcos/results_260824/OHC_2004_2025_lev700_1850_expC_validation_260810.nc \
# /scratch/alpine/wimi7695/ohc_validation/gcos/results_260824/OHC_2004_2025_lev1800_1850_expC_validation_260810.nc \

# OP20260506
#/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev15_20_expC_prod_260824.nc \
#/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev15_300_expC_prod_260824.nc \
#/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev300_700_expC_prod_260824.nc \
#/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev700_1000_expC_prod_260824.nc \
#/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev700_1850_expC_prod_260824.nc \
#/scratch/alpine/wimi7695/ohc_prod/results_260824/OHC_2004_2025_lev1800_1850_expC_prod_260824.nc \
