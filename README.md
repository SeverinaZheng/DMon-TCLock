# A Semi-automated Framework for Patching Specific Locks
## Description
Cache misses can reflect lock contentions. This project aims to automate the process by observing the L1 cache miss, one could figure out which lock is contending and prioritize that type of lock on the specific target structure by shuffling. The process includes 1. monitoring using perf; 2. finding out the lock/unlock function along with the structure; 3. finding the call chain from the lock/unlock function to the built-in bpf_version of the underlying lock; 4. changing all the same locks to bpf version across the kernel; 5. generating the patch. The following session will be organized to explain each step in detail

## Resources, tools and prerequisites
* perf (version linux-tools-5.4.0-107 was used)
* cscope
* coccinelle
* Different kernels(for spinlock/or for both spinlock and rwsem) which either enables shuffling or not [SynCord-linux source](https://github.com/SeverinaZheng/SynCord-linux/tree/main). The source code for only enabling rwsem can be found [here](https://github.com/rs3lab/TCLocks/tree/shfllock/src/kernel/linux-5.14.16)

## Repo Detail
The complete framework is on "patch" branch, while the main and master branches contain some intermediate work. Compared to the original DMon and TCLock repo, the scripts and some results for this project are under benchmarks/DMon_filter folder. The down_write, spin_lock and rwsem folder contain a template.patch file respectively, which has the patch code needed to be added into the kernel to allow the ebpf to work. And there might be a patch folder under those folders, which contains some working patches generated by the framework. The following sessions explains the scripts under scripts/ folder.

## Monitoring using perf
There are some environment variables to be set to use perf. The script is [here](https://github.com/SeverinaZheng/DMon-TCLock/blob/patch/benchmarks/DMon_filter/scripts/setenv.sh). The critical commands used to collect L1 cache misses and analyze them are:
```
perf record -g -C 0,1 -e mem_load_retired.l1_miss -- sleep 5
perf report -i path/to/perf_data
```
-g flag enables collecting call graphs, -C specifies the CPUs we look at, and -e denotes the event. We could look at all the CPUs but the distribution is similar for running the above command multiple times and the size will be way larger. The complete version can be found [here](https://github.com/efeslab/DMon-AE/blob/main/test-case/run.sh), which filter all level of cache misses.

## Finding out the lock/unlock function
The script [filter_target_function.sh](https://github.com/SeverinaZheng/DMon-TCLock/blob/patch/benchmarks/DMon_filter/scripts/filter_target_function.sh) will analyze the perf data to find the functions that finally call the spinlock/rwsem by looking at keyword "spin_lock" or "down_write". So the $TARGET and $PERF_DATA variable has to be changed to which lock is targeted(can be found by perf script command) and which perf.data is used.

After finding the functions, find_locking_spin_lock.sh/find_locking_down_write.sh will find the function calls that contain those keywords. For example, it will find 
```
"spin_lock(&files->file_lock)"
```
or
```
"if(down_write_killable(&mm->mmap_sem,flags))"
```
, and thus find out the target structures(file_lock/ mmap_sem).

## Finding the call chain
An example of the call chain is as follows:
```
spin_lock
| raw_spin_lock
| _raw_spin_lock
| __raw_spin_lock
| do_raw_spin_lock
| arch_spin_lock
-> queued_spin_lock
```
So the aim of this part is to find all these calls to deeply reach the bpf_functions built in the kernel(e.g. bpf_queued_spin_lock_slowpath). A heuristic that all the function names contain the keyword "spin_lock". The tricky part of finding the right call chain is that there might be macro definitions in between that redirect a function that doesn't have the keyword to one that does. The current solution is not only to look at itself, but also look at the function it's calling. All the functions found in the call chain will be rewritten to bpf version, which is, adding bpf_ to the function name, adding policy to arguments and its proper child function found in the call chain. An example will be:
```
static inline void do_raw_spin_unlock(raw_spinlock_t *lock) __releases(lock)
{
       mmiowb_spin_unlock();
       arch_spin_unlock(&lock->raw_lock,policy);
       __release(lock);
}
```
is modified to
```
static inline void bpf_do_raw_spin_unlock(raw_spinlock_t *lock, int policy) __releases(lock)
{
       mmiowb_spin_unlock();
       bpf_arch_spin_unlock(&lock->raw_lock,policy);
       __release(lock);
}

```

Upon finding the call chain, it will create a new header file that contains all the modified bpf prefixed functions under $my_bpf_path, which was "include/linux/my_bpf_spin_lock.h" for instance. The corresponding script is [adapt_to_bpf.py](https://github.com/SeverinaZheng/DMon-TCLock/blob/patch/benchmarks/DMon_filter/scripts/adapt_to_bpf.py).

## Changing all the same locks
The next step is to change all the locks on the same structure. In addition, our new header file needs to be included in all the relevant files. We used Coccinelle to achieve this. The coccinelle scripts are under [cocci_scripts](https://github.com/SeverinaZheng/DMon-TCLock/tree/patch/benchmarks/DMon_filter/scripts/cocci_scripts), which is basically adding extern num_policy and calling bpf_ prefixed functions. These coccinelle scripts need some manual work because coccinelle only can read arguments from the command line as predefined patterns and cannot use them in the code modification section. And the naming schema for the pipeline to function is {lock_type}_{structure}.cocci, which allows the framework to find the proper script.(e.g "spin_lock(&files->file_lock)" needs "spin_lock_file_lock.cocci")

## Generate the patch
A simple command to compare between SynCord-linux-base and SynCord-linux-destination:
```
diff -ruN SynCord-linux-base  SynCord-linux-destination > template.patch
```

## Getting started instructions
### Prepare the kernel source code
As a start, we only need to have the source code of the current kernel as SynCord-linux-base. (Used rwsem_spin_disable branch of the SynCord-linux repo above). If pulling from the SynCord-linux repo from rs3lab, remember to have a proper .config from SynCord/scripts repo. During the whole process, SynCord-linux-template will be generated as an intermediate folder and SynCord-linux-destination is the one that contains all the changes, which is used to generate the patch. 

### Run perf to find the contention
Run 
```
perf record -g -C 0,1 -e mem_load_retired.l1_miss -- sleep 5
```
to collect the perf.data trace and use 
```
perf report -i path/to/perf_data
```
to find the contention function/lock type.

### Generate the patch
Set the following variables:
```
TARGET, PERF_DATA in filter_target_function.sh
target_lock_type, target_unlock_type, source_path, template_path, destination_path, DMON_dir in generate.py
```
Then run 
```
python3 generate.py
```
which includes steps 2-5 and generate a patch in the home directory.

### Run with SynCord 
SynCord is a framework to modify kernel locks without recompiling or rebooting the kernel. It abstracts key behaviors of kernel locks and exposes them as APIs for designing user-defined kernel locks. SynCord provides the mechanisms to customize kernel locks safely and correctly from userspace. For more details, see the [webpage](https://rs3lab.github.io/SynCord/).

After generating the patch, run
```
python3 concord.py --linux /home/syncord/SynCord-linux-base --policy policy/numa-grouping --livepatch /home/syncord/template.patch
```
to compile and follow the [instruction](https://rs3lab.github.io/SynCord/docs/artifact.html) to insert the patch.


## Be cautious
1. when inserting the patch, "ERROR: invalid ancestor" for some random file: kpatch only allows changing c files, not the header files in the original source, which causes inconsistent object files and thus the error.
2. when inserting the patch, "ld: arch/x86/built-in.a: member arch/x86/mm/extable.o in archive is not an object": the previous build might not be cleaned, so remove and pull the original source code to be the base.
3. The vm's storage defined in the image might not be enough, remember to properly partition the file system and get enough size.
4. After inserting the patch, "NULL pointer dereference": the num_policy starts at 1 as how it was written in the inode.c in the patch, so starting from 0 will cause the problem.
5. Sometimes inside the vm there will be soft lockup even when "make" something, it's better to wait some time for it to resolve by itself instead of try to kill it, which might lead to corruption and not reboot.
6. Due to the time budget, this framework is a prototype, tested with dup1, open1, open2, fallocate1,signal1 and mmap1 in will-it-scale. The general flow works with other workloads, but there might be parsing and formatting bugs that need to be fixed.

