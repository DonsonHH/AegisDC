sinfo -o '%P|%a|%l|%D|%t|%N|%G'
squeue -u renly -o '%.18i|%.9P|%.24j|%.8T|%.10M|%.10l|%.6D|%R'
cd /share/home/renly/renly-patrol-rsi/mainline/39c-development/24-instance-review-red
test ! -e job-id.txt
job_id=$(sbatch --parsable job.slurm)
printf '%s\n' "$job_id" > job-id.txt
scontrol show job "$job_id" -o
