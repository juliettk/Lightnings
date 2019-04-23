# Lightnings
A project to plot geomap with overplotted color-coded information about lightnings from lightnings.ru (layer "lightnings_layer")
 and scattered locations of instagram images with tags "thunder" and "lightnings" (layer "instagram_layer"). 
Only photos taken during the time interval, corresponding to the lightnings information, are included. Each marker is clickable and contains hyperlink and preview.

Algorithm: 1) draw map
	2) parse and add lightnings data
	3) search instagram images by tag "thunder"
	4) chose only those who: I. Also have contain "lightning" in tags
				II. Have location data
				III. Were taken during the specified time_interval
	5) Add location markers to the map together with hyperlinks and preview images
	6) Save map as "my_map.html"

To run the project execute main(count:int, time_interval:int) from lightnings_maps_folium.py.

Parameters:
    count is max number of instagram images. Default is 100
    time_interval can be 4h (default) or 24h (any value different from 4 is considered 24 :) )

Also the example map with count=5000 and time_interval = 24h