from collections import defaultdict
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm import object_session


def _build_add_func(time, action):
    # time = before/after/failed
    method = f'_add_{time}_commit_object'

    def add_object(mapper, connection, object):
        getattr(object_session(object), method)(object, action)

    return add_object


class MappedClass:
    """
    Mixin to any class derived from Base.
    Define methods like "after_commit_from_delete".
    Combinations: (after/before)_commit_from_(insert/update/delete)

    These methods will automatically be called around commit time.
    """

    def __init_subclass__(cls, **kwargs):
        cls._register_hooks(cls._overridden_hooks())
        super().__init_subclass__(**kwargs)

    @classmethod
    def _register_hooks(cls, methods):
        for m in methods:
            tmp = m.split('_')
            time = tmp[0]
            action = tmp[3]
            # after insert/update/delete, we add the object to the session storage
            event.listen(cls, f'after_{action}', _build_add_func(time, action))

    @classmethod
    def _overridden_hooks(cls):
        hooks = cls._lookup_hooks()

        overridden = set()
        for hook in hooks:
            if getattr(MappedClass, hook) != getattr(cls, hook):
                overridden.add(hook)

        return overridden

    @classmethod
    def _lookup_hooks(cls):
        return {m for m in MappedClass.__dict__.keys() if '_commit_from_' in m}

    __err = 'Override to add hooks'

    # we define all methods for IDE autocompletion
    def before_commit_from_insert(self):
        raise NotImplemented(self.__err)

    def before_commit_from_update(self):
        raise NotImplemented(self.__err)

    def before_commit_from_delete(self):
        raise NotImplemented(self.__err)

    def after_commit_from_insert(self):
        raise NotImplemented(self.__err)

    def after_commit_from_update(self):
        raise NotImplemented(self.__err)

    def after_commit_from_delete(self):
        raise NotImplemented(self.__err)

    def failed_commit_from_insert(self):
        raise NotImplemented(self.__err)

    def failed_commit_from_update(self):
        raise NotImplemented(self.__err)

    def failed_commit_from_delete(self):
        raise NotImplemented(self.__err)


class _CommitObjects:
    def __init__(self):
        self.lock = False
        self.before = defaultdict(set)
        self.after = defaultdict(set)
        self.failed = defaultdict(set)


# class _ObjectStack:
#     def __init__(self):
#         self.stack = [_CommitObjects()]
#
#     def push(self):
#         self.stack.append(_CommitObjects())
#
#     def pop(self):
#         tmp = self.stack[-1]
#         self.stack = self.stack[:-1]
#         return tmp
#
#     def peek(self):
#         return self.stack[-1]
#
#     def _add_before_commit_object(self, obj, action):
#         print("adding object")
#         self.stack[-2].before[obj].add(action)
#
#     def _add_after_commit_object(self, obj, action):
#         self.stack[-2].after[obj].add(action)
#
#     def _add_failed_commit_object(self, obj, action):
#         self.stack[-3].failed[obj].add(action)

# make it easier to see which events are going to happen on a given object... somehow...
#  maybe _commit_actions[] on the object?

class Session:
    """
    Session Mixin
    Automatically calls "after_commit" after a successful commit on
    every instance of After_Commit_Insert or After_Commit_Delete

    The mixin must come before sqlalchemy.Session in the inheritance
    list to override __init__, as sqlalchemy.Session doesn't call super().
    The class will raise an exception on insertion if such a condition is
    detected.
    """
    transaction = None

    def __init__(self, *args, **kwargs):
        self._commit_objects = _CommitObjects()
        self._after_failed_commit_active = False
        super().__init__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs):
        cls._register_commit_hooks()
        super().__init_subclass__()

    @classmethod
    def _register_commit_hooks(cls):
        @event.listens_for(cls, "before_commit")
        def before_commit(session: Session):
            # before_commit event occurs before flush inside commit.
            #  flush is where after_insert etc. events occur.
            #  run flush now to guarantee that all objects have
            #  been added to _commit_objects
            session.flush()
            session._after_failed_commit_active = True
            # print("before_commit")
            session._do_before_commits()

        @event.listens_for(cls, "after_commit")
        def after_commit(session: Session):
            # print("after_commit")
            session._after_failed_commit_active = False
            session._do_after_commits()

        @event.listens_for(cls, "after_soft_rollback")
        def after_failed_commit(session: Session, transaction):
            # print("after_failed_commit")
            if session._after_failed_commit_active:
                session._do_failed_commits()
            session._after_failed_commit_active = False

        # @event.listens_for(cls, "after_begin")
        # def transaction_enter(session: Session, transaction):
        #     print("after_begin", transaction)
        #     session._commit_objects.push()
        #     #session._commit_objects.append(_Commit_Objects())

    def _add_before_commit_object(self, obj, action):
        #self._commit_objects._add_before_commit_object(obj, action)
        #print("adding object")
        if not self._commit_objects.lock:
            self._commit_objects.before[obj].add(action)

    def _add_after_commit_object(self, obj, action):
        #self._commit_objects._add_after_commit_object(obj, action)
        if not self._commit_objects.lock:
            self._commit_objects.after[obj].add(action)

    def _add_failed_commit_object(self, obj, action):
        #self._commit_objects._add_failed_commit_object(obj, action)
        if not self._commit_objects.lock:
            self._commit_objects.failed[obj].add(action)

    def _do_before_commits(self):
        self._commit_objects.lock = True
        self._do_commits('before')

    def _do_after_commits(self):
        self._do_commits('after')
        # reset failed commit lists, too
        self._commit_objects.failed.clear()
        self._commit_objects.lock = False

    def _do_failed_commits(self):
        self._do_commits('failed')
        # reset failed commit lists, too
        self._commit_objects.after.clear()
        self._commit_objects.lock = False

    def _do_commits(self, time):
        """
        Executes commit hooks. All inserts are processed first, then
        all updates, then all deletes.
        """
        objects = getattr(self._commit_objects, time)
        for type_ in ['insert', 'update', 'delete']:
            func = f'{time}_commit_from_{type_}'
            for obj in objects:
                if type_ in objects[obj]:
                    getattr(obj, func)()
        objects.clear()

#
# @contextmanager
# def _tmp_transaction(session: Session):
#     """
#     _do_after_commits is called within a transaction.commit()
#     As such, queries cannot be called within it.
#     Fix it by providing a temporary transaction.
#     """
#     #current_transaction = session.transaction
#     #session.transaction = SessionTransaction(session)
#     yield session
#     #session.transaction = current_transaction
