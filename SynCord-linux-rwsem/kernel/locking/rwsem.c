// SPDX-License-Identifier: GPL-2.0
/* kernel/rwsem.c: R/W semaphores, public implementation
 *
 * Written by David Howells (dhowells@redhat.com).
 * Derived from asm-i386/semaphore.h
 */

#include <linux/types.h>
#include <linux/kernel.h>
#include <linux/sched.h>
#include <linux/sched/debug.h>
#include <linux/export.h>
#include <linux/rwsem.h>
#include <linux/atomic.h>
#include <linux/random.h>
#include <linux/smp.h>
#include <linux/percpu.h>
#include <linux/sched/stat.h>
#include <linux/topology.h>

#include "rwsem.h"

static int __aqm_lock_slowpath(struct rwmutex *lock, long state, int is_reader);

static void __rwmutex_init(struct rwmutex *lock)
{
	atomic_set(&lock->val, 0);
	lock->tail = NULL;
}

/*
 * Actual trylock that will work on any unlocked state.
 */
static inline bool __rwmutex_trylock(struct rwmutex *lock)
{
	return (atomic_cmpxchg(&lock->val, 0, 1) == 0);
}

static inline void rwmutex_lock(struct rwmutex *lock, int is_reader)
{
	if (likely(cmpxchg(&lock->locked_no_stealing, 0, 1) == 0))
		return;

	__aqm_lock_slowpath(lock, TASK_UNINTERRUPTIBLE, is_reader);
}

static inline void rwmutex_unlock(struct rwmutex *lock)
{
	xchg(&lock->locked, 0);
}

static DEFINE_PER_CPU(u32, seed);

/*
 * Controls the probability for intra-socket lock hand-off. It can be
 * tuned and depend, e.g., on the number of CPUs per socket. For now,
 * choose a value that provides reasonable long-term fairness without
 * sacrificing performance compared to a version that does not have any
 * fairness guarantees.
 */
#ifndef INTRA_SOCKET_HANDOFF_PROB_ARG
#define INTRA_SOCKET_HANDOFF_PROB_ARG  0x10000
#endif

#ifndef THRESHOLD
#define THRESHOLD (0xffff)
#endif

#ifndef UNLOCK_COUNT_THRESHOLD
#define UNLOCK_COUNT_THRESHOLD 1024
#endif

#define MAX_POLICY 5
void *bpf_prog_should_reorder_rwsem[MAX_POLICY];
EXPORT_SYMBOL(bpf_prog_should_reorder_rwsem);

static int syncord_should_reorder(struct rwmutex *lock, struct rwaqm_node *node, struct rwaqm_node *curr, int policy_id)
{
	return 0;
}

static inline uint32_t xor_random(void)
{
        u32 v = this_cpu_read(seed);

        if (v == 0)
		get_random_bytes(&v, sizeof(u32));

        v ^= v << 6;
        v ^= (u32)(v) >> 21;
        v ^= v << 7;
        this_cpu_write(seed, v);

        return v & (UNLOCK_COUNT_THRESHOLD - 1);
	/* return v; */
}

static inline bool probably(unsigned int range)
{
        return xor_random() & (range - 1);
}

static inline void enable_stealing(struct rwmutex *lock)
{
        atomic_andnot(_RWAQ_MCS_NOSTEAL_VAL, &lock->val);
}

static inline void unlock_and_enable_stealing(struct rwmutex *lock)
{
        WRITE_ONCE(lock->locked_no_stealing, 0);
}

static inline void disable_stealing(struct rwmutex *lock)
{
        atomic_fetch_or_acquire(_RWAQ_MCS_NOSTEAL_VAL, &lock->val);
}

static inline u8 is_stealing_disabled(struct rwmutex *lock)
{
        return smp_load_acquire(&lock->no_stealing);
}

static inline void set_sleader(struct rwaqm_node *node, struct rwaqm_node *qend)
{
        smp_store_release(&node->sleader, 1);
        if (qend != node)
                smp_store_release(&node->last_visited, qend);
}

