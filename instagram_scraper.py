import hashlib
import requests
import re
import json
from datetime import datetime
from exceptions import (ExceptionManager,
                         InstagramException,
                         InternetException, UnexpectedResponse, NotUpdatedElement)
exception_manager = ExceptionManager(repeats=5)

class Tag:
    entry_data_path = ("TagPage", 0, "graphql", "hashtag")
    base_url = "explore/tags/"
    media_path = ("hashtag", "edge_hashtag_to_media")
    media_query_hash = "ded47faa9a1aaded10161a2ff32abb6b"

    def __init__(self, name, additional_name):
        self.name = name
        self.additional_name = additional_name
        self.media_count = None

        self.media = set()
        self.top_posts = set()

    def set_data(self, data):
        self.name = data["name"]
        self.media_count = data["edge_hashtag_to_media"]["count"]
        for node in data["edge_hashtag_to_top_posts"]["edges"]:
            self.top_posts.add(Media(node["node"]["shortcode"]))

class Media:
    #entry_data_path = ("PostPage", 0, "graphql", "shortcode_media")

    def __init__(self, code):
        self.id = None
        self.code = code
        self.date = None
        self.location = None
        self.is_video = None
        self.video_url = None
        self.display_url = None
        self.main_url = None


    def set_data(self, data):
        self.id = data["id"]
        self.code = data["shortcode"]
        self.date = data["taken_at_timestamp"]
        self.is_video = data["is_video"]
        if self.is_video and "video_url" in data:
            self.video_url = data["video_url"]
        self.display_url = data["display_url"]
        self.main_url = "https://www.instagram.com/p/{0}/".format(self.code)

    def search_location(self, session):
        resp = session.get(self.main_url)
        # find the corresponding location address
        match = re.search(r"(\{\"@context.*)", resp.text)
        if not match is None:
            data = json.loads(match.group(0))
            # if location is available
            if 'contentLocation' in data.keys():
                loc_url = data['contentLocation']['mainEntityofPage']['@id']
                # parse latitude and longtitude
                #print(loc_url)
                resp = session.get(loc_url)
                match = re.search(r"\s*<meta\s*property\s*=\s*\"place:location:latitude\"\s*content=\"(.*)\"",
                                  resp.text)
                if not match is None:
                    lat = float(match.group(1))
                    match = re.search(r"\s*<meta\s*property\s*=\s*\"place:location:longitude\"\s*content=\"(.*)\"",
                                      resp.text)
                    long = float(match.group(1))
                    self.location = (lat, long)

