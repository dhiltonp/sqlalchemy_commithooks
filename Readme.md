commit_mixin allows actions to be deferred until commit time.
It also allows for objects to take action if a commit *fails*.

This is useful for maintaining consistency with external systems, for example:

 * sending events
 * s3 synchronization
 * redis queue synchronization

#### Usage Notes

before_commit_* will always fire, and either after_commit_* or failed_commit_*
will fire, assuming two conditions are met.

1. You handle your own exceptions in your \*\_commit_from\_\* handlers.
2. You are using sqlalchemy's recommended transaction semantics
(commit/rollback).

If a mapped class is inserted (flushed), updated (flushed), deleted (flushed)
and then commit is called, all methods will execute.

Updates in before_commit_* will be applied, but will not cascade/trigger any 
\*\_commit\_from\_\* calls.

##### Limitations

commit_mixin cannot solve all problems. As an example, it is not perfectly robust 
against network outages:

    DB.add(mapped_object)
    DB.commit()
      before_commit_from_insert is run, puts an object into s3
      network outage occurs now
      actual commit to DB fails (network outage)
      failed_commit_from_insert is run, fails to remove object from s3
      
For each use case, you must determine what has priority.

Should an notification be sent if the DB commit fails (notification is sent,
then network outage preventing full commit)? Or should an event notification 
possibly not be sent if the commit succeeds (transaction is committed, network 
outage prevents notification)?

#### TODO

* add session.nested_transaction support
* add cascade option
