#!/bin/bash
#SBATCH --qos=preemptable
#SBATCH --export=NONE
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --time=12:00:00
#SBATCH --job-name=derived_ohc
#SBATCH --output=%x.%j.out
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=katie.mills@colorado.edu
#SBATCH --mem=64GB
#SBATCH --exclude=blanca-g6-u21

module purge
module load anaconda/2023.09
conda activate ohc_crosscheck

cd $SLURM_SUBMIT_DIR
# $1 = mapped-layer level (from run.sh); $2 = provenance tag (required by derive.py --tag)
python derive.py /scratch/alpine/wimi7695/gcos_validation/OP20260127b_potentialTemperature_-89.5S_89.5N_20.5W_379.5E_2004_2025_${1}/OHC_* \
  --out /scratch/alpine/wimi7695/gcos_validation/OP20260127b_potentialTemperature_-89.5S_89.5N_20.5W_379.5E_2004_2025_${1} \
  --tag "${2:?derive.slurm needs a provenance tag as \$2 — launch via run.sh <tag>}" \
  --transforms integral,area --keep-members integral
