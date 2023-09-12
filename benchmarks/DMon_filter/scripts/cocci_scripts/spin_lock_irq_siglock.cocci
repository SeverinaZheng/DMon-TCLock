@@
expression p;
identifier n =~ "spin_lock_irq$";
identifier m =~ "spin_unlock_irq$";
@@

{
+ extern int num_policy;
...
- n(&p->siglock);
+ my_bpf_spin_lock_irq(&p->siglock, num_policy);
...
- m(&p->siglock);
+ my_bpf_spin_unlock_irq(&p->siglock, num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock_irq$";
identifier m =~ "spin_unlock_irq$";
@@

{
+ extern int num_policy;
...
- m(&p->siglock);
+ my_bpf_spin_unlock_irq(&p->siglock, num_policy);
...
- n(&p->siglock);
+ my_bpf_spin_lock_irq(&p->siglock, num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock_irq$";
@@

{
+ extern int num_policy;
...
- n(&p->siglock);
+ my_bpf_spin_lock_irq(&p->siglock, num_policy);
...
}


@@
expression p;
identifier m =~ "spin_unlock_irq$";
@@

{
+ extern int num_policy;
...
- m(&p->siglock);
+ my_bpf_spin_unlock_irq(&p->siglock, num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock_irq$";
identifier m =~ "spin_unlock_irq$";
@@

- m(&p->siglock);
+ extern int num_policy;
+ my_bpf_spin_unlock_irq(&p->siglock, num_policy);

@@
expression p;
identifier n =~ "spin_lock_irq$";
identifier m =~ "spin_unlock_irq$";
@@

- n(&p->siglock);
+ extern int num_policy;
+ my_bpf_spin_lock_irq(&p->siglock, num_policy);
