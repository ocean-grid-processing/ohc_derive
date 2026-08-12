TAG=${1:?usage: ./run.sh <provenance-tag>   (e.g. ./run.sh OP20260127b)}
for level in 15_20 15_300 300_700 700_1850 1800_1850
do
  sbatch derive.slurm $level "$TAG"
done
