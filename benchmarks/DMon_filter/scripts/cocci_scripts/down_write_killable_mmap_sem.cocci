@@
expression E;
identifier p;
@@
{
+ extern int num_policy;
...
- down_write_killable(&E->mmap_sem)
+ my_bpf_down_write_killable(&E->mmap_sem, num_policy)
...
}
