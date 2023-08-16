@@
expression p;
identifier n =~ "spin_lock$";
identifier m =~ "spin_unlock$";
@@

{
+ extern int policy;
...
- n(&p->file_lock);
+ my_bpf_spin_lock(&p->file_lock,policy);
...
- m(&p->file_lock);
+ my_bpf_spin_unlock(&p->file_lock,policy);
...
}

@@
expression p;
identifier n =~ "spin_lock$";
identifier m =~ "spin_unlock$";
@@

{
+ extern int policy;
...
- m(&p->file_lock);
+ my_bpf_spin_unlock(&p->file_lock,policy);
...
- n(&p->file_lock);
+ my_bpf_spin_lock(&p->file_lock,policy);
...
}

@@
expression p;
identifier n =~ "spin_lock$";
@@

{
+ extern int policy;
...
- n(&p->file_lock);
+ my_bpf_spin_lock(&p->file_lock,policy);
...
}


@@
expression p;
identifier m =~ "spin_unlock$";
@@

{
+ extern int policy;
...
- m(&p->file_lock);
+ my_bpf_spin_unlock(&p->file_lock,policy);
...
}

