from contextlib import contextmanager

import pytest
from mock import Mock
from sqlalchemy import Column, Integer
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from . import commit_mixin
from .commit_mixin import _build_add_func, Session


def test_build_add_func_time(monkeypatch):
    session = Mock()
    monkeypatch.setattr(commit_mixin, 'object_session', lambda x: session)
    for time in ['before', 'after', 'failed']:
        f = _build_add_func(time, 'update')
        f(None, None, f'{time}_obj')
    session._add_before_commit_object.assert_called_once()
    assert 'before_obj' == session._add_before_commit_object.call_args[0][0]
    session._add_after_commit_object.assert_called_once()
    assert 'after_obj' == session._add_after_commit_object.call_args[0][0]
    session._add_after_commit_object.assert_called_once()
    assert 'failed_obj' == session._add_failed_commit_object.call_args[0][0]


class TestHookRegistration:
    class Hook(commit_mixin.CommitMixin):
        pass

    def test_one(self, monkeypatch):
        event = Mock()
        monkeypatch.setattr(commit_mixin, 'event', event)
        self.Hook._register_hooks({'before_commit_from_insert'})
        event.listen.assert_called_once()

        e = event.listen.call_args
        cls_, event_, func_ = e[0]
        assert cls_ == self.Hook
        assert event_ == 'after_insert'

    def test_all(self, monkeypatch):
        event = Mock()
        monkeypatch.setattr(commit_mixin, 'event', event)
        hooks = commit_mixin.CommitMixin._lookup_hooks()
        commit_mixin.CommitMixin._register_hooks(hooks)

        assert event.listen.call_count == 9
        for e in event.listen.call_args_list:
            cls_, event_, func_ = e[0]
            assert cls_ == commit_mixin.CommitMixin
            assert event_ in ['after_insert', 'after_update', 'after_delete']


class TestHookLookup:
    class Direct(commit_mixin.CommitMixin):
        def before_commit_from_update(self):
            pass

    class Overridden(Direct):
        def before_commit_from_update(self):
            pass

    class Skipped(Direct):
        pass

    class SkippedSub(Skipped):
        def before_commit_from_insert(self):
            pass

    class X:
        pass

    class Z:
        pass

    class Multiple(X, Direct, Z):
        def before_commit_from_delete(self):
            pass

    def test_direct_inheritance(self):
        assert len(self.Direct._overridden_hooks()) == 1
        assert 'before_commit_from_update' in self.Direct._overridden_hooks()

    def test_overridden_inheritance(self):
        assert len(self.Overridden._overridden_hooks()) == 1
        assert 'before_commit_from_update' in self.Overridden._overridden_hooks()

    def test_skipped_inheritance(self):
        assert len(self.Skipped._overridden_hooks()) == 1
        assert 'before_commit_from_update' in self.Skipped._overridden_hooks()

    def test_skipped_sub(self):
        assert len(self.SkippedSub._overridden_hooks()) == 2
        assert 'before_commit_from_update' in self.SkippedSub._overridden_hooks()
        assert 'before_commit_from_insert' in self.SkippedSub._overridden_hooks()

    def test_multiple_inheritance(self):
        assert len(self.Multiple._overridden_hooks()) == 2
        assert 'before_commit_from_update' in self.Multiple._overridden_hooks()
        assert 'before_commit_from_delete' in self.Multiple._overridden_hooks()



@contextmanager
def _tmp_transaction_patch(session: Session):
    """needed for _do_after_commit"""
    yield session


class TestAddCommitObject:
    class FakeSession(commit_mixin.Session):
        transaction = "transaction"

        @classmethod
        def _register_commit_hooks(cls):
            pass

    def test_add_before_commit_object(self, monkeypatch):
        session = self.FakeSession()
        obj = Mock()
        for type_ in ['delete', 'insert', 'update', 'update']:
            session._add_before_commit_object(obj, type_)
            assert type_ in session._commit_objects.before[obj]

        assert len(session._commit_objects.before[obj]) == 3

    def test_add_after_commit_object(self, monkeypatch):
        session = self.FakeSession()
        obj = Mock()
        for type_ in ['delete', 'delete']:
            session._add_after_commit_object(obj, type_)
            assert type_ in session._commit_objects.after[obj]

        assert len(session._commit_objects.after[obj]) == 1

    def test_do_before_commits(self):
        session = self.FakeSession()
        obj = Mock()

        session._add_before_commit_object(obj, 'insert')
        session._do_before_commits()

        assert len(obj.method_calls) == 1
        assert obj.method_calls[0][0] == 'before_commit_from_insert'

    def test_do_after_commits(self, monkeypatch):
        session = self.FakeSession()
        monkeypatch.setattr(commit_mixin, '_tmp_transaction', _tmp_transaction_patch)
        obj = Mock()

        session._add_after_commit_object(obj, 'insert')
        session._do_after_commits()

        assert len(obj.method_calls) == 1
        assert obj.method_calls[0][0] == 'after_commit_from_insert'

    def test_do_commits_order(self):
        session = self.FakeSession()
        obj = Mock()
        for type_ in ['delete', 'insert', 'update']:
            session._add_before_commit_object(obj, type_)

        session._do_before_commits()
        assert len(obj.method_calls) == 3
        assert obj.method_calls[0][0] == 'before_commit_from_insert'
        assert obj.method_calls[1][0] == 'before_commit_from_update'
        assert obj.method_calls[2][0] == 'before_commit_from_delete'

    def test_do_commits_cleared(self):
        session = self.FakeSession()
        obj = Mock()

        session._add_before_commit_object(obj, 'insert')
        session._do_before_commits()
        assert len(obj.method_calls) == 1

        # calls aren't duplicated
        session._do_before_commits()
        assert len(obj.method_calls) == 1


def test_end_to_end():
    Base = declarative_base()

    class Data(Base, commit_mixin.CommitMixin):
        __tablename__ = "data"
        id = Column(Integer, primary_key=True)

        def __init__(self):
            self.before_commit_counter = 0
            self.after_commit_counter = 0

        def before_commit_from_insert(self):
            self.before_commit_counter += 1

        def after_commit_from_insert(self):
            self.after_commit_counter += 1

    engine = create_engine('sqlite:///:memory:')
    Data.__table__.create(bind=engine)

    SessionMaker = sessionmaker(class_=Session, bind=engine)
    session = SessionMaker()

    data = Data()
    session.add(data)

    session.commit()

    assert data.before_commit_counter == 1
    assert data.after_commit_counter == 1


Base = declarative_base()

class TestQueriesAtCommit:
    class Foo(Base):
        __tablename__ = "foo"
        id = Column(Integer, primary_key=True)

    class Data(Base, commit_mixin.CommitMixin):
        __tablename__ = "data2"
        id = Column(Integer, primary_key=True)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def before_commit_from_insert(self):
            self._sa_instance_state.session.query(TestQueriesAtCommit.Foo).all()

        def after_commit_from_delete(self):
            self._sa_instance_state.session.query(TestQueriesAtCommit.Foo).all()

    def get_session(self):
        engine = create_engine('sqlite:///:memory:')
        self.Foo.__table__.create(bind=engine)
        self.Data.__table__.create(bind=engine)

        SessionMaker = sessionmaker(class_=Session, bind=engine)
        return SessionMaker()

    def test_before_commit(self):
        session = self.get_session()
        session.add(self.Data())
        session.commit()

    def test_after_commit(self):
        session = self.get_session()
        d = self.Data()
        session.add(d)
        session.commit()

        session.delete(d)
        session.commit()


class TestCommitMixinHooks:
    """verify correct behavior with the hooks we have selected"""
    class Data(Base, commit_mixin.CommitMixin):
        __tablename__ = "data"
        id = Column(Integer, primary_key=True)

        def __init__(self, *args, **kwargs):
            self.before_commit_counter = 0
            self.after_commit_counter = 0
            self.failed_commit_counter = 0
            super().__init__(*args, **kwargs)

        def before_commit_from_insert(self):
            self.before_commit_counter += 1

        def after_commit_from_insert(self):
            self.after_commit_counter += 1

        def failed_commit_from_insert(self):
            self.failed_commit_counter += 1

        def assert_never_committed(self):
            assert self.before_commit_counter == 0 and \
                   self.after_commit_counter == 0 and \
                   self.failed_commit_counter == 0

        def assert_regular_commit(self):
            assert self.before_commit_counter == 1 and \
                   self.after_commit_counter == 1 and \
                   self.failed_commit_counter == 0

        def assert_failed_commit(self):
            assert self.before_commit_counter == 1 and \
                   self.after_commit_counter == 0 and \
                   self.failed_commit_counter == 1

    def get_session(self):
        engine = create_engine('sqlite:///:memory:')
        self.Data.__table__.create(bind=engine)

        SessionMaker = sessionmaker(class_=Session, bind=engine)
        return SessionMaker()

    # def test_subtransaction(self):
    #     session = self.get_session()
    #     outer_data = self.Data(id=1)
    #     session.add(outer_data)
    #
    #     session.begin(subtransactions=True)
    #     with pytest.raises(Exception):
    #         bad_flush_data = self.Data(id=1)
    #         session.add(self.Data())
    #         session.commit()
    #     # except
    #     session.rollback()
    #     # flush fails in before_commit hook, skip commit on rollback.
    #     outer_data.assert_never_committed()
    #     bad_flush_data.assert_never_committed()
    #     # end except
    #
    #     session.commit()
    #     outer_data.assert_regular_commit()
    #     bad_flush_data.assert_never_committed()

    def test_nested_bad_flush(self):
        session = self.get_session()
        outer_data = self.Data(id=1)
        session.add(outer_data)

        session.begin_nested()
        with pytest.raises(Exception):
            bad_flush_data = self.Data(id=1)
            session.add(bad_flush_data)
            session.commit()
        # except
        session.rollback()
        # flush fails in before_commit hook, skip commit on rollback.
        outer_data.assert_never_committed()
        bad_flush_data.assert_never_committed()
        # end except

        session.commit()
        outer_data.assert_regular_commit()
        bad_flush_data.assert_never_committed()

    # def test_nested_bad_commit(self, monkeypatch):
    #     session = self.get_session()
    #     outer_data = self.Data()
    #     session.add(outer_data)
    #
    #     session.begin_nested()
    #     with pytest.raises(Exception):
    #         bad_flush_data = self.Data()
    #         session.add(bad_flush_data)
    #         monkeypatch.delattr('sqlalchemy.engine.base.Transaction.commit')
    #         session.commit()
    #     # except
    #     session.rollback()
    #     outer_data.assert_never_committed()
    #     bad_flush_data.assert_failed_commit()
    #     # end except
    #
    #     monkeypatch.undo()
    #     session.commit()
    #     outer_data.assert_regular_commit()
    #     bad_flush_data.assert_failed_commit()

    def test_multiple_good_commits(self):
        session = self.get_session()
        data1 = self.Data()
        session.add(data1)
        session.commit()
        data1.assert_regular_commit()

        data2 = self.Data()
        session.add(data2)
        session.commit()
        data1.assert_regular_commit()
        data2.assert_regular_commit()

    def test_multiple_bad_commits(self, monkeypatch):
        session = self.get_session()

        data1 = self.Data()
        session.add(data1)
        with pytest.raises(AttributeError):
            monkeypatch.delattr('sqlalchemy.engine.base.Transaction.commit')
            session.commit()
        monkeypatch.undo()
        session.rollback()
        data1.assert_failed_commit()

        data2 = self.Data()
        session.add(data2)
        with pytest.raises(AttributeError):
            monkeypatch.delattr('sqlalchemy.engine.base.Transaction.commit')
            session.commit()
        monkeypatch.undo()
        session.rollback()
        data1.assert_failed_commit()
        data2.assert_failed_commit()
