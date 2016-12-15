#!/usr/bin/env python
import argparse
import datetime
import logging
import math
import sys
from collections import Counter
from operator import attrgetter

import numpy

from youtrack.kanban_metrics import KanbanAwareYouTrackConnection


def to_date_fetch_query(datetime_value):
    return datetime_value.strftime('%Y-%m-%d')


def main(arguments):
    if arguments.verbose > 1:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    elif arguments.verbose == 1:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.WARN)

    yt = KanbanAwareYouTrackConnection('https://tickets.i.gini.net', arguments.username, arguments.password)
    if arguments.history_from:
        now = datetime.datetime.strptime(arguments.history_from, '%Y-%m-%d')
    else:
        now = datetime.datetime.now()
    then = now - datetime.timedelta(days=arguments.history_age)

    issues = []
    for project in arguments.projects:
        issues.extend(yt.get_cycle_time_issues(project, 1000,
                                               history_range=(to_date_fetch_query(now), to_date_fetch_query(then))))

    base(issues, now, then)

    chart_title = '%s %s' % (arguments.projects, (to_date_fetch_query(then), to_date_fetch_query(now)))

    chart_filename = None
    if arguments.save_chart:
        chart_filename = '%s_%s-%s.png' % (arguments.projects, to_date_fetch_query(then), to_date_fetch_query(now))
    if arguments.chart == 'histogram':
        histogram(issues, chart_title, chart_filename)
    elif arguments.chart == 'control':
        control_chart(issues, chart_title, chart_filename)
    elif arguments.chart == 'metrics':
        metrics(issues)
    elif arguments.chart == 'basic':
        pass
    elif arguments.chart == 'percentile':
        percentile(issues, chart_title, chart_filename)
    elif arguments.chart == 'states':
        states(issues, chart_title, chart_filename)


def states(issues, chart_title, chart_file):
    class TimedeltaCounter(Counter):
        def __missing__(self, key):
            return datetime.timedelta(0)

    counter = TimedeltaCounter()
    for issue in issues:
        for state_change in issue.state_changes:
            counter[state_change.from_state] = counter[state_change.from_state] + state_change.duration
    labels = []
    values = []
    index = numpy.arange(len(counter.keys()))
    for item in sorted(counter.iteritems(), key=lambda x: x[1]):
        print 'days in [%s] state: %s' % (item[0], item[1].days)
        labels.append(item[0])
        values.append(item[1].days)

    import matplotlib.pyplot as plt
    bar_distance = 4
    fig, ax = plt.subplots()
    fig.subplots_adjust(bottom=.4)
    bars = ax.bar(index * bar_distance + 0.5, values, 1, color='lightyellow')
    autolabel(bars, labels, ax)
    ax.set_xticks(index * bar_distance + 1)
    ax.set_xticklabels(labels, rotation=90)

    ax.set_xlabel('Workflow State')
    ax.set_ylabel('Cumulated Cycle Times [days]')
    ax.set_title('Workflow Step chart for  %s' % chart_title)

    if chart_file:
        plt.savefig('states_%s' % chart_file)
    else:
        plt.show()


def autolabel(rects, labels, ax):
    # Get y-axis height to calculate label_names position from.
    (y_bottom, y_top) = ax.get_ylim()
    y_height = y_top - y_bottom

    for rect in rects:
        height = rect.get_height()
        label = '%d' % (rect.get_height())

        # Fraction of axis height taken up by this rectangle
        p_height = (height / y_height)

        # If we can fit the label_names above the column, do that;
        # otherwise, put it inside the column.
        if p_height > 0.95:
            label_position = height - (y_height * 0.05)
        else:
            label_position = height + (y_height * 0.01)

        ax.text(rect.get_x() + rect.get_width() / 2., label_position,
                label, color='lightgreen', ha='center', va='bottom')


def percentile(issues, chart_title, chart_file):
    import matplotlib.pyplot as plt
    if args.chart_log:
        plt.yscale('log')

    cycletimes = [issue.cycle_time.days for issue in issues]
    x_axis = (10, 25, 50, 75, 80, 90, 95, 99)
    y_axis = [numpy.percentile(cycletimes, quantile) for quantile in x_axis]

    plt.plot(x_axis, y_axis)

    plt.xlabel('Percentile')
    plt.ylabel('Cycle Time [days]')
    plt.title('Percentile chart for  %s' % chart_title)
    plt.grid(True)
    plt.grid(True, which='minor')

    if chart_file:
        plt.savefig('percentile_%s' % chart_file)
    else:
        plt.show()


