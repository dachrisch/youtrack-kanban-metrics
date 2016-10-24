#!/usr/bin/env python
import argparse
import datetime
import logging
import math
import sys

import numpy
import pyfscache

from youtrack.kanban_metrics import KanbanAwareYouTrackConnection


def to_date_fetch_query(datetime_value):
    return datetime_value.strftime('%Y-%m-%d')


def main(arguments):
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    cache = pyfscache.FSCache(arguments.cachedir, days=arguments.cacheage)

    yt = KanbanAwareYouTrackConnection('https://tickets.i.gini.net', arguments.username, arguments.password, cache)
    if arguments.historyfrom:
        now = datetime.datetime.strptime(arguments.historyfrom, '%Y-%m-%d')
    else:
        now = datetime.datetime.now()
    then = now - datetime.timedelta(days=arguments.historyage)

    issues = yt.get_cycle_time_issues(arguments.project, 1000,
                                      history_range=(to_date_fetch_query(now), to_date_fetch_query(then)))

    base(issues, now, then)

    chart_title = '[%s] %s' % (arguments.project, (to_date_fetch_query(then), to_date_fetch_query(now)))

    chart_filename = None
    if arguments.savechart:
        chart_filename = '%s_%s-%s.png' % (arguments.project, to_date_fetch_query(then), to_date_fetch_query(now))
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


def percentile(issues, chart_title, chart_file):
    import matplotlib.pyplot as plt
    if args.chart_log:
        plt.yscale('log')

    cycletimes = [issue.cycle_time.days for issue in issues]
    x_axis = (10, 25, 50, 75, 80, 90, 95, 99)
    y_axis = [numpy.percentile(cycletimes, quantile) for quantile in x_axis]

    axis = plt.subplot()
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
    x_resolved_date = [issue.cycle_time_end.toordinal() for issue in issues]
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
    plt.title('Cycle Time Histogram for %s' % chart_title)
    plt.axis([plot_bins[0], plot_bins[-1], 0, max(n) + 1])
    plt.grid(True)
    if chart_file:
        plt.savefig('histogram_%s' % chart_file)
    else:
        plt.show()


def base(issues, now, then):
    timespan = (now - then).days
    print 'timespan: %d days' % timespan
    print 'number of finished issues: %d' % len(issues)
    started_issues = filter(lambda issue: issue.cycle_time_start > then, issues)
    print 'number of started issues: %d' % len(started_issues)
    print 'first issue : %s' % issues[0]
    print 'last issue  : %s' % issues[-1]
    cycletimes = [issue.cycle_time.days for issue in issues]
    median_cycle_time = sorted(cycletimes)[len(cycletimes) // 2]
    max_cycle_time = numpy.max(cycletimes)
    min_cycle_time = numpy.min(cycletimes)
    print 'min issue   : %s' % filter(lambda issue: issue.cycle_time.days == min_cycle_time, issues)[0]
    print 'median issue: %s' % filter(lambda issue: issue.cycle_time.days == median_cycle_time, issues)[0]
    print 'max issue   : %s' % filter(lambda issue: issue.cycle_time.days == max_cycle_time, issues)[0]

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
    parser.add_argument('project', help='the project to calculate statistics for')
    parser.add_argument('-v', '--verbose', dest='verbose', help='print status messages to stdout more verbose',
                        action='count')
    parser.add_argument('--username', dest='username', required=True, help='username for login')
    parser.add_argument('--password', dest='password', required=True, help='password for login')
    parser.add_argument('--cachedir', dest='cachedir', default='/tmp/', help='directory to cache results')
    parser.add_argument('--cacheage', dest='cacheage', type=int, default=14, help='days before updating cache')
    parser.add_argument('--historyage', dest='historyage', default=90, type=int,
                        help='how many days to fetch (from now)')
    parser.add_argument('--historyfrom', dest='historyfrom', help='where to start fetching (instead of "now")')
    parser.add_argument('--chart_log', dest='chart_log', action='store_true', default=False,
                        help='days before updating cache')
    parser.add_argument('--savechart', dest='savechart', action='store_true', default=None,
                        help='save chart to file instead of showing it')

    parser.add_argument('chart', choices=('histogram', 'control', 'metrics', 'basic', 'percentile'))
    args = parser.parse_args()
    main(args)
