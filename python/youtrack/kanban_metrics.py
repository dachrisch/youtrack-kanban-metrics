import datetime
import logging
from operator import attrgetter

from connection import Connection


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


# noinspection PyAbstractClass
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


class data:
    @staticmethod
    def repr(obj):
        items = []
        for prop, value in obj.__dict__.items():
            try:
                item = "%s = %r" % (prop, value)
                assert len(item) < 20
            except:
                item = "%s: <%s>" % (prop, value.__class__.__name__)
            items.append(item)

        return "%s(%s)" % (obj.__class__.__name__, ', '.join(items))

    def __init__(self, cls):
        cls.__repr__ = data.repr
        self.cls = cls

    def __call__(self, *args, **kwargs):
        return self.cls(*args, **kwargs)


@data
class StateChange(object):
    def __init__(self, from_state, to_state, updated, duration):
        self.updated = updated
        self.duration = duration
        self.from_state = from_state
        self.to_state = to_state
        self.transition = '%s->%s' % (from_state, to_state)

    def __str__(self):
        return 'StateChange[%(transition)s](updated: %(updated)s, duration: %(duration)s)' % self.__dict__


class CycleTimeAwareIssue(object):
    def __init__(self, issue, history_provider=None):
        self._log = logging.getLogger(self.__class__.__name__)
        self.issue_id = issue.id
        self.created_time = millis_to_datetime(int(issue.created))
        self.history_provider = history_provider
        self.changes = self.history_provider.retrieve_changes(self)
        # self._init_transition_stages()
        self._init_time_in_state()
        self._calculate_cycle_time(
            ('In Progress', 'Review', 'Code Review', 'Analysis', 'Development',
             'Verification', 'Testing | Verification', 'Ready for Code Review'))
        self._log.info(str(self))

    def __getstate__(self):
        state = dict(self.__dict__)
        del state['_log']
        return state

    def __str__(self):
        return '[%(issue_id)s], (created): %(created_time)s, ' \
               '(%(cycle_time_start_source_transition)s): %(cycle_time_start)s, ' \
               '(%(cycle_time_end_source_transition)s): %(cycle_time_end)s, cycle time: %(cycle_time)s' % self.__dict__

    def _init_time_in_state(self):
        self.state_changes = []
        last_updated = self.created_time
        for state_change in filter(has_state_changes, self.changes):
            state_change_field = filter(is_state_field, state_change.fields)[0]
            state_updated = millis_to_datetime(state_change.updated)
            self.state_changes.append(StateChange(state_change_field.old_value[0], state_change_field.new_value[0],
                                                  state_updated, state_updated - last_updated))
            last_updated = state_updated

    def _calculate_cycle_time(self, cycle_time_states):
        self.cycle_time = sum([state_change.duration for state_change in
                               filter(lambda s: s.from_state in cycle_time_states, self.state_changes)],
                              datetime.timedelta())
        forward_sorted_changes = sorted(self.state_changes, key=attrgetter('updated'))
        if not forward_sorted_changes:
            self.cycle_time_start = self.cycle_time_end = self.created_time
            self.cycle_time_start_source_transition =  self.cycle_time_end_source_transition = None
            return

        self.cycle_time_start = forward_sorted_changes[0].updated
        self.cycle_time_start_source_transition = forward_sorted_changes[0].transition
        for state_change in forward_sorted_changes:
            if state_change.to_state in cycle_time_states:
                self.cycle_time_start = state_change.updated
                self.cycle_time_start_source_transition = state_change.transition
                break

        backward_sorted_changes = sorted(self.state_changes, key=attrgetter('updated'), reverse=True)
        self.cycle_time_end = backward_sorted_changes[0].updated
        self.cycle_time_end_source_transition = backward_sorted_changes[0].transition
        for state_change in backward_sorted_changes:
            if state_change.from_state in cycle_time_states:
                self.cycle_time_end = state_change.updated
                self.cycle_time_end_source_transition = state_change.transition
                break

    def time_in_state(self, state):
        return sum(
            [state_change.duration for state_change in filter(lambda s: s.from_state == state, self.state_changes)],
            datetime.timedelta())

    def first_date_in_state(self, state):
        return sorted(filter(lambda s: s.to_state == state, self.state_changes), key=attrgetter('updated'))[0].updated


def is_state_field(field):
    return field.name == 'State'


def has_state_changes(change):
    return len(filter(is_state_field, change.fields)) > 0


def has_old_value(value, change):
    for field in filter(is_state_field, change.fields):
        if field.old_value[0] in value:
            return True
    return False


def has_new_value(value, change):
    for field in filter(is_state_field, change.fields):
        if field.new_value[0] in value:
            return True
    return False


def is_resolved_field(field):
    return field.name == u'resolved'


def has_resolved_value(change):
    for field in filter(is_resolved_field, change.fields):
        if field:
            return True
    return False
