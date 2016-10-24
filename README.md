YouTrack Kanban Metrics
=======================
Provides Kanban Metrics for YouTrack
- cycle time
- histogram chart
- percentile chart
- control chart

usage
-----
usage: main.py [-h] [-v] --username USERNAME --password PASSWORD
               [--cachedir CACHEDIR] [--cacheage CACHEAGE]
               [--historyage HISTORYAGE] [--historyfrom HISTORYFROM]
               [--chart_log] [--savechart]
               project {histogram,control,metrics,basic,percentile}

positional arguments:
  project               the project to calculate statistics for
  {histogram,control,metrics,basic,percentile}

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         print status messages to stdout more verbose
  --username USERNAME   username for login
  --password PASSWORD   password for login
  --cachedir CACHEDIR   directory to cache results
  --cacheage CACHEAGE   days before updating cache
  --historyage HISTORYAGE
                        how many days to fetch (from now)
  --historyfrom HISTORYFROM
                        where to start fetching (instead of "now")
  --chart_log           days before updating cache
  --savechart           save chart to file instead of showing it
