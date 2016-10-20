# coding=UTF-8

import datetime
import os
import unittest
from functools import partial

from youtrack import IssueChange, ChangeField
from youtrack.connection import Connection

username = os.environ['username']
password = os.environ['password']


def state_field(field):
    return field.name == 'State'


def has_state_changes(change):
    return len(filter(state_field, change.fields)) > 0


def has_old_value(value, change):
    for field in filter(state_field, change.fields):
        if value in field.old_value:
            return True
    return False


def has_new_value(value, change):
    for field in filter(state_field, change.fields):
        if value in field.new_value:
            return True
    return False


class CycleTimeAwareIssue(object):
    def __init__(self, issue_id, history_provider=None):
        self.issue_id = issue_id
        self.history_provider = history_provider
        self.changes = self.history_provider.retrieve_changes(self)
        self._init_transition_stages()

    def _init_transition_stages(self):
        self.cycle_time_start = None
        self.cycle_time_end = None
        self.cycle_time = None
        state_changes = filter(has_state_changes, self.changes)

        if state_changes:
            open_state_changes = filter(partial(has_new_value, 'In Progress'), state_changes) or \
                                 filter(partial(has_new_value, 'Review'), state_changes) or \
                                 filter(partial(has_old_value, 'In Progress'), state_changes)
        if len(open_state_changes) > 0:
            self.cycle_time_start = datetime.datetime.fromtimestamp(
                open_state_changes[0].updated / 1000.0)

        complete_state_changes = filter(partial(has_new_value, 'Complete'), state_changes) or \
                                 filter(partial(has_new_value, 'Verified'), state_changes)
        if len(complete_state_changes) == 1:
            self.cycle_time_end = datetime.datetime.fromtimestamp(
                complete_state_changes[0].updated / 1000.0)

        if self.cycle_time_start and self.cycle_time_end:
            self.cycle_time = self.cycle_time_end - self.cycle_time_start

    def __str__(self):
        return '[%(issue_id)s], started: %(cycle_time_start)s, finished: %(cycle_time_end)s, cycle time: %(cycle_time)s' % self.__dict__


def init_changes():
    open_issue_change = IssueChange()
    open_issue_change.updated = 1362960471944
    change_field = ChangeField()
    change_field.name = 'State'
    change_field.old_value = ('Open',)
    change_field.new_value = ('In Progress',)
    open_issue_change.fields.append(change_field)
    complete_issue_change = IssueChange()
    complete_issue_change.updated = 1472861471944
    change_field = ChangeField()
    change_field.name = 'State'
    change_field.old_value = ('In Progress',)
    change_field.new_value = ('Complete',)
    complete_issue_change.fields.append(change_field)
    changes = (open_issue_change, complete_issue_change)
    return changes


class TestProvider(object):
    def retrieve_changes(self, issue):
        return init_changes()


class YoutrackProvider(object):
    def __init__(self, youtrack):
        self.youtrack = youtrack

    def retrieve_changes(self, issue):
        return self.youtrack.get_changes_for_issue(issue.issue_id)


class TestCalculateCycleTime(unittest.TestCase):
    def test_get_cylce_time_for_issue(self):
        issue = CycleTimeAwareIssue('BACKEND-671', TestProvider())
        self.assertEqual(1272, issue.cycle_time.days)

    def test_cycle_time_from_issue_changes(self):
        changes = init_changes()

        state_changes = filter(has_state_changes, changes)
        self.assertEqual(2, len(state_changes))

        open_state_changes = filter(partial(has_new_value, 'In Progress'), state_changes)
        self.assertEqual(1, len(open_state_changes))

        open_state_time = open_state_changes[0].updated

        open_state_datetime = datetime.datetime.fromtimestamp(open_state_time / 1000.0)
        self.assertEqual(2013, open_state_datetime.year)
        self.assertEqual(3, open_state_datetime.month)
        self.assertEqual(11, open_state_datetime.day)

        open_state_changes = filter(partial(has_new_value, 'Complete'), state_changes)
        self.assertEqual(1, len(open_state_changes))

        complete_state_time = open_state_changes[0].updated
        complete_state_datetime = datetime.datetime.fromtimestamp(complete_state_time / 1000.0)
        self.assertEqual(2016, complete_state_datetime.year)
        self.assertEqual(9, complete_state_datetime.month)
        self.assertEqual(3, complete_state_datetime.day)

        self.assertEqual(datetime.timedelta(1272, 3800), complete_state_datetime - open_state_datetime)

    def test_live_cylce_time_for_issues(self):
        yt = Connection('https://tickets.i.gini.net', username, password)
        print 'connected to [%s]' % yt.baseUrl
        all_backend_issues = yt.getIssues('Backend', 'state:resolved', 0, 1000)
        print 'found %d issues' % len(all_backend_issues)
        cycle_time_issues = filter(lambda issue: issue.cycle_time is not None,
                                   [CycleTimeAwareIssue(backend_issue.id, YoutrackProvider(yt)) for backend_issue in
                                    all_backend_issues])
        print 'found %d issues with cycle times' % len(cycle_time_issues)
        print map(str, cycle_time_issues)

    def te_st_live_get_cycle_time(self):
        yt = Connection('https://tickets.i.gini.net', username, password)
        print 'connected to [%s]' % yt.baseUrl
        issue = CycleTimeAwareIssue('BACKEND-671', YoutrackProvider(yt))
        self.assertEqual(7, issue.cycle_time.days)

    def t_est_live(self):
        yt = Connection('https://tickets.i.gini.net', username, password)
        print 'connected to [%s]' % yt.baseUrl
        all_backend_issues = yt.getIssues('Backend', 'state:complete', 0, 1)
        print 'found %d issues' % len(all_backend_issues)
        changes = yt.get_changes_for_issue(all_backend_issues[0].id)

        state_changes = filter(has_state_changes, changes)
        self.assertEqual(4, len(state_changes))

        open_state_changes = filter(partial(has_new_value, 'In Progress'), state_changes)
        self.assertEqual(1, len(open_state_changes))

        open_state_time = open_state_changes[0].updated

        open_state_datetime = datetime.datetime.fromtimestamp(open_state_time / 1000.0)
        self.assertEqual(2016, open_state_datetime.year)
        self.assertEqual(7, open_state_datetime.month)
        self.assertEqual(6, open_state_datetime.day)

        complete_state_changes = filter(partial(has_new_value, 'Complete'), state_changes)
        self.assertEqual(1, len(complete_state_changes))

        complete_state_time = complete_state_changes[0].updated
        complete_state_datetime = datetime.datetime.fromtimestamp(complete_state_time / 1000.0)
        self.assertEqual(2016, complete_state_datetime.year)
        self.assertEqual(7, complete_state_datetime.month)
        self.assertEqual(13, complete_state_datetime.day)

        self.assertEqual(datetime.timedelta(7, 3875, 903000), complete_state_datetime - open_state_datetime)
