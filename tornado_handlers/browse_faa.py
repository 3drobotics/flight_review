"""
Tornado handler for the browse page
"""
from __future__ import print_function
import collections
import sys
import os
from datetime import datetime
import json
import sqlite3
import tornado.web

# this is needed for the following imports
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../plot_app'))
from config import get_db_filename, get_overview_img_filepath
from db_entry import DBData, DBDataGenerated
from helper import flight_modes_table, get_airframe_data, html_long_word_force_break

#pylint: disable=relative-beyond-top-level,too-many-statements
from .common import get_jinja_env, get_generated_db_data_from_log

BROWSE_TEMPLATE = 'browse_faa.html'

#pylint: disable=abstract-method

class BrowseFAADataRetrievalHandler(tornado.web.RequestHandler):
    """ Ajax data retrieval handler """

    def get(self, *args, **kwargs):
        search_str = self.get_argument('search[value]', '').lower()
        order_ind = int(self.get_argument('order[0][column]'))
        order_dir = self.get_argument('order[0][dir]', '').lower()
        data_start = int(self.get_argument('start'))
        data_length = int(self.get_argument('length'))
        draw_counter = int(self.get_argument('draw'))

        json_output = dict()
        json_output['draw'] = draw_counter


        # get the logs (but only the public ones)
        con = sqlite3.connect(get_db_filename(), detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()

        sql_order = ' ORDER BY Date DESC'

        ordering_col = ['LogsGenerated.UUID',
                        '', # UAS Model
                        'LogsGenerated.StartTime',
                        'LogsGenerated.VehicleFlightTime',
                        '', # End Hours
                        'LogsGenerated.Duration',
                        '', # Flight Rating
                        ]
        if ordering_col[order_ind] != '':
            sql_order = ' ORDER BY ' + ordering_col[order_ind]
            if order_dir == 'desc':
                sql_order += ' DESC'

        cur.execute('SELECT '
                    '   Logs.Id, '
                    '   Logs.Rating, '
                    '   LogsGenerated.Id, '
                    '   LogsGenerated.UUID, '
                    '   LogsGenerated.StartTime, '
                    '   LogsGenerated.Duration, '
                    '   LogsGenerated.VehicleFlightTime '
                    'FROM Logs '
                    '   LEFT JOIN LogsGenerated on Logs.Id=LogsGenerated.Id '
                    '   LEFT JOIN Vehicle on LogsGenerated.UUID=Vehicle.UUID '
                    'WHERE Logs.Public = 1 AND NOT Logs.Source = "CI" '
                    +sql_order)

        # pylint: disable=invalid-name
        Columns = collections.namedtuple("Columns", "columns search_only_columns")

        def get_columns_from_tuple(db_tuple, counter):
            """ load the columns (list of strings) from a db_tuple
            """

            db_data = DBDataJoin()
            log_id = db_tuple[0]
            db_data.rating = db_tuple[1]
            generateddata_log_id = db_tuple[2]
            if log_id != generateddata_log_id:
                print('Join failed, loading and updating data')
                db_data_gen = get_generated_db_data_from_log(log_id, con, cur)
                if db_data_gen is None:
                    return None
                db_data.add_generated_db_data_from_log(db_data_gen)
            else:
                db_data.vehicle_uuid = db_tuple[3]
                db_data.start_time_utc = db_tuple[4]
                db_data.duration_s = db_tuple[5]
                db_data.vehicle_flight_time = db_tuple[6]

            def format_duration(s):
                m, s = divmod(round(s), 60)
                h, m = divmod(m, 60)
                return '{:d}:{:02d}:{:02d}'.format(h, m, s)

            duration_str = format_duration(db_data.duration_s)

            start_time_str = 'N/A'
            if db_data.start_time_utc != 0:
                start_datetime = datetime.fromtimestamp(db_data.start_time_utc)
                start_time_str = start_datetime.strftime("%Y-%m-%d  %H:%M")

            start_hours_str = 'N/A'
            end_hours_str = 'N/A'
            if db_data.vehicle_flight_time is not None:
                start_hours_str = format_duration(db_data.vehicle_flight_time)
                end_hours_str = format_duration(db_data.vehicle_flight_time + db_data.duration_s)

            search_only_columns = []

            if db_data.vehicle_uuid is not None:
                search_only_columns.append(db_data.vehicle_uuid)

            rating_str = 'Fail'
            if db_data.rating in ['good', 'great']:
                rating_str = 'Pass'

            return Columns([
                db_data.vehicle_uuid,
                'H520-G', # hardcoded 😱
                '<a href="/plot_app?log='+log_id+'&faa=true">'+start_time_str+'</a>',
                start_hours_str,
                end_hours_str,
                duration_str,
                rating_str,
            ], search_only_columns)

        # need to fetch all here, because we will do more SQL calls while
        # iterating (having multiple cursor's does not seem to work)
        db_tuples = cur.fetchall()
        json_output['recordsTotal'] = len(db_tuples)
        json_output['data'] = []
        if data_length == -1:
            data_length = len(db_tuples)

        filtered_counter = 0
        if search_str == '':
            # speed-up the request by iterating only over the requested items
            counter = data_start
            for i in range(data_start, min(data_start + data_length, len(db_tuples))):
                counter += 1

                columns = get_columns_from_tuple(db_tuples[i], counter)
                if columns is None:
                    continue

                json_output['data'].append(columns.columns)
            filtered_counter = len(db_tuples)
        else:
            counter = 1
            for db_tuple in db_tuples:
                counter += 1

                columns = get_columns_from_tuple(db_tuple, counter)
                if columns is None:
                    continue

                if any([search_str in str(column).lower() for column in \
                        (columns.columns, columns.search_only_columns)]):
                    if data_start <= filtered_counter < data_start + data_length:
                        json_output['data'].append(columns.columns)
                    filtered_counter += 1


        cur.close()
        con.close()

        json_output['recordsFiltered'] = filtered_counter

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(json_output))

class DBDataJoin(DBData, DBDataGenerated):
    """Class for joined Data"""

    def add_generated_db_data_from_log(self, source):
        """Update joined data by parent data"""
        self.__dict__.update(source.__dict__)


class BrowseFAAHandler(tornado.web.RequestHandler):
    """ Browse public log file Tornado request handler """

    def get(self, *args, **kwargs):
        template = get_jinja_env().get_template(BROWSE_TEMPLATE)

        template_args = {}

        search_str = self.get_argument('search', '').lower()
        if len(search_str) > 0:
            template_args['initial_search'] = json.dumps(search_str)

        self.write(template.render(template_args))
