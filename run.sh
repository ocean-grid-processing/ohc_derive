for level in 15_20 15_300 300_700 700_1850 1800_1850
do
  outputdir=/scratch/alpine/wimi7695/ohc_prod/results
  sbatch derive.slurm ${outputdir}/OHC_*${level}*.nc $outputdir
done