def control_chart(issues, chart_title, chart_file):
    import matplotlib.pyplot as plt
    if args.chart_log:
        plt.yscale('log')
    axis = plt.subplot()
    x_resolved_date = [issue.resolved_date.toordinal() for issue in issues]
    y_cycletimes = [issue.cycle_time.days for issue in issues]
    plt.plot(x_resolved_date, y_cycletimes, 'ro')

    plt.margins(0.1)
    x_ticks = axis.get_xticks()
    x_ticks_labels = [datetime.date.fromordinal(int(x_tick)) for x_tick in x_ticks]
    axis.set_xticklabels(x_ticks_labels, rotation=25)
    plt.xlabel('Resolved Date')
    plt.ylabel('Cycle Time [days]')
    plt.title('Control Chart for  %s' % chart_title)
    plt.grid(True)
    plt.grid(True, which='minor')

    if chart_file:
        plt.savefig('control_%s' % chart_file)
    else:
        plt.show()


def histogram(issues, chart_title, chart_file):
    import matplotlib.pyplot as plt
    cycletimes = [issue.cycle_time.days for issue in issues]

    if args.chart_log:
        plt.xscale('log')
        plt.grid(True, which='minor')
        plot_bins = numpy.logspace(0, math.ceil(numpy.log10(max(cycletimes))), num=10)
        plot_bins[0] = 0
    else:
        plot_bins = numpy.linspace(0, max(cycletimes), num=10)
        plt.xticks(plot_bins)

    n, bins, patches = plt.hist(cycletimes, bins=plot_bins,
                                facecolor='green',
                                alpha=0.75)
    assert sum(n) == len(cycletimes)
    plt.xlabel('Cycle Time [days]')
    plt.ylabel('Frequency')
    plt.title('Cycle Time Histogram for %s' % chart_title)
    plt.ylim([0, max(n) + 1])
    plt.grid(True)
    if chart_file:
        plt.savefig('histogram_%s' % chart_file)
    else:
        plt.show()


def base(issues, now, then):
    timespan = (now - then).days
    print 'oldest issue  : %s' % min(issues, key=attrgetter('resolved_date'))
    print 'youngest issue: %s' % max(issues, key=attrgetter('resolved_date'))
    cycletimes = [issue.cycle_time.days for issue in issues]
    print 'min issue     : %s' % min(issues, key=attrgetter('cycle_time.days'))
    print 'median issue  : %s' % sorted(issues, key=attrgetter('cycle_time.days'))[len(issues) // 2]
    print 'max issue     : %s' % max(issues, key=attrgetter('cycle_time.days'))

    print 'timespan (%s - %s): %d days' % (now, then, timespan)
    print 'number of finished issues: %d' % len(issues)
    started_issues = filter(lambda issue: issue.cycle_time_start > then, issues)
    print 'number of started issues: %d' % len(started_issues)

    mean_cycle_time = numpy.mean(cycletimes)
    print 'mean cycle time: %d days' % mean_cycle_time
    print 'mean WiP: %.2f items' % (len(issues) / float(timespan) * mean_cycle_time)
    print 'pull rate: %.2f issues per week' % (len(started_issues) / float(timespan) * 7)


def metrics(issues):
    cycletimes = [issue.cycle_time.days for issue in issues]
    issue_to_print = [issue for issue in issues]
    for quantile in (10, 25, 50, 75, 80, 90, 95, 99):
        quantile_cycle_time = numpy.percentile(cycletimes, quantile)
        print '%d%% percentile: %s days' % (quantile, quantile_cycle_time)
        for issue in issue_to_print:
            if issue.cycle_time.days <= quantile_cycle_time:
                print issue
                issue_to_print.remove(issue)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('projects', nargs='+', help='the project to calculate statistics for')
    parser.add_argument('-v', '--verbose', dest='verbose', help='print status messages to stdout more verbose',
                        action='count')
    parser.add_argument('--username', dest='username', required=True, help='username for login')
    parser.add_argument('--password', dest='password', required=True, help='password for login')
    parser.add_argument('-a', '--history_age', dest='history_age', default=90, type=int,
                        help='how many days to fetch (from now)')
    parser.add_argument('--history_from', dest='history_from', help='where to start fetching (instead of "now")')
    parser.add_argument('-l', '--chart_log', dest='chart_log', action='store_true', default=False,
                        help='days before updating cache')
    parser.add_argument('--save_chart', dest='save_chart', action='store_true', default=None,
                        help='save chart to file instead of showing it')

    parser.add_argument('chart', choices=('histogram', 'control', 'metrics', 'basic', 'percentile', 'states'),
                        help='metric to calculate')

    args = parser.parse_args()
    main(args)
