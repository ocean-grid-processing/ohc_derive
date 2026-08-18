#!/bin/bash
#SBATCH --qos=preemptable
#SBATCH --export=NONE
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --time=12:00:00
#SBATCH --job-name=ohc_derive
#SBATCH --output=%x.%j.out
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=katie.mills@colorado.edu
#SBATCH --mem=64GB
#SBATCH --exclude=blanca-g6-u21

module purge
module load anaconda/2023.09
conda activate ohc_crosscheck

cd $SLURM_SUBMIT_DIR
python run.py \
    /data/me4oh/OHC_LocalGP_15_20.nc \
    /data/me4oh/OHC_LocalGP_15_300.nc \
    /data/me4oh/OHC_LocalGP_300_700.nc \
    /data/me4oh/OHC_LocalGP_700_1850.nc \
    /data/me4oh/OHC_LocalGP_1800_1850.nc \
    --level 0_2000 \
    --bathy /data/standard/bathy_1deg.nc \
    --quantities ohca,ohu,ohca_trend,ohu_trend \
    --mask fully_wet_nan \
    --time-window 2005:2024 \
    --tag dev \
    --provenance-link https://example.dev.com \
    --out /data/derive_out
