import datetime
import logging
from functools import partial

from youtrack.connection import Connection


class ChangesProvider(object):
    def retrieve_changes(self, issue):
        pass


class YoutrackProvider(ChangesProvider):
    def __init__(self, youtrack):
        self.youtrack = youtrack

    def retrieve_changes(self, issue):
        return self.youtrack.get_changes_for_issue(issue.issue_id)


class ProjectNotFoundException(Exception):
    pass


class KanbanAwareYouTrackConnection(Connection):
    def __init__(self, url, username, password, cache=None, *args, **kwargs):
        Connection.__init__(self, url, username, password, *args, **kwargs)
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.debug('connected to [%s@%s]' % (username, self.baseUrl))
        if cache:
            self.get_cycle_time_issues = cache(self.get_cycle_time_issues)

    def __getstate__(self):
        state = dict(self.__dict__)
        del state['_log']
        del state['get_cycle_time_issues']
        return state

    def get_cycle_time_issues(self, project, items, history_range=None):
        projects = self.getProjects()
        if project not in projects and project not in projects.values():
            raise ProjectNotFoundException('[%s] not in [%s]' % (project, projects))
        if history_range:
            all_issues = self.getIssues(project, 'state:resolved resolved date:%s .. %s' % history_range, 0, items)
            self._log.debug('found %d issues in range %s' % (len(all_issues), history_range))
        else:
            all_issues = self.getIssues(project, 'state:resolved', 0, items)
            self._log.debug('found %d issues' % len(all_issues))
        cycle_time_issues = filter(lambda issue: issue.cycle_time is not None,
                                   [CycleTimeAwareIssue(one_issue, YoutrackProvider(self)) for one_issue in
                                    all_issues])
        self._log.debug('found %d issues with cycle times' % len(cycle_time_issues))
        return cycle_time_issues


def millis_to_datetime(time_str):
    return datetime.datetime.fromtimestamp(time_str / 1000.0)


class CycleTimeAwareIssue(object):
    def __init__(self, issue, history_provider=None):
        self._log = logging.getLogger(self.__class__.__name__)
        self.issue_id = issue.id
        self.created_time = millis_to_datetime(int(issue.created))
        self.history_provider = history_provider
        self.changes = self.history_provider.retrieve_changes(self)
        self._init_transition_stages()

    def __getstate__(self):
        state = dict(self.__dict__)
        del state['_log']
        return state

    def _init_transition_stages(self):
        self.cycle_time_start = None
        self.cycle_time_end = None
        self.cycle_time = None
        state_changes = filter(has_state_changes, self.changes)

        if state_changes:
            open_state_changes = filter(
                partial(has_new_value,
                        ('In Progress', 'Review', 'Analysis', 'Development', 'Verification', 'Testing | Verification')),
                state_changes) or \
                                 filter(partial(has_old_value, 'In Progress'), state_changes)
            if len(open_state_changes) > 0:
                self.cycle_time_start = millis_to_datetime(
                    min([open_state_change.updated for open_state_change in open_state_changes]))
            else:
                first_change_time = millis_to_datetime(min([state_change.updated for state_change in state_changes]))
                self._log.warn("[%s] couldn't find any start time in changes. Using first change time %s" % (
                    self.issue_id, first_change_time))
                self._log.debug('available changes were: [%s]' % state_changes)
                self.cycle_time_start = first_change_time

            complete_state_changes = filter(has_resolved_value, state_changes) or \
                                     filter(partial(has_new_value, ('Obsolete', 'Prod | Final', 'Archived')),
                                            state_changes)
            if len(complete_state_changes) > 0:
                self.cycle_time_end = millis_to_datetime(
                    max([complete_state_change.updated for complete_state_change in complete_state_changes]))
            else:
                self._log.error("[%s] couldn't find any end time in changes [%s]" % (self.issue_id, state_changes))

        if self.cycle_time_start and self.cycle_time_end:
            self.cycle_time = self.cycle_time_end - self.cycle_time_start
        self._log.debug(str(self))

    def __str__(self):
        return '[%(issue_id)s], started: %(cycle_time_start)s, ' \
               'finished: %(cycle_time_end)s, cycle time: %(cycle_time)s' % self.__dict__


def state_field(field):
    return field.name == 'State'


def has_state_changes(change):
    return len(filter(state_field, change.fields)) > 0


def has_old_value(value, change):
    for field in filter(state_field, change.fields):
        if field.old_value[0] in value:
            return True
    return False


def has_new_value(value, change):
    for field in filter(state_field, change.fields):
        if field.new_value[0] in value:
            return True
    return False


def resolved_field(field):
    return field.name == u'resolved'


def has_resolved_value(change):
    for field in filter(resolved_field, change.fields):
        if field:
            return True
    return False
