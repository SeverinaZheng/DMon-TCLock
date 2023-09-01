@@
expression p;
identifier n =~ "spin_lock$";
identifier m =~ "spin_unlock$";
@@

{
+ extern int num_policy;
...
- n(&p->file_lock);
+ my_bpf_spin_lock(&p->file_lock,num_policy);
...
- m(&p->file_lock);
+ my_bpf_spin_unlock(&p->file_lock,num_policy);
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
- m(&p->file_lock);
+ my_bpf_spin_unlock(&p->file_lock,num_policy);
...
- n(&p->file_lock);
+ my_bpf_spin_lock(&p->file_lock,num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock$";
@@

{
+ extern int num_policy;
...
- n(&p->file_lock);
+ my_bpf_spin_lock(&p->file_lock,num_policy);
...
}


@@
expression p;
identifier m =~ "spin_unlock$";
@@

{
+ extern int num_policy;
...
- m(&p->file_lock);
+ my_bpf_spin_unlock(&p->file_lock,num_policy);
...
}

