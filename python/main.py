#!/usr/bin/env python
import logging
import os
import sys

import matplotlib.pyplot as plt

from youtrack.kanban_metrics import KanbanAwareYouTrackConnection


def main():
    username = os.environ['username']
    password = os.environ['password']
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    yt = KanbanAwareYouTrackConnection('https://tickets.i.gini.net', username, password)
    project = 'Mobile'
    issues = yt.get_cycle_time_issues(project, 1000)

    cycletimes = [issue.cycle_time.days for issue in issues]
    print cycletimes

    # the histogram of the data
    n, bins, patches = plt.hist(cycletimes, bins=(0, 5, 10, 30, 60, 90, 120, 365, 365 * 2), facecolor='green',
                                alpha=0.75)

    print n

    l = plt.plot(bins, 'r--', linewidth=1)

    plt.xlabel('Cycle Times')
    plt.ylabel('Frequency')
    plt.title('Cycle Time Histogram for [%s]' % project)
    plt.axis([0, 365 * 2, 0, max(n) + 1])
    plt.grid(True)

    plt.show()


main()
