import logging

__author__ = 'Yorick Chollet'

from core.handler_baseclass import Handler
from lxml import etree
import StringIO
from errors.timegateerrors import HandlerError
import urlparse
import urllib2
from core.timegate_utils import date_str


class WikipediaHandler(Handler):

    def __init__(self):
        Handler.__init__(self)
        self.TIMESTAMPFMT = '%Y%m%d%H%M%S'

        # Storing first mementos
        self.inner_cache = {}
        self.max_inner_cache_size = 100000

    def get_memento(self, req_uri, accept_datetime):
        timestamp = date_str(accept_datetime, self.TIMESTAMPFMT)
        params = {
            'rvlimit': 1,  # Only need one
            'rvstart': timestamp,  # Start listing from here
            'rvdir': 'older'  # List in decreasing order
        }


        # Finds the API and title using scraping
        api_base_uri = None
        try:
            dom = self.get_xml(req_uri, html=True)
            links = dom.xpath("//link")
            for link in links:
                if link.attrib['rel'].lower() == "edituri":
                    api_base_uri = link.attrib['href'].split("?")[0]
                    if api_base_uri.startswith("//"):
                        api_base_uri = api_base_uri.replace("//", "http://")
            parsed_url = urlparse.urlparse(req_uri)
            try:
                title = urlparse.parse_qs(parsed_url[4])['title'][0]
            except Exception as e:
                title = parsed_url.path.split('/')[-1]
            logging.debug("Mediawiki handler: API found: %s, page title parsed to: %s " % (api_base_uri, title) )
            if not title:
                raise HandlerError("Cannot find Title", 404)
            if not api_base_uri:
                raise HandlerError("Cannot find mediawiki API on page", 404)
            else:
                title = urllib2.unquote(title)

        except HandlerError as he:
            raise he
        except Exception as e:
            logging.error("MediaWikiHandler: querying and parsing page for title/api %s. handler will return empty response" % e)
            return None

        base_uri = api_base_uri.replace("api.php", "index.php")

        # The best Memento
        memento = self.query(req_uri, params, title, api_base_uri, base_uri)[0]

        # The first Memento
        if title in self.inner_cache and memento:
            logging.debug("Wiki Handler: found cached first for "+title)
            first = self.inner_cache[title]
        else:
            logging.debug("Wiki Handler: Querying first for "+title)
            first_params = {
                'rvlimit': 1,  # Only need one
                'rvstart': '19900101000000',  # Start listing from 1990
                'rvdir': 'newer'  # List in increasing order
            }
            first = self.query(req_uri, first_params, title, api_base_uri, base_uri)[0]
            if len(self.inner_cache) > self.max_inner_cache_size:
                self.inner_cache = {}
            self.inner_cache[title] = first

        # This handler returns more than only the best Memento.
        # A Link with rel="first memento" will also be returned to the client.
        return [first, memento]

    def query(self, req_uri, req_params, title, api_base_uri, base_uri):
        """
        Returns a processed list of tuple.
        Can be used with increased rvlimit.
        :param req_uri:
        :param req_params:
        :param title:
        :param api_base_uri:
        :param base_uri:
        :return:
        """

        params = {
            'action': 'query',
            'format': 'json',
            'prop': 'revisions',
            'rvprop': 'ids|timestamp',
            'indexpageids': '',
            'titles': title
        }
        params.update(req_params)

        # Does sequential queries to get all revisions IDs and Timestamps
        queries_results = []
        condition = True
        while condition:
            # Clone original request
            newparams = params.copy()
            req = self.request(api_base_uri, params=newparams)
            try:
                result = req.json()
            except Exception as e:
                logging.error("No JSON can be decoded from API %s" % api_base_uri)
                raise HandlerError("No API answer.", 404)
            if 'error' in result:
                raise HandlerError(result['error'])
            if 'warnings' in result:
                # logging.warn(result['warnings'])
                pass
            try:
                # The request was successful
                pid = result['query']['pageids'][0]  # the JSON key of the page (only one)
                queries_results += result['query']['pages'][pid]['revisions']
                if ('missing' in result['query']['pages'][pid] or
                                'invalid' in result['query']['pages'][pid]):
                    raise HandlerError("Cannot find resource on version server.", 404)
            except Exception as e:
                if req_params['rvdir'] == 'older':
                    req_params['rvdir'] = 'newer'
                    return self.query(req_uri, req_params, title, api_base_uri, base_uri)
                else:
                    raise HandlerError("No revision returned from API.", 404)
            if 'continue' in result:
                # The response was truncated, the rest can be obtained using
                # &rvcontinue=ID
                cont = result['continue']
                # Modify it with the values returned in the 'continue' section of the last result.
                newparams.update(cont)
                condition = True
            else:
                condition = False

        # Processing list
        def f(rev):
            rev_uri = base_uri + '?title=%s&oldid=%d' % (
                urllib2.quote(title), rev['revid'])
            dt = rev['timestamp']
            return (rev_uri, dt)


        # logging.debug("Returning API results of size %d" % len(queries_results))
        return map(f, queries_results)

    def get_xml(self, uri, html=False):
        """
        Retrieves the resource using the url, parses it as XML or HTML
        and returns the parsed dom object.
        :param uri: [str] The uri to retrieve
        :param headers: [dict(header_name: value)] optional http headers to send in the request
        :param html: [bool] optional flag to parse the response as HTML
        :return: [lxml_obj] parsed dom.
        """

        try:
            page = self.request(uri)
        except HandlerError as he:
            raise HandlerError(he, status=404)

        try:
            page_data = page.content
            if not html:
                parser = etree.XMLParser(recover=True)
            else:
                parser = etree.HTMLParser(recover=True)
            return etree.parse(StringIO.StringIO(page_data), parser)
        except Exception as e:
            logging.error("Cannot parse XML/HTML from %s" % uri)
            raise HandlerError("Couldn't parse data from %s" % uri, 404)

