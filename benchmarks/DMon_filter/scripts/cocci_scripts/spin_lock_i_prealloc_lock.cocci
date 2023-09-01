@@
expression p;
identifier n =~ "spin_lock$";
identifier m =~ "spin_unlock$";
@@

{
+ extern int num_policy;
...
- n(&p->i_prealloc_lock);
+ my_bpf_spin_lock(&p->i_prealloc_lock,num_policy);
...
- m(&p->i_prealloc_lock);
+ my_bpf_spin_unlock(&p->i_prealloc_lock,num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock$";
identifier m =~ "spin_unlock$";
@@

{
+ extern int num_policy;
...
- m(&p->i_prealloc_lock);
+ my_bpf_spin_unlock(&p->i_prealloc_lock,num_policy);
...
- n(&p->i_prealloc_lock);
+ my_bpf_spin_lock(&p->i_prealloc_lock,num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock$";
@@

{
+ extern int num_policy;
...
- n(&p->i_prealloc_lock);
+ my_bpf_spin_lock(&p->i_prealloc_lock,num_policy);
...
}


@@
expression p;
identifier m =~ "spin_unlock$";
@@

{
+ extern int num_policy;
...
- m(&p->i_prealloc_lock);
+ my_bpf_spin_unlock(&p->i_prealloc_lock,num_policy);
...
}

