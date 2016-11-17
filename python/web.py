import os

import flask
from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.resources import INLINE
from bokeh.util.string import encode_utf8
from flask import render_template
from flask import session
from flask import url_for, request
from flask_login import LoginManager
from werkzeug.utils import redirect

from youtrack.kanban_metrics import KanbanAwareYouTrackConnection

app = flask.Flask(__name__)

project_keys = {
    'backend': ('BACKEND',),
    'semantic': ('SEMANTIC',),
    'mobile': ('MOBILE', 'GP', 'MSDK')
}

youtrack = {}


def control_chart(issues, projects, chart_log = False):
    from bokeh.plotting import figure
    x_resolved_date = [issue.resolved_date for issue in issues]
    y_cycletimes = [issue.cycle_time.days for issue in issues]

    figure_arguments = {'x_axis_label': 'Resolved Date', 'y_axis_label': 'Cycle Time [days]',
                        'x_axis_type': "datetime", 'title': 'Control Chart %s' % str(projects)}

    if chart_log:
        control_chart_figure = figure(y_axis_type="log", **figure_arguments)
    else:
        control_chart_figure = figure(**figure_arguments)
    control_chart_figure.circle(x_resolved_date, y_cycletimes)

    return control_chart_figure


def getitem(obj, item, default):
    if item not in obj:
        return default
    else:
        return obj[item]


@app.route('/')
def index():
    if not session.get('logged_in'):
        return render_template('login.html')
    return redirect(url_for('projects_metrics'))


@app.route('/login', methods=['POST'])
def login():
    youtrack['connection'] = KanbanAwareYouTrackConnection('https://tickets.i.gini.net', request.form['username'],
                                                        request.form['password'])
    session['logged_in'] = True
    return redirect(url_for('projects_metrics'))


@app.route('/projects')
def projects_metrics():
    # Grab the inputs arguments from the URL
    args = flask.request.args

    # Get all the form arguments in the url with defaults
    projects = project_keys[getitem(args, 'project', 'mobile')]
    _from = int(getitem(args, '_from', 0))
    to = int(getitem(args, 'to', 10))

    issues = []
    for project in projects:
        issues.extend(youtrack['connection'].get_cycle_time_issues(project, 1000,
                                           history_range=('2016-11-01', '2016-10-01')))

    fig = control_chart(issues, projects)

    js_resources = INLINE.render_js()
    css_resources = INLINE.render_css()

    script, div = components(fig)
    html = flask.render_template(
        'single_project.html',
        plot_script=script,
        plot_div=div,
        js_resources=js_resources,
        css_resources=css_resources,
        project=getitem(args, 'project', 'mobile'),
        _from=_from,
        to=to
    )
    return encode_utf8(html)


if __name__ == "__main__":
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    print(__doc__)
    app.secret_key = os.urandom(12)
    app.run()