static inline void clear_sleader(struct rwaqm_node *node)
{
        node->sleader = 0;
}

static inline void set_waitcount(struct rwaqm_node *node, int count)
{
        smp_store_release(&node->wcount, count);
}

static inline void wake_up_waiter(struct rwaqm_node *node)
{
	wake_up_process(node->task);
}

static inline void schedule_out_curr_task(void)
{
        schedule_preempt_disabled();
}

static int force_update_node(struct rwaqm_node *node, u8 state)
{
#if 1
        if (cmpxchg(&node->lstatus, _RWAQ_MCS_STATUS_PWAIT,
                    state) == _RWAQ_MCS_STATUS_PWAIT)
                return false;
        /**
         * OUCH: That is going to hurt as I am doing two
         * atomic instructions just for the sake of avoiding
         * the wakeup in the worst case scenario i.e., waking
         * up the VERY NEXT WAITER.
         **/
        if (cmpxchg(&node->lstatus, _RWAQ_MCS_STATUS_PARKED,
                    state) == _RWAQ_MCS_STATUS_PARKED) {
                wake_up_waiter(node);
                return true;
        }
#endif
        return false;
}

static inline void park_waiter(struct rwaqm_node *node, long state)
{
	set_current_state(state);
#if 1
        if (cmpxchg(&node->lstatus, _RWAQ_MCS_STATUS_PWAIT,
                    _RWAQ_MCS_STATUS_PARKED) == _RWAQ_MCS_STATUS_PWAIT) {
		schedule_out_curr_task();
	}
#endif
        set_current_state(TASK_RUNNING);
}

