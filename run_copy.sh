rm -rf perf.data tmp.txt selected.txt 
WL_PATH=~/TCLocks/src/benchmarks/will-it-scale/runscript.sh
export PATH=$PATH:~/pmu-tools
taskset -c 0,1 $WL_PATH &
sleep 15
toplev.py -l1 --no-desc --core C0 -o tmp.txt sleep 1 &> /dev/null
val=$(grep Backend_Bound tmp.txt |awk '{printf "%d\n", $5}')

#first  check the cache miss, if all levels surpass the threshold, perf to find the problematic line
if (( $(echo "$val > 9.9" |bc -l) ))
then
  echo "Severe backend bound problems ($val% of pipeline slots) identified, enabling memory bound profiling";
  toplev.py -l2 --no-desc --core C0 -o tmp.txt sleep 1 &> /dev/null
  val=$(grep Backend_Bound.Memory_Bound tmp.txt |awk '{printf "%d\n", $5}')
    if (( $(echo "$val > 9.9" |bc -l) ))
    then
      echo "Severe memory bound problems ($val% of pipeline slots) identified, enabling L1/L2/L3 bound profiling";
      toplev.py -l3 --no-desc --core C0 -o tmp.txt sleep 1 &> /dev/null
      one=$(grep Backend_Bound.Memory_Bound.L1_Bound tmp.txt |awk '{printf "%d\n", $5}')
      two=$(grep Backend_Bound.Memory_Bound.L2_Bound tmp.txt |awk '{printf "%d\n", $5}')
      three=$(grep Backend_Bound.Memory_Bound.L3_Bound tmp.txt |awk '{printf "%d\n", $5}')
      total=$(echo "$one $two $three"|awk '{printf "%d\n",$1+$2+$3}');
      if (( $(echo "$total > 9.9" |bc -l) ))				
      then									        echo "Severe L1/L2/L3 bound problems ($total% of pipeline slots) identified, enabling cache miss sampling";
	rm -rf perf.data						
	perf record -g -C 0,1 -e mem_load_retired.l1_miss -- sleep 5 # mem_load_retired.l1_miss or mem_load_retired.l3_miss						perf report -g -F+srcline
      fi
   fi										fi
