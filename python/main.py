#!/usr/bin/env python
import argparse
import datetime
import logging
import math
import sys

import pyfscache

from youtrack.kanban_metrics import KanbanAwareYouTrackConnection


def to_date_fetch_query(datetime_value):
    return datetime_value.strftime('%Y-%m-%d')


def main(arguments):
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    cache = pyfscache.FSCache(arguments.cachedir, days=arguments.cacheage)

    yt = KanbanAwareYouTrackConnection('https://tickets.i.gini.net', arguments.username, arguments.password, cache)
    now = to_date_fetch_query(datetime.datetime.now())
    history = to_date_fetch_query(datetime.datetime.now() - datetime.timedelta(days=arguments.historyage))
    issues = yt.get_cycle_time_issues(arguments.project, 1000, history_range=(now, history))

    metrics(issues)

    if arguments.chart == 'histogram':
        histogram(arguments, history, issues, now)
    elif arguments.chart == 'control':
        control_chart(arguments, history, issues, now)


def control_chart(args, history, issues, now):
    import matplotlib.pyplot as plt
    if args.chart_log:
        plt.yscale('log')
    axis = plt.subplot()
    x_resolved_date = [issue.cycle_time_end.toordinal() for issue in issues]
    y_cycletimes = [issue.cycle_time.days for issue in issues]
    plt.plot(x_resolved_date, y_cycletimes, 'ro')
    plt.margins(0.1)
    x_ticks = axis.get_xticks()
    x_ticks_labels = [datetime.date.fromordinal(int(x_tick)) for x_tick in x_ticks]
    axis.set_xticklabels(x_ticks_labels, rotation=25)
    plt.axis((min(x_resolved_date), max(x_resolved_date), 0, max(y_cycletimes)))
    plt.xlabel('Resolved Date')
    plt.ylabel('Cycle Time [days]')
    plt.title('Control Chart for [%s] %s' % (args.project, (history, now)))
    plt.show()


def histogram(args, history, issues, now):
    import matplotlib.pyplot as plt
    if args.chart_log:
        plt.yscale('log')
    cycletimes = [issue.cycle_time.days for issue in issues]
    # the histogram of the data
    step = math.ceil(max(cycletimes) / 10.).as_integer_ratio()[0]
    plot_bins = range(min(cycletimes), step * 11, step)
    print plot_bins
    n, bins, patches = plt.hist(cycletimes, bins=plot_bins,
                                facecolor='green',
                                alpha=0.75)
    plt.xticks(plot_bins)
    plt.xlabel('Cycle Time [days]')
    plt.ylabel('Frequency')
    plt.title('Cycle Time Histogram for [%s] %s' % (args.project, (history, now)))
    plt.axis([plot_bins[0], plot_bins[-1], 0, max(n) + 1])
    plt.grid(True)
    plt.show()


def metrics(issues):
    print 'number of issues: %d' % len(issues)
    print 'first issue : %s' % issues[0]
    print 'last issue  : %s' % issues[-1]
    cycletimes = [issue.cycle_time.days for issue in issues]
    import numpy
    median_cycle_time = sorted(cycletimes)[len(cycletimes) // 2]
    max_cycle_time = numpy.max(cycletimes)
    min_cycle_time = numpy.min(cycletimes)
    for issue in issues:
        if median_cycle_time == issue.cycle_time.days:
            print 'median issue: %s' % issue
            break
        if max_cycle_time == issue.cycle_time.days:
            print 'max issue   : %s' % issue
            break
        if min_cycle_time == issue.cycle_time.days:
            print 'min issue   : %s' % issue
            break
    mean_cycle_time = numpy.mean(cycletimes)
    print 'mean cycle time: %d days' % mean_cycle_time
    issue_to_print = [issue for issue in issues]
    for quantile in (10,25,50,75,80,90,95,99):
        quantile_cycle_time = numpy.percentile(cycletimes, quantile)
        print '%d%% percentile: %s days' % (quantile, quantile_cycle_time)
        for issue in issue_to_print:
            if issue.cycle_time.days <=quantile_cycle_time:
                print issue
                issue_to_print.remove(issue)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('project', help='the project to calculate statistics for')
    parser.add_argument('-v', '--verbose', dest='verbose', help='print status messages to stdout more verbose',
                        action='count')
    parser.add_argument('--username', dest='username', required=True, help='username for login')
    parser.add_argument('--password', dest='password', required=True, help='password for login')
    parser.add_argument('--cachedir', dest='cachedir', default='/tmp/', help='directory to cache results')
    parser.add_argument('--cacheage', dest='cacheage', type=int, default=14, help='days before updating cache')
    parser.add_argument('--historyage', dest='historyage', default=90, type=int,
                        help='how many days to fetch (from now)')
    parser.add_argument('--chart_log', dest='chart_log', action='store_true', default=False,
                        help='days before updating cache')

    parser.add_argument('chart', choices=('histogram', 'control', 'metrics'))
    args = parser.parse_args()
    main(args)