class TagScraper:
    """Class for scraping media by tag"""
    def __init__(self,name: str, additional_name:str):
        self.rhx_gis = None
        self.csrf_token = None
        self.session = requests.Session()
        self.tag = Tag(name, additional_name)

    @exception_manager.decorator
    def get_request(self, *args, **kwargs):
        try:
            response = self.session.get(*args, **kwargs)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, ConnectionResetError) as exception:
            raise InternetException(exception)

    @exception_manager.decorator
    def open_session (self, settings=None, cookies=None):
        settings = dict() if settings is None else settings.copy()
        if cookies:
            self.session.cookies = requests.cookies.cookiejar_from_dict(cookies)
        query = "https://www.instagram.com/{0}{1}/".format(self.tag.base_url,self.tag.name)
        print ("url is", query)
        response = self.get_request(query, **settings)
        try:
            match = re.search(
                r"<script[^>]*>\s*window._sharedData\s*=\s*((?!<script>).*)\s*;\s*</script>",
                response.text,
            )
            data = json.loads(match.group(1))
            self.rhx_gis = data["rhx_gis"]
            self.csrf_token = data["config"]["csrf_token"]

            data = data["entry_data"]
            for key in self.tag.entry_data_path:
                data=data[key]
       # print(data)
            self.tag.set_data(data)
            return data
        except (AttributeError, KeyError, ValueError) as exception:
            raise UnexpectedResponse(exception, response.url)

    @exception_manager.decorator
    def graphql_request(self, query_hash, variables, referer, settings=None):
        if not isinstance(query_hash, str):
            raise TypeError("'query_hash' must be str type")
        if not isinstance(variables, str):
            raise TypeError("'variables' must be str type")
        if not isinstance(settings, dict) and not settings is None:
            raise TypeError("'settings' must be dict type or None")
        settings = dict() if settings is None else settings.copy()

        if not "params" in settings:
            settings["params"] = dict()
        settings["params"].update({"query_hash": query_hash})

        settings["params"]["variables"] = variables
        gis = "%s:%s" % (self.rhx_gis, variables)
        if not "headers" in settings:
            settings["headers"] = dict()
        settings["headers"].update({
        # "X-IG-App-ID": "936619743392459",
            "X-Instagram-GIS": hashlib.md5(gis.encode("utf-8")).hexdigest(),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer,
        })
        return self.get_request("https://www.instagram.com/graphql/query/", **settings)


    @exception_manager.decorator
    def get_media(self, pointer=None, time_interval = 4, count=12, limit=5, delay=0, settings=None):
        if not isinstance(pointer, str) and not pointer is None:
            raise TypeError("'pointer' must be str type or None")
        if not isinstance(count, int):
            raise TypeError("'count' must be int type")
        if not isinstance(limit, int):
            raise TypeError("'limit' must be int type")
        if not isinstance(delay, (int, float)):
            raise TypeError("'delay' must be int or float type")

        variables_string = '{{"{name}":"{name_value}","first":{first},"after":"{after}"}}'
        medias = []

        if pointer is None:
            try:
                data = self.open_session(settings=settings)
                print ("Start downloading {} images".format(count))
                data = data[self.tag.media_path[-1]]

                page_info = data["page_info"]
                edges = data["edges"]

                for index in range(min(len(edges), count)):
                    #print (edges[index])
                    node = edges[index]["node"]
                    m = Media(node["shortcode"])
                    m.set_data(node)
                    m.search_location(self.session)
                    inner_edges = node['edge_media_to_caption']['edges']
                    if inner_edges:
                        tags = inner_edges[0]['node']['text']
                    #check for additional tag in tags and availability of location information
                    if self.tag.additional_name in tags and m.location is not None:
                        #check time to be recent enough
                        date_time = datetime.utcfromtimestamp(m.date)
                        now = datetime.utcnow()
                        #in hours
                        photo_age = (now - date_time).seconds/3600
                        if photo_age < time_interval:
                            self.tag.media.add(m)
                            medias.append(m)

                pointer = page_info["end_cursor"] if page_info["has_next_page"] else None

                if len(edges) < count and page_info["has_next_page"]:
                    count = count - len(edges)
                else:
                    return medias, pointer
            except (ValueError, KeyError) as exception:
                print("Get media '%s' was unsuccessfull: %s", self.tag, str(exception))
                raise UnexpectedResponse(
                        exception,
                        "https://www.instagram.com/" + self.tag.base_url + self.tag.name,
                    )
        while True:
            print ("Processing...{0} images left".format(count))
            data = {"after": pointer, "first": min(limit, count)}
            data["name"] = "tag_name"
            data["name_value"] = self.tag.name

            response = self.graphql_request(
            query_hash=self.tag.media_query_hash,
            variables=variables_string.format(**data),
            referer="https://instagram.com/" + self.tag.base_url + self.tag.name,
            settings=settings,
            )

            try:
                if response is None:
                    pass
                data = response.json()["data"]
                for key in self.tag.media_path:
                    data = data[key]
                page_info = data["page_info"]
                edges = data["edges"]

                for index in range(min(len(edges), count)):
                    #print (edges[index])
                    node = edges[index]["node"]
                    m = Media(node["shortcode"])
                    m.set_data(node)
                    m.search_location(self.session)
                    inner_edges = node['edge_media_to_caption']['edges']
                    if inner_edges:
                        tags = inner_edges[0]['node']['text']

                    #check for location information
                    if self.tag.additional_name in tags and m.location is not None:
                        #check time to be recent enough
                        date_time = datetime.utcfromtimestamp(m.date)
                        now = datetime.utcnow()
                        #in hours
                        photo_age = (now - date_time).seconds/3600
                        if photo_age < time_interval:
#                            print(now, date_time, photo_age, m.location)
                            self.tag.media.add(m)
                            medias.append(m)

                pointer = page_info["end_cursor"] if page_info["has_next_page"] else None

                if len(edges) < count and page_info["has_next_page"]:
                    count = count - len(edges)
                else:
                    return medias, pointer
            except (ValueError, KeyError) as exception:
                print("Get media '%s' was unsuccessfull: %s", obj, self.tag(exception))
                raise UnexpectedResponse(exception, response.url)