static inline void shuffle_waiters(struct rwmutex *lock, struct rwaqm_node *node,
				   int is_next_waiter)
{
        struct rwaqm_node *curr, *prev, *next, *last, *sleader, *qend;
        int nid;
        int curr_locked_count;
        int one_shuffle = false;
        int woke_up_one = false;
	int cmp = 0;

        prev = smp_load_acquire(&node->last_visited);
        if (!prev)
                prev = node;
        last = node;
        curr = NULL;
        next = NULL;
        sleader = NULL;
        qend = NULL;

        nid = node->nid;
        curr_locked_count = node->wcount;

        barrier();

        cmpxchg(&node->lstatus, _RWAQ_MCS_STATUS_PWAIT, _RWAQ_MCS_STATUS_UNPWAIT);

        /*
         * If the wait count is 0, then increase node->wcount
         * to 1 to avoid coming it again.
         */
        if (curr_locked_count == 0) {
                set_waitcount(node, ++curr_locked_count);
        }

        /*
         * Our constraint is that we will reset every shuffle
         * leader and the new one will be selected at the end,
         * if any.
         *
         * This one here is to avoid the confusion of having
         * multiple shuffling leaders.
         */
        clear_sleader(node);

        /*
         * In case the curr_locked_count has crossed a
         * threshold, which is certainly impossible in this
         * design, then load the very next of the node and pass
         * the shuffling responsibility to that @next.
         */
#ifdef USE_COUNTER
        if (curr_locked_count >= _AQ_MAX_LOCK_COUNT)
#else
	if (!probably(INTRA_SOCKET_HANDOFF_PROB_ARG))
#endif
	{
                sleader = smp_load_acquire(&node->next);
                goto out;
        }

        /*
         * In this loop, we try to shuffle the wait queue at
         * least once to allow waiters from the same socket to
         * have no cache-line bouncing. This shuffling is
         * associated in two aspects:
         * 1) when both adjacent nodes belong to the same socket
         * 2) when there is an actual shuffling that happens.
         *
         * Currently, the approach is very conservative. If we
         * miss any of the elements while traversing, we return
         * back.
         */
        for (;;) {
                /*
                 * Get the curr first
                 */
                curr = READ_ONCE(prev->next);

                /*
                 * Now, right away we can quit the loop if curr
                 * is NULL or is at the end of the wait queue
                 * and choose @last as the sleader.
                 */
                if (!curr) {
                        /* sleader = last; */
                        /* qend = prev; /1* Until prev, I am updated *1/ */
                        break;
                }

                /*
                 * If we are the last one in the tail, then
                 * we cannot do anything, we should return back
                 * while selecting the next sleader as the last one
                 */
                if (curr == READ_ONCE(lock->tail)) {
                        /* sleader = last; */
                        /* qend = prev; */
                        break;
                }

                /* got the current for sure i?*/
		cmp = syncord_should_reorder(lock,node,curr,0);
		
                /* Check if curr->nid is same as nid */
                if (cmp && curr->nid == nid && curr->type == false) {
                        /*
                         * if prev->nid == curr->nid, then
                         * just update the last and prev
                         * and proceed forward
                         */
                        if (prev->nid == nid) {
#ifdef USE_COUNTER
				set_waitcount(curr, ++curr_locked_count);
#else
				set_waitcount(curr, curr_locked_count);
#endif

                                last = curr;
                                prev = curr;
                                one_shuffle = true;

				woke_up_one = force_update_node(curr,
                                                        _RWAQ_MCS_STATUS_UNPWAIT);

				if (woke_up_one && need_resched()) {
					__set_current_state(TASK_RUNNING);
					schedule_out_curr_task();
				}
                        }
			else {
                                /* prev->nid is not same, then we need
                                 * to find next and move @curr to
                                 * last->next, while linking @prev->next
                                 * to next.
                                 *
                                 * NOTE: We do not update @prev here
                                 * because @curr has been already moved
                                 * out.
                                 */
                                next = READ_ONCE(curr->next);
                                if (!next) {
					/* XXX */
                                        /* sleader = last; */
                                        break;
                                }

                                /*
                                 * Since, we have curr and next,
                                 * we mark the curr that it has been
                                 * shuffled and shuffle the queue
                                 */
#ifdef USE_COUNTER
				set_waitcount(curr, ++curr_locked_count);
#else
				set_waitcount(curr, curr_locked_count);
#endif

				smp_store_release(&prev->next, next);
				smp_store_release(&curr->next, last->next);
				smp_store_release(&last->next, curr);

                                woke_up_one = force_update_node(curr,
                                               _RWAQ_MCS_STATUS_UNPWAIT);
                                last = curr;
                                /* curr = next; */
				prev = next;
                                one_shuffle = true;

                        }
                } else
                        prev = curr;

                if (one_shuffle &&
		    ((is_next_waiter && !READ_ONCE(lock->locked)) ||
		     (!is_next_waiter && smp_load_acquire(&node->lstatus)
		      				== _RWAQ_MCS_STATUS_LOCKED))) {
			sleader = last;
                        /* qend = prev; */
                        break;
                }

		if (need_resched()) {
			__set_current_state(TASK_RUNNING);
			schedule_out_curr_task();
		}
        }

     out:
        if (sleader) {
                set_sleader(sleader, qend);
        }
}

