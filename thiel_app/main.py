""" This does Thiel analysis plots """

from os import read
import px4tools
import numpy as np
import copy
import math
import io
import os
import sys
import errno
import base64
from db_entry import *
import pickle 



#import thiel_analysis
from bokeh.io import curdoc,output_file, show
from bokeh.models.widgets import Div
from bokeh.layouts import column
from scipy.interpolate import interp1d

from os.path import dirname, join

from config import *
from helper import *
from leaflet import ulog_to_polyline
from bokeh.models import CheckboxGroup
from bokeh.models import RadioButtonGroup
from bokeh.models.widgets import FileInput
from bokeh.models.widgets import Paragraph

import pandas as pd
import argparse

from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, PreText, Select
from bokeh.plotting import figure
from bokeh.server.server import Server
from bokeh.themes import Theme
from bokeh.application.handlers import DirectoryHandler


#pylint: disable=cell-var-from-loop, undefined-loop-variable,

DATA_DIR = join(dirname(__file__), 'datalogs')

sim_polarity = 1  # determines if we should reverse the Y data
real_polarity = 1
simx_offset = 0
realx_offset = 0
read_file = True
reverse_sim_data = False
reverse_real_data = False
new_data = True
read_file_local = False
new_real = False
new_sim = False
keys = []





sim_reverse_button = RadioButtonGroup(
        labels=["Sim Default", "Reversed"], active=0)
sim_reverse_button.on_change('active', lambda attr, old, new: reverse_sim())
real_reverse_button = RadioButtonGroup(
        labels=["Real Default", "Reversed"], active=0)
real_reverse_button.on_change('active', lambda attr, old, new: reverse_real())

# set up widgets

stats = PreText(text='Thiel Coefficient', width=500)



@lru_cache()
def load_data(filename):
    global keys
    fname = join(DATA_DIR, filename)
    ulog = load_ulog_file(fname)
    data = ulog.data_list
    for d in data:
        data_keys = [f.field_name for f in d.field_data]
        data_keys.remove('timestamp')
        keys.append(data_keys)
    cur_dataset = ulog.get_dataset('vehicle_local_position')
    return cur_dataset


@lru_cache()
def get_data(simname,realname, metric):
    global new_real, new_sim, read_file_local, realfile, simfile
    print("Now in get_data")
    dfsim = load_data(simname)
    dfreal = load_data(realname)


    if read_file_local:    # replace the datalogs with local ones
        if new_real:
            print("Loading in a new real log")
            dfreal = realfile
            new_real = False
        if new_sim:
            print("Loading in a new sim log")
            dfsim = simfile
            new_sim = False
 
 
    sim_data = dfsim.data[metric]
    pd_sim = pd.DataFrame(sim_data, columns = ['sim'])
    sim_time = dfsim.data['timestamp']
    pd_time = pd.DataFrame(sim_time, columns = ['time'])
    real_data = dfreal.data[metric]
    pd_real = pd.DataFrame(real_data, columns = ['real'])
    new_data = pd.concat([pd_time,pd_sim, pd_real], axis=1)
    new_data = new_data.dropna()   # remove missing values
    save_settings(config)
    return new_data

    # sim_mean = dfsim.y.mean()  # get the average
    # real_mean = dfreal.y.mean()
    # mean_diff = sim_mean - real_mean 
    # data.realy = data.realy + mean_diff # normalize the two
    # data['sim'] = dfsim.x
    # data['simt'] = dfsim.timestamp
    # data['real'] = dfreal.x
    # data['realt'] = dfreal.timestamp

def update_config():
    config[0] = simname
    config[1] = realname
    config[2] = metric
    config[3] = simdescription
    config[4] = realdescription
    config[5] = 0
    config[6] = 0
    return config

def save_settings(config):
    with open('settings', 'wb') as fp:  #save state
        pickle.dump(config, fp)

def read_settings():
    ''' We're now going to load a bunch of state variables to sync the app back to the last known state. The file "settings" should exist in the main directory

        # config = [simname, realname, metric, simdescription, realdescription]

        The format of the list is as follows:
        config[0] = sim ID
        config[1] = real ID
        config[2] = metric
        config[3] = simdescription
        config[4] = realdesciption
        config[5] = real_reverse_button.active
        config[6] = sim_reverse_button.active

        '''
    global simname, realname, metric, simdescription, realdescription, real_reverse_button, sim_reverse_button
    
    with open ('settings', 'rb') as fp:
        config = pickle.load(fp)
    simname = config[0]
    realname = config[1]
    metric = config[2]
    simdescription = config[3]
    realdescription = config[4]
    # real_reverse_button.active = config[5]
    # sim_reverse_button.active = config[6]
    return config


def update(selected=None):
    global read_file, read_file_local, reverse_sim_data, reverse_real_data, new_data, datalog, original_data, new_data, datasource
    if (read_file or read_file_local):
        print("Fetching new data", simname, realname, metric)
        original_data = get_data(simname, realname, metric)
        datalog = copy.deepcopy(original_data)
        datasource.data = datalog
        read_file = False
        read_file_local = False
    print("Sim offset", simx_offset)
    print("Real offset", realx_offset)
    if reverse_sim_data:
        datalog[['sim']] = sim_polarity * original_data['sim']  # reverse data if necessary
        simmax = round(max(datalog[['sim']].values)[0])  # reset the axis scales as appopriate (auto scaling doesn't work)
        simmin = round(min(datalog[['sim']].values)[0])
        datasource.data = datalog
        reverse_sim_data = False
    if reverse_real_data:
        datalog['real'] = real_polarity * original_data['real']
        realmax = round(max(datalog[['real']].values)[0])
        realmin = round(min(datalog[['real']].values)[0])
        datasource.data = datalog
        reverse_real_data = False
    if new_data:
        datasource.data = datalog
        new_data = False
    config = update_config()
    update_stats(datalog)
    save_settings(config)


