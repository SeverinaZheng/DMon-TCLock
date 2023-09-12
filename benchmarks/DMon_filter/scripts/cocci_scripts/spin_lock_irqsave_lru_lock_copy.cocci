@@
expression p;
identifier n =~ "spin_lock_irqsave$";
identifier m =~ "spin_unlock_irqrestore$";
@@

{
+ extern int num_policy;
...
- n(&p->lru_lock, flags);
+ my_bpf_spin_lock_irqsave(&p->lru_lock, flags, num_policy);
...
- m(&p->lru_lock, flags);
+ my_bpf_spin_unlock_irqrestore(&p->lru_lock, flags, num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock_irqsave$";
identifier m =~ "spin_unlock_irqrestore$";
@@

{
+ extern int num_policy;
...
- m(&p->lru_lock, flags);
+ my_bpf_spin_unlock_irqrestore(&p->lru_lock, flags, num_policy);
...
- n(&p->lru_lock, flags);
+ my_bpf_spin_lock_irqsave(&p->lru_lock, flags, num_policy);
...
}

@@
expression p;
identifier n =~ "spin_lock_irqsave$";
@@

{
+ extern int num_policy;
...
- n(&p->lru_lock, flags);
+ my_bpf_spin_lock_irqsave(&p->lru_lock, flags,num_policy);
...
}


@@
expression p;
identifier m =~ "spin_unlock_irqrestore$";
@@

{
+ extern int num_policy;
...
- m(&p->lru_lock, flags);
+ my_bpf_spin_unlock_irqrestore(&p->lru_lock, flags,num_policy);
...
}

