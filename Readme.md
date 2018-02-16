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

Updates in before_commit_* will be applied, but will not trigger any 
\_commit\_* calls

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

---------------
consider this use case:
insert/flush/update/commit (or /flush/delete/commit)

Should only insert be called on this object?

Right now, insert and update are called. This means that update code
may need to verify that its properties were not actually changed.

On the other hand, what if client code relies on changes after flush
calling update? I guess insert could conditionally call update()
if such a condition is detected?

Which is more likely? What is expected behavior? What will introduce 
less bugs?

Right now, I'm leaving it as is - insert, update and delete may all
be called. This may change.

-----------
