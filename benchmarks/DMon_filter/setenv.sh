sudo sysctl -w kernel.perf_event_paranoid=-1
sudo sysctl -w kernel.kptr_restrict=0
sudo sysctl -w kernel.randomize_va_space=0
export WL_PATH=~/TCLocks/src/benchmarks/will-it-scale/runscript.sh
