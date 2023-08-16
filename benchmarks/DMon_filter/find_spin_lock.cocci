@@
expression p;
@@

(
- spin_lock(&p->file_lock);
+ my_bpf_spin_lock(&p->file_lock);
|
- spin_unlock(&p->file_lock);
+ my_bpf_spin_unlock(&p->file_lock);
)
