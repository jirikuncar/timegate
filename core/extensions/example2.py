from pip._vendor.requests.packages.urllib3 import request

__author__ = 'Yorick Chollet'

from core.handler import Handler
from errors.handlererror import HandlerError

#TODO define what needs to be imported in superclass, so what will be needed in
#Handlers


class OtherHandler(Handler):


    def __init__(self):

        # Regular Expressions! must begin with http:// or https://
        self.resourcebase = ['http://www.an\d{1,2}.other.com/*',
                             'http://www.another.com/*'
                             ]

        self.singleonly = True



    def get(self, uri, datetime=None):
        api_uri = 'http://127.0.0.1:9001/timemap2/'

        # Requests the API
        req = self.request(api_uri, uri)

        # Handles API Response
        if not req or req.status_code == 404:
            raise HandlerError("Cannot find resource on version server.", 404)
        elif req.status_code == 200:
            # Assume the API handles the requests correctly
            assert (req.headers['content-type'].startswith('application/json'))

            # Extract the JSON elements URI-R and (Mementos, Datetime) pairs
            json = req.json()
            uri_r = json['original_uri']
            dict_list = json['mementos']['all']

            # Transform each dictionary element e of the list into a tuple of its values
            def keys2tuple(e):
                return tuple(e.values())
            tuplelist = map(keys2tuple, dict_list)

            # Returns the list of tuples (URI, Datetime)
            tuplelist.append((uri_r, None))
            return tuplelist

        else:
            # API response undefined.
            raise HandlerError("Unknown API response.", 503)