static int __aqm_lock_slowpath(struct rwmutex *lock, long state, int is_reader)
{
	struct rwaqm_node snode ____cacheline_aligned;
	struct rwaqm_node *node = &snode;
        struct rwaqm_node *prev, *next;
        u8 plstatus;
	u16 wcount = 0;
	u8 sleader = true;

        preempt_disable();
	barrier();
        node->next = NULL;
        node->last_visited = NULL;
        node->locked = _RWAQ_MCS_STATUS_PWAIT;
        node->nid = numa_node_id();
        node->task = current;
	node->type = is_reader;

        /*
         * Ensure that the initialisation of @node is complete before we
         * publish the updated tail via xchg_tail() and potentially link
         * @node into the waitqueue via WRITE_ONCE(prev->next, node) below.
         */
        smp_wmb();

        prev = xchg(&lock->tail, node);
        next = NULL;

        if (prev) {

                WRITE_ONCE(prev->next, node);

                for (;;) {
			if (smp_load_acquire(&node->lstatus) ==
			    				_RWAQ_MCS_STATUS_LOCKED)
				break;

			/* if (READ_ONCE(node->sleader)) { */
			/* 	shuffle_waiters(lock, node, false); */
			/* } */

                        if (need_resched()) {
                                /*if (single_task_running()) {
                                        __set_current_state(TASK_RUNNING);
                                        schedule_out_curr_task();
                                } else {
                                        park_waiter(node, state);
                                }*/
								//TODO: Fix this
								__set_current_state(TASK_RUNNING);
								schedule_out_curr_task();
                        }
                        cpu_relax();
                }
        } else {
		/* disable_stealing(lock); */
	}

        /*
         * we are now the very next waiters, all we have to do is
         * to wait for the @lock->locked to become 0, i.e. unlocked.
         * In the meantime, we will try to be shuffle leader if possible
         * and at least find someone in my socket.
         */

	wcount = smp_load_acquire(&node->wcount);
	if (wcount)
		sleader = smp_load_acquire(&node->sleader);
	else
		sleader = true;
        for(;;) {

                if (!smp_load_acquire(&lock->locked))
                        break;

		if (need_resched())
			schedule_out_curr_task();

		if (sleader) {
			sleader = false;
			/* enable_stealing(lock); */
			shuffle_waiters(lock, node, true);
			/* disable_stealing(lock); */
		}
        }

        for (;;) {
                if (cmpxchg(&lock->locked, 0, 1) == 0) {
                        /* lock->nid = numa_node_id(); */
                        break;
                }

                while (smp_load_acquire(&lock->locked)) {

			if (need_resched())
				schedule_out_curr_task();

			cpu_relax();
		}
        }

        next = smp_load_acquire(&node->next);
        if (!next) {
                if (cmpxchg(&lock->tail, node, NULL) == node) {
			enable_stealing(lock);
                        goto out;
                }

                for (;;) {
                        next = READ_ONCE(node->next);
                        if (next)
                                break;

			if (need_resched())
				schedule_out_curr_task();

                        cpu_relax();
                }
        }

        /*
         * Notify the very next waiter
         */
        plstatus = xchg_release(&next->lstatus, _RWAQ_MCS_STATUS_LOCKED);
        if (unlikely(plstatus == _RWAQ_MCS_STATUS_PARKED)) {
                wake_up_waiter(next);
        }

     out:
        preempt_enable();
	return 0;
}

static inline void aqm_read_lock_slowpath(struct rw_semaphore *sem)
{
	atomic_long_sub(RWAQM_R_BIAS, &sem->cnts);

	rwmutex_lock(&sem->wait_lock, true);
	atomic_long_add(RWAQM_R_BIAS, &sem->cnts);

	atomic_long_cond_read_acquire(&sem->cnts, !(VAL & RWAQM_W_LOCKED));

	rwmutex_unlock(&sem->wait_lock);
}

void down_read(struct rw_semaphore *sem)
{
	u64 cnts;

	might_sleep();

	cnts = atomic_long_add_return_acquire(RWAQM_R_BIAS, &sem->cnts);
	if (likely(!(cnts & RWAQM_W_WMASK)))
		return;

	aqm_read_lock_slowpath(sem);
}
EXPORT_SYMBOL(down_read);


int __must_check down_read_killable(struct rw_semaphore *sem)
{
	/* XXX: Will handle the EINTR later */
	down_read(sem);
	return 0;
}
EXPORT_SYMBOL(down_read_killable);

int __must_check down_read_interruptible(struct rw_semaphore *sem)
{
	/* XXX: Will handle the EINTR later */
	down_read(sem);
	return 0;
}
EXPORT_SYMBOL(down_read_interruptible);


/*
 * trylock for reading -- returns 1 if successful, 0 if contention
 */
int down_read_trylock(struct rw_semaphore *sem)
{
	u64 cnts;

	might_sleep();

	cnts = atomic_long_read(&sem->cnts);
	if (likely(!(cnts & RWAQM_W_WMASK))) {
		cnts = (u64)atomic_long_add_return_acquire(RWAQM_R_BIAS,
							   &sem->cnts);
		if (likely(!(cnts & RWAQM_W_WMASK)))
			return 1;
		atomic_long_sub(RWAQM_R_BIAS, &sem->cnts);
	}
	return 0;
}
EXPORT_SYMBOL(down_read_trylock);


static inline void aqm_write_lock_slowpath(struct rw_semaphore *sem)
{
	rwmutex_lock(&sem->wait_lock, false);

	if (!atomic_long_read(&sem->cnts) &&
	    (atomic_long_cmpxchg_acquire(&sem->cnts, 0, RWAQM_W_LOCKED) == 0))
		goto unlock;

	/* atomic_long_add(RWAQM_W_WAITING, &sem->cnts); */

	do {
		/* atomic_long_cond_read_acquire(&sem->cnts, VAL == RWAQM_W_WAITING); */
		atomic_long_cond_read_acquire(&sem->cnts, VAL == 0);
	} while (atomic_long_cmpxchg_relaxed(&sem->cnts, 0,
					     RWAQM_W_LOCKED) != 0);
     unlock:
	rwmutex_unlock(&sem->wait_lock);
}
/*
 * lock for writing
 */
void down_write(struct rw_semaphore *sem)
{
	might_sleep();

	if (atomic_long_cmpxchg_acquire(&sem->cnts, 0, RWAQM_W_LOCKED) == 0)
		return;

	aqm_write_lock_slowpath(sem);
}
EXPORT_SYMBOL(down_write);

int __must_check down_write_killable(struct rw_semaphore *sem)
{
	down_write(sem);
	return 0;
}
EXPORT_SYMBOL(down_write_killable);

/*
 * trylock for writing -- returns 1 if successful, 0 if contention
 */
int down_write_trylock(struct rw_semaphore *sem)
{
	u64 cnts;

	might_sleep();

	cnts = atomic_long_read(&sem->cnts);
	if (unlikely(cnts))
		return 0;

	return likely(atomic_long_cmpxchg_acquire(&sem->cnts,
					cnts, cnts | RWAQM_W_LOCKED) == cnts);
}
EXPORT_SYMBOL(down_write_trylock);

/*
 * release a read lock
 */
void up_read(struct rw_semaphore *sem)
{
	(void)atomic_long_sub_return_release(RWAQM_R_BIAS, &sem->cnts);
}
EXPORT_SYMBOL(up_read);

/*
 * release a write lock
 */
void up_write(struct rw_semaphore *sem)
{
	smp_store_release(&sem->wlocked, 0);
}
EXPORT_SYMBOL(up_write);


/*
 * downgrade write lock to read lock
 */
void downgrade_write(struct rw_semaphore *sem)
{
	/*
	 * Two ways to do it:
	 * 1) lock the cacheline and then do it
	 * 2) first increment it by the value  then write wlocked to 0
	 */
	atomic_long_add(RWAQM_R_BIAS, &sem->cnts);
	up_write(sem);
	smp_mb__after_atomic();
}
EXPORT_SYMBOL(downgrade_write);

void __init_rwsem(struct rw_semaphore *sem, const char *name,
		  struct lock_class_key *key)
{
	atomic_long_set(&sem->cnts, RWAQM_UNLOCKED_VALUE);
	__rwmutex_init(&sem->wait_lock);
#ifdef USE_GLOBAL_RDTABLE
	sem->skt_readers = NULL;
	sem->cpu_readers = NULL;
#endif
}
EXPORT_SYMBOL(__init_rwsem);
