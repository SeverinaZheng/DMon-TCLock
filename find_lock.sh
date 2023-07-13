rm -rf perf.data selected.txt stride stride.txt tmp.txt without-debug
#WORKLOAD="lock1"
taskset -c 0,1 ~/TCLocks/src/benchmarks/will-it-scale/runscript.sh &
sleep 20
perf record -C 0,1 -e mem_load_retired.l1_miss -- sleep 1
