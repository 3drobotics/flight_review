from __future__ import print_function
import tornado.web

#pylint: disable=relative-beyond-top-level
from .common import get_jinja_env

TOP_TEMPLATE = 'top.html'

#pylint: disable=abstract-method

class TopHandler(tornado.web.RequestHandler):
    """ Tornado Request Handler to render the radio controller (for testing
        only) """
    print("Starting top page")

    def get(self, *args, **kwargs):
        """ GET request """

        template = get_jinja_env().get_template(TOP_TEMPLATE)
        self.write(template.render())