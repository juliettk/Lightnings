import folium
import datetime
import requests
import json
from instagram_scraper import TagScraper, exception_manager
from exceptions import (ExceptionManager,
                         InstagramException,
                         InternetException, UnexpectedResponse, NotUpdatedElement)

#colors for drawing lightnings data
RGBC_RECT = ["#000000","#FFFFFF","#E0FFFF","#AFEEEE","#ADD8E6","#B0E0E6","#7FFFD4","#00FFFF","#00CED1","#66CDAA","#20B2AA","#008B8B","#008080","#4682B4","#4169E1","#0000FF","#0000CD","#000080"];
RGB_TIME = ["#DF0101","#FE2E2E","#F78181","#DF7401","#FE9A2E","#F7BE81","#F7FE2E","#D0FA58","#BEF781","#58FA58","#58FAAC","#58FAF4","#2ECCFA","#2ECCFA","#2ECCFA","#2ECCFA","#2ECCFA","#2ECCFA"];


class MyMap:
    def __init__(self, time_interval = 4, location = (53,38)):
        """initializes class for creating lightnings maps during time_interval (4 or 24 h)"""
        self.time_interval = time_interval
        if time_interval == 4:
            self.lightnings_url = 'http://lightnings.ru/vr44.php?LA={0}&LO={1}'.format(*location)
        else:
            self.lightnings_url = 'http://lightnings.ru/vr44_24.php?LA={0}&LO={1}'.format(*location)
        self.location = location
        self.map = folium.Map(location=location, zoom_start=5,tiles="cartodbpositron")
        self.lightnings_data = self.load_json()
        self.scraper = TagScraper ('thunder', 'lightning')
        self.lightnings_locations = []

    def load_json(self):
        try:
            r = requests.get(self.lightnings_url)
            js = r.text[4:-19]
            js2 = json.loads(js)
        except (requests.exceptions.RequestException, ConnectionResetError) as exception:
            raise InternetException(exception)

        return js2

    def add_lightnings_layer (self):
        """adds color layer from lightnings.ru"""
        fg = folium.FeatureGroup(name='lightnings_layer')
        for item in self.lightnings_data:
            location = []
            indexes = list(range(1, 5))
            indexes.append(1)
            for i in indexes:
                keyt = 'p{}t'.format(i)
                keyn = 'p{}n'.format(i)
                location.append((float(item[keyt]), float(item[keyn])))
            self.lightnings_locations.append([0.25 * sum(l) for l in zip(*location[:-1])])

            value = int(item['cnt'])
            now = datetime.datetime.utcnow()
            endtime = datetime.datetime.strptime(item['DE'], "%Y-%m-%d %H:%M:%S")
            if self.time_interval == 4:
                delta = ((now - endtime).seconds) // 1200
            else:
                delta = ((now - endtime).seconds) // 10800
            if value > 17:
                value = 17
            fg.add_child(folium.vector_layers.Polygon(location, color=RGB_TIME[delta], fill=True, fill_opacity=0.7,
                                                      fill_color=RGBC_RECT[value - 1]))
            # poly_filled.add_to(my_map)
        self.lightnings_locations.sort()
        print(self.lightnings_locations)
        self.map.add_child(fg)

    def add_istagram_layer (self, count=100, limit = 100):
        """Scatter on map geolocated links to instagram images with tag 'thunder'"""
        fg = folium.FeatureGroup(name='instagram_layer')
        self.scraper.get_media(count=count, limit=limit, time_interval=self.time_interval)

        # for each media in scraper.tag put a marker on map
        for media in self.scraper.tag.media:
            test = folium.Html('<a href="{0}" "target="_blank"> <font size="+3">{0}</font </a><div class="box"><iframe src="{1}" width = "800px" height = "800px"></iframe></div>'.format(media.main_url, media.display_url), script=True)
            popup = folium.Popup(test)
            fg.add_child(folium.vector_layers.Marker(location=media.location, popup=popup))
        self.map.add_child(fg)

    def save (self, name = "my_map.html"):
        self.map.save(name)


def main(count = 100, time_interval = 4):
    my_map = MyMap(time_interval=time_interval)
    my_map.add_lightnings_layer()
    my_map.add_istagram_layer(count=count)
    my_map.save()
    my_map.scraper.session.close()

main(count=5000, time_interval=24)