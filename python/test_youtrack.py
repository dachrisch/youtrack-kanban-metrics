#!/usr/bin/env python
# coding=UTF-8

import datetime
import logging
import os
import sys
import unittest
from functools import partial

import numpy
import pyfscache

from youtrack import IssueChange, ChangeField, Issue
from youtrack.connection import Connection
from youtrack.kanban_metrics import YoutrackProvider, ChangesProvider, CycleTimeAwareIssue, has_state_changes, \
    has_new_value, KanbanAwareYouTrackConnection, has_resolved_value, millis_to_datetime

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


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
    change_field = ChangeField()
    change_field.name = 'resolved'
    change_field.old_value = ('',)
    change_field.new_value = (1472861471941,)
    complete_issue_change.fields.append(change_field)
    changes = (open_issue_change, complete_issue_change)
    return changes


class TestProvider(ChangesProvider):
    def retrieve_changes(self, issue):
        return init_changes()


def state_change_field(new_value, old_value):
    field = ChangeField()
    field.new_value = (new_value,)
    field.old_value = (old_value,)
    field.name = 'State'
    return field


class TestCalculateCycleTime(unittest.TestCase):
    def test_get_cylce_time_for_issue(self):
        issue = Issue()
        issue.created = '123'
        issue.id = 'BACKEND-671'
        issue = CycleTimeAwareIssue(issue, TestProvider())
        self.assertEqual(millis_to_datetime(1472861471944) - millis_to_datetime(1362960471944), issue.cycle_time)
        self.assertEqual(datetime.datetime(1970, 1, 1, 1, 0, 0, 123000), issue.created_time)

    def test_logspace(self):
        linear_space = numpy.linspace(1, 100, 4)
        self.assertEqual({1, 34, 67, 100}, set(linear_space))

        log_space = numpy.logspace(0, 2, 4)
        self.assertEqual({1, 4.6415888336127784, 21.544346900318832, 100}, set(log_space))

    def test_issue_in_state_time(self):
        issue = Issue()
        issue.created = '123'
        issue.id = 'BACKEND-671'
        issue = CycleTimeAwareIssue(issue, TestProvider())
        self.assertEqual(issue.time_in_state('Open'), millis_to_datetime(1362960471944) - issue.created_time)
        self.assertEqual(issue.time_in_state('In Progress'),
                         millis_to_datetime(1472861471944) - millis_to_datetime(1362960471944))
        self.assertEqual(issue.time_in_state('Complete'), datetime.timedelta(0))
        self.assertEqual(issue.cycle_time, datetime.timedelta(1272, 3800))

        self.assertEqual(issue.first_date_in_state('In Progress'), millis_to_datetime(1362960471944))

        self.assertEqual(issue.cycle_time_start, millis_to_datetime(1362960471944))
        self.assertEqual(issue.cycle_time_end, millis_to_datetime(1472861471944))

        self.assertEqual(str(issue),
                         '[BACKEND-671], (created): 1970-01-01 01:00:00.123000, '
                         '(Open->In Progress): 2013-03-11 01:07:51.944000, '
                         '(In Progress->Complete): 2016-09-03 02:11:11.944000, cycle time: 1272 days, 1:03:20')

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

    def te_st_live_cylce_time_for_issues_with_cache(self):
        username = os.environ['username']
        password = os.environ['password']

        from tempfile import mkdtemp
        cachedir = mkdtemp()
        cache = pyfscache.FSCache(cachedir, days=14)
        yt = KanbanAwareYouTrackConnection('https://tickets.i.gini.net', username, password, cache)
        print 'connected to [%s]' % yt.baseUrl
        cycle_time_issues = yt.get_cycle_time_issues('Backend', 10)

        print 'found %d issues with cycle times' % len(cycle_time_issues)
        [self.assertIsNotNone(cycle_time_issue.cycle_time) for cycle_time_issue in cycle_time_issues]

    def te_st_live_get_cycle_time(self):
        yt = Connection('https://tickets.i.gini.net', username, password)
        print 'connected to [%s]' % yt.baseUrl
        issue = Issue()
        issue.id = 'BACKEND-671'
        issue.created = '123'
        issue = CycleTimeAwareIssue(issue, YoutrackProvider(yt))
        self.assertEqual(7, issue.cycle_time.days)

    def te_st_live(self):
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

        resolved_state_changes = filter(has_resolved_value, state_changes)
        self.assertEqual(1, len(resolved_state_changes))

        complete_state_time = resolved_state_changes[0].updated
        complete_state_datetime = datetime.datetime.fromtimestamp(complete_state_time / 1000.0)
        self.assertEqual(2016, complete_state_datetime.year)
        self.assertEqual(7, complete_state_datetime.month)
        self.assertEqual(13, complete_state_datetime.day)

        self.assertEqual(datetime.timedelta(7, 3875, 903000), complete_state_datetime - open_state_datetime)
