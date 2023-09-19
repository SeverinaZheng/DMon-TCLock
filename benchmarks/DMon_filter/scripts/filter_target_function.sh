# TARGET="spin_lock"
TARGET="down_write"
TARGET_D="/$TARGET/d"
PERF_DATA="/home/syncord/SynCord/benchmarks/will-it-scale/will_perf/lock1_perf.data"
/usr/lib/linux-tools-5.4.0-107/perf script -i $PERF_DATA| grep -A 1 $TARGET| sed $TARGET_D| sed '/--/d'> result.txt
awk '{print $2}' result.txt | sort | uniq > contend_func.txt
