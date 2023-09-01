@@
expression p;
identifier n =~ "spin_lock$";
identifier m =~ "spin_unlock$";
@@

{
+ extern int num_policy;
...
- n(&p->pa_lock);
+ my_bpf_spin_lock(&p->pa_lock,num_policy);
...
- m(&p->pa_lock);
+ my_bpf_spin_unlock(&p->pa_lock,num_policy);
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
- m(&p->pa_lock);
+ my_bpf_spin_unlock(&p->pa_lock,num_policy);
...
- n(&p->pa_lock);
+ my_bpf_spin_lock(&p->pa_lock,num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock$";
@@

{
+ extern int num_policy;
...
- n(&p->pa_lock);
+ my_bpf_spin_lock(&p->pa_lock,num_policy);
...
}


@@
expression p;
identifier m =~ "spin_unlock$";
@@

{
+ extern int num_policy;
...
- m(&p->pa_lock);
+ my_bpf_spin_unlock(&p->pa_lock,num_policy);
...
}

