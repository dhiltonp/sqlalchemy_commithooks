# Overview

sqlalchemy_commithooks allows actions to be deferred until commit time.
It also allows for objects to take action if a commit *fails*.

This is useful for maintaining consistency with external systems, for example:

 * sending events
 * s3 synchronization
 * redis queue synchronization

sqlalchemy_commithooks requires Python >=3.6. This would be hard (impossible?)
to get around without changing the API or modifying sqlalchemy.

There is no overhead if a commit hook is unused.

## Getting Started

Use sqlalchemy_commithooks.Session instead of sqlalchemy.orm.Session.
SessionMixin is also defined, if you are already subclassing Session:

```python
session = sqlalchemy_commithooks.Session()
```

Add sqlalchemy_commithooks.CommitMixin to your mapped class and use any of 9 hooks:

```python
class Data(Base, sqlalchemy_commithooks.CommitMixin):
    def before_commit_from_insert(self):
        pass
```

The hooks are available for all combinations of (`before`,
`after`, `failed`) and (`insert`, `update`, `delete`).

Simply override methods like `before_commit_from_insert`, `failed_commit_from_insert`,
`after_commit_from_delete` etc.


# Usage Notes

before_commit_* will always fire, and one of after_commit_* or failed_commit_*
will fire, assuming two conditions are met.

1. You handle your own exceptions in your \*\_commit_from\_\* handlers.
2. [You are using sqlalchemy's recommended transaction semantics
(commit/rollback)](http://docs.sqlalchemy.org/en/latest/orm/session_basics.html#when-do-i-construct-a-session-when-do-i-commit-it-and-when-do-i-close-it).

If an object is inserted (flushed), updated (flushed), deleted (flushed)
and then commit is called, insert/update/delete methods will execute (in
that order) even though the object will not persist after the commit.

Updates in before_commit_* will be applied, but will not cascade/trigger any 
\*\_commit\_from\_\* calls.

## Limitations

sqlalchemy_commithooks cannot solve all problems. As an example, it is not
perfectly robust against network outages:

```python
DB.add(mapped_object)
DB.commit()
#  before_commit_from_insert is run, puts an object into s3
#  network outage occurs now
#  actual commit to DB fails (network outage)
#  failed_commit_from_insert is run, fails to remove object from s3
```
      
For each use case, you must determine what has priority.

Should an notification be sent if the DB commit fails (notification is sent,
then network outage preventing full commit)? Or should an event notification
possibly not be sent if the commit succeeds (transaction is committed, network
outage prevents notification)?

## TODO

* add session.nested_transaction support
* add cascade option
* make it easy to see which hooks will run in the debugger