def upload_new_data_real(attr, old, new):
    global read_file_local, new_real, realfile, original_data
    read_file_local = True
    new_real = True
    decoded = base64.b64decode(new)
    tempfile = io.BytesIO(decoded)
    tempfile = ULog(tempfile)
    realfile = tempfile.get_dataset('vehicle_local_position')
    print("Uploading new real file")
    update()

def upload_new_data_sim(attr, old, new):
    global read_file_local, new_sim, simfile
    read_file_local = True
    new_sim = True
    decoded = base64.b64decode(new)
    tempfile = io.BytesIO(decoded)
    tempfile = ULog(tempfile)
    simfile = tempfile.get_dataset('vehicle_local_position')
    print("Uploading new sim file")
    update()

def update_stats(data):
    real = np.array(data['real'])
    sim = np.array(data['sim'])
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
    stats.text = 'Thiel coefficient (1 = no correlation, 0 = perfect): ' + str(round(TIC,3))


def reverse_sim():
    global sim_polarity, reverse_sim_data, config
    if (sim_reverse_button.active == 1): 
        sim_polarity = -1
        config[6] = sim_reverse_button.active
    else: sim_polarity = 1
    reverse_sim_data = True
    update()

def reverse_real():
    global real_polarity, reverse_real_data, config
    if (real_reverse_button.active == 1): 
        real_polarity = -1
        config[5] = real_reverse_button.active
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

def sim_change(attrname, old, new):
    global metric, read_file, config
    print("Sim change:", new)
    metric = new
    config[2] = metric # save state
    read_file = True
    update()   

def get_thiel_analysis_plots(simname, realname):
    global datalog, original_data, datasource

    additional_links= "<b><a href='/browse2?search=sim'>Load Simulation Log</a> <p> <a href='/browse2?search=real'>Load Real Log</a></b>" 
    save_settings(config)
    datalog = get_data(simname, realname, metric)
    original_data = copy.deepcopy(datalog)

    datatype = Select(value='x', options=keys[0])

    datatype.on_change('value', sim_change)

    intro_text = Div(text="""<H2>Sim/Real Thiel Coefficient Calculator</H2>""",width=800, height=100, align="center")
    choose_field_text = Paragraph(text="Choose a data field to compare:",width=500, height=15)
    links_text = Div(text="<table width='100%'><tr><td><h3>" + "</h3></td><td align='left'>" + additional_links+"</td></tr></table>")

    datasource = ColumnDataSource(data = dict(time=[],sim=[],real=[]))
    datasource.data = datalog

    tools = 'xpan,wheel_zoom,reset'
    
    ts1 = figure(plot_width=1000, plot_height=400, tools=tools, x_axis_type='linear')
    ts1.line('time','sim', source=datasource, line_width=2, color="orange", legend_label="Simulated data: "+ simdescription)
    ts1.line('time','real', source=datasource, line_width=2, color="blue", legend_label="Real data: " + realdescription)
    

    # x_range_offset = (datalog.last_timestamp - datalog.start_timestamp) * 0.05
    # x_range = Range1d(datalog.start_timestamp - x_range_offset, datalog.last_timestamp + x_range_offset)
    # flight_mode_changes = get_flight_mode_changes(datalog)

    # set up layout
    widgets = column(datatype,stats)
    sim_button = column(sim_reverse_button)
    real_button = column(real_reverse_button)
    main_row = row(widgets)
    series = column(ts1, sim_button, real_button)
    layout = column(main_row, series)

    # initialize


    update()
    curdoc().add_root(intro_text)
    curdoc().add_root(links_text)
    curdoc().add_root(choose_field_text)    
    curdoc().add_root(layout)
    curdoc().title = "Flight data"



print("Now starting Thiel app")
GET_arguments = curdoc().session_context.request.arguments
config = read_settings()
print("simname is", simname, "realname is", realname)
# simname = join(DATA_DIR, simname)    # this is the default log file to load if you haven't been given another one
# realname = join(DATA_DIR, realname)    # this is the default log file to load if you haven't been given another one


if GET_arguments is not None and 'log' in GET_arguments:
    log_args = GET_arguments['log']
    if len(log_args) == 1:
        templog_id = str(log_args[0], 'utf-8')
        file_details = templog_id.split('desc:')
        templog_id = file_details[0]
        if (templog_id.find("sim") != -1):
            log_id = templog_id.replace('sim','')
            print("This is a sim file. New log ID=", log_id)
            ulog_file_name = get_log_filename(log_id)
            simname = os.path.join(get_log_filepath(), ulog_file_name)
            simdescription = file_details[1]
        elif (templog_id.find("real") != -1):
            log_id = templog_id.replace('real','')
            print("This is a real file. New log ID=", log_id)
            ulog_file_name = get_log_filename(log_id)
            realname = os.path.join(get_log_filepath(), ulog_file_name)
            realdescription = file_details[1]
        else:
            log_id = str(log_args[0], 'utf-8')
            if not validate_log_id(log_id):
                raise ValueError('Invalid log id: {}'.format(log_id))
        print('GET[log]={}'.format(log_id))
        ulog_file_name = get_log_filename(log_id)
get_thiel_analysis_plots(simname, realname)