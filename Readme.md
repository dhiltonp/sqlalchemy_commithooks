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
\*\_commit\_from\_\* calls (**TODO**: add cascade option)

##### Limitations

commit_mixin is not perfect. As an example, it is not perfectly robust 
against network outages.

DB Insert, s3 put in before_commit, (network outage), DB commit <- fails,
s3 delete in failed_commit <- fails.

For each use case, you must determine what has priority.
Should an event notification be sent if the DB commit fails?
Or should an event notification possibly not be sent if the commit succeeds?

#### TODO

add session.nested_transaction support
