commit_mixin allows computation to be deferred until commit time.
It also allows for objects to take action if a commit *fails*.

before_commit_* will always fire, and either after_commit_* or failed_commit_*
will fire, assuming two conditions are met.

1. You handle your own exceptions in your \*\_commit_from\_\* handlers.
2. You are using sqlalchemy's recommended transaction semantics
(commit/rollback).

Updates in before_commit_* will be applied, but will not trigger any 
\_commit\_* calls

session.nested_transaction is not currently supported.