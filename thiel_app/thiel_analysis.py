

''' Create a simple real/sim data correlation dashboard.

Use the ``bokeh serve`` command to run the example by executing:

    bokeh serve thiel.py

at your command prompt. Then navigate to the URL

    http://localhost:5006

'''
import px4tools
import numpy as np
import math
import io
import os
import sys
import errno
from plotting import DataPlot
from functools import lru_cache
from os.path import dirname, join
from bokeh.io import output_file, show
from bokeh.models.widgets import FileInput
from bokeh.models.widgets import Paragraph
from bokeh.models import CheckboxGroup
from bokeh.models import RadioButtonGroup
from bokeh.models import Range1d
from bokeh.server.server import Server
from bokeh.themes import Theme
from bokeh.application.handlers import DirectoryHandler


import time
import copy
from bokeh.models import Div


import pandas as pd
import argparse

from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, PreText, Select
from bokeh.plotting import figure

DATA_DIR = join(dirname(__file__), 'datalogs')

DEFAULT_FIELDS = ['XY', 'LatLon', 'VxVy']

simname = 'airtonomysim.csv'
realname = 'airtonomyreal.csv'
sim_polarity = 1  # determines if we should reverse the Y data
real_polarity = 1
simx_offset = 0
realx_offset = 0
read_file = True
reverse_sim_data = False
reverse_real_data = False
new_data = True


@lru_cache()
def load_data_sim(simname):
    fname = join(DATA_DIR, simname)
    data = pd.read_csv(fname)
    dfsim = pd.DataFrame(data)
    return dfsim

@lru_cache()
def load_data_real(realname):
    fname = join(DATA_DIR, realname)
    data = pd.read_csv(fname)
 #   select_data.to_numpy()  # convert to a numpy array
    dfreal = pd.DataFrame(data)
    return dfreal


@lru_cache()
def get_data(simname,realname):
    global select_data
    dfsim = load_data_sim(simname)
    dfreal = load_data_real(realname)
    data = pd.concat([dfsim, dfreal], axis=1)
    data = data.dropna()   # remove missing values
    sim_mean = data.simy.mean()  # get the average
    real_mean = data.realy.mean()
    mean_diff = sim_mean - real_mean 
    data.realy = data.realy + mean_diff # normalize the two
    data['simy'] = data.simy
    data['simx'] = data.simx
    data['realy'] = data.realy
    data['realx'] = data.realx
    select_data=np.asarray(data)  # convert to an array for real selection line
#    original_data = copy.deepcopy(data)
    return data

# set up widgets

stats = PreText(text='Thiel Coefficient', width=500)
datatype = Select(value='XY', options=DEFAULT_FIELDS)

# set up plots

simsource = ColumnDataSource(data = dict(simx=[],simy=[]))
simsource_static = ColumnDataSource(data = dict(simx=[],simy=[]))
realsource = ColumnDataSource(data = dict(realx=[],realy=[]))
realsource_static = ColumnDataSource(data = dict(realx=[],realy=[]))

realtools = 'xpan,wheel_zoom,xbox_select,reset'
simtools = 'xpan,wheel_zoom,reset'

ts1 = figure(plot_width=900, plot_height=200, tools=realtools, x_axis_type='linear', active_drag="xbox_select")
ts1.line('simx', 'simy', source=simsource, line_width=2)
ts1.circle('simx', 'simy', size=1, source=simsource_static, color=None, selection_color="orange")

ts2 = figure(plot_width=900, plot_height=200, tools=simtools, x_axis_type='linear')
# to adjust ranges, add something like this: x_range=Range1d(0, 1000), y_range = None,
# ts2.x_range = ts1.x_range
ts2.line('realx', 'realy', source=realsource, line_width=2, legend_label="Real data")
ts2.circle('realx', 'realy', size=1, source=realsource_static, color="orange",legend_label="Simulated data")

# set up callbacks

def sim_change(attrname, old, new):
    real.options = nix(new, DEFAULT_FIELDS)
    update()

def update(selected=None):
    global read_file, reverse_sim_data, reverse_real_data, new_data, simsource, simsource_static, realsource, realsource_static,original_data, data, data_static, new_data, select_data, select_datadf
    if (read_file):
        original_data = get_data(simname, realname)
        data = copy.deepcopy(original_data)
        data_static = copy.deepcopy(original_data)
        read_file = False
    print("Sim offset", simx_offset)
    print("Real offset", realx_offset)
    if reverse_sim_data:
        data[['simy']] = sim_polarity * original_data[['simy']]  # reverse data if necessary
        data_static[['simy']] = sim_polarity * original_data[['simy']]  # reverse data if necessary
        simsource.data = data
        simsource_static.data = data_static
        simmax = round(max(data[['simy']].values)[0])  # reset the axis scales as appopriate (auto scaling doesn't work)
        simmin = round(min(data[['simy']].values)[0])
        ts1.y_range.start = simmin - abs((simmax-simmin)/10)
        ts1.y_range.end = simmax + abs((simmax-simmin)/10)
        reverse_sim_data = False
    if reverse_real_data:
        data[['realy']] = real_polarity * original_data[['realy']]
        data_static[['realy']] = real_polarity * original_data[['realy']]
        realsource.data = data
        select_datadf[['realy']] = -1 * select_datadf[['realy']]
        realsource_static.data = select_datadf
        realmax = round(max(data[['realy']].values)[0])
        realmin = round(min(data[['realy']].values)[0])
        ts2.y_range.start = realmin - abs((realmax-realmin)/10)
        ts2.y_range.end = realmax + abs((realmax-realmin)/10)
        reverse_real_data = False
    if new_data:
        simsource.data = data[['simx', 'simy','realx','realy']]
        simsource_static.data = data_static[['simx', 'simy','realx','realy']]
        realsource.data = data[['simx', 'simy','realx','realy']]
        select_datadf = pd.DataFrame({'realx': select_data[:, 2], 'realy': select_data[:, 3]})  # convert back to a pandas dataframe     
        realsource_static.data = select_datadf
        new_data = False
#    select_data = copy.deepcopy(tempdata)
    ts1.title.text, ts2.title.text = 'Sim', 'Real'

def upload_new_data_sim(attr, old, new):
    global simname
    decoded = b64decode(new)
    simname = io.BytesIO(decoded)
    update()

def upload_new_data_real(attr, old, new):
    global realname
    decoded = b64decode(new)
    realname = io.BytesIO(decoded)
    update()

def update_stats(data):
    real = np.array(data['realy'])
    sim = np.array(data['simy'])
    sum1 = 0
    sum2 = 0
    sum3 = 0
    for n in range(len(real)):
        sum1 = sum1 + (real[int(n)]-sim[int(n)])**2
        sum2 = sum2 + real[int(n)]**2
        sum3 = sum3 + sim[int(n)]**2
    sum1 = 1/len(real) * sum1
    sum2 = 1/len(real) * sum2
    sum3 = 1/len(real) * sum3
    sum1 = math.sqrt(sum1)
    sum2 = math.sqrt(sum2)
    sum3 = math.sqrt(sum3)
    TIC = sum1/(sum2 + sum3)
    stats.text = 'Thiel coefficient: ' + str(round(TIC,3))

datatype.on_change('value', sim_change)

def simselection_change(attrname, old, new):
    global data_static, new_data, realx_offset, realsource_static,select_data
    selected = simsource_static.selected.indices
    if selected:
        seldata = data.iloc[selected, :]
        sorted_data = seldata.sort_values(by=['simx'])
        start = int(sorted_data.values[0][0])
        print("Start =", start)
    if (len(seldata['simx']) != 0):
        for x in range(len(select_data)):
            select_data[x][2] = 0    #zero out the data
            select_data[x][3] = 0
        for x in range(start, (start+len(sorted_data['simx'])-1)):
            tempx = int(sorted_data['realx'][x] + realx_offset - simx_offset)
            select_data[tempx][2] = realsource.data['realx'][tempx]
            select_data[tempx][3] = realsource.data['realy'][tempx]
        update_stats(seldata)
    new_data = True
    update()

def reverse_sim():
    global sim_polarity, reverse_sim_data
    if (sim_reverse_button.active == 1): sim_polarity = -1
    else: sim_polarity = 1
    reverse_sim_data = True
    update()

def reverse_real():
    global real_polarity, reverse_real_data
    if (real_reverse_button.active == 1): real_polarity = -1
    else: real_polarity = 1
    reverse_real_data = True
    update()

def change_sim_scale(shift):
    global simx_offset, new_data
    simx_offset = shift
    new_data = True
    update()

def change_real_scale(shift):
    global realx_offset, new_data
    realx_offset = shift
    new_data = True
    update()
 

def startserver(doc):
    file_input = FileInput(accept=".ulg, .csv")
    file_input.on_change('value', upload_new_data_sim)
    file_input2 = FileInput(accept=".ulg, .csv")
    file_input2.on_change('value', upload_new_data_real)

    intro_text = Div(text="""<H2>Sim/Real Thiel Coefficient Calculator</H2>""",width=500, height=100, align="center")
    sim_upload_text = Paragraph(text="Upload a simulator datalog:",width=500, height=15)
    real_upload_text = Paragraph(text="Upload a corresponding real-world datalog:",width=500, height=15)
    #checkbox_group = CheckboxGroup(labels=["x", "y", "vx","vy","lat","lon"], active=[0, 1])

    sim_reverse_button = RadioButtonGroup(
            labels=["Sim Default", "Reversed"], active=0)
    sim_reverse_button.on_change('active', lambda attr, old, new: reverse_sim())
    real_reverse_button = RadioButtonGroup(
            labels=["Real Default", "Reversed"], active=0)
    real_reverse_button.on_change('active', lambda attr, old, new: reverse_real())

    simsource_static.selected.on_change('indices', simselection_change)


    # The below are in case you want to see the x axis range change as you pan. Poorly documented elsewhere!
    #ts1.x_range.on_change('end', lambda attr, old, new: print ("TS1 X range = ", ts1.x_range.start, ts1.x_range.end))
    #ts2.x_range.on_change('end', lambda attr, old, new: print ("TS2 X range = ", ts2.x_range.start, ts2.x_range.end))

    ts1.x_range.on_change('end', lambda attr, old, new: change_sim_scale(ts1.x_range.start))
    ts2.x_range.on_change('end', lambda attr, old, new: change_real_scale(ts2.x_range.start))

    # set up layout
    widgets = column(datatype,stats)
    sim_button = column(sim_reverse_button)
    real_button = column(real_reverse_button)
    main_row = row(widgets)
    series = column(ts1, sim_button, ts2, real_button)
    layout = column(main_row, series)

    # initialize
    update()
    doc.add_root(intro_text)

    doc.add_root(sim_upload_text)
    doc.add_root(file_input)
    doc.add_root(real_upload_text)
    doc.add_root(file_input2)
    doc.add_root(layout)
    doc.title = "Flight data"


    # horizonal marker line at 1
    data_span = Span(location=1,
                     dimension='width', line_color='black',
                     line_alpha=0.5, line_width=1.5)
    p.add_layout(data_span)

    data_plot.set_use_time_formatter(False)
    data_plot.finalize()
 #   return data_plot

