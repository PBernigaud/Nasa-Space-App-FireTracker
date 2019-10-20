from __future__ import (absolute_import, division, print_function)

import os
import time
import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import shutil
import sys
from urllib.request import urlopen, Request, URLError, HTTPError
import json
import pandas
import requests

import cloudinary
import cloudinary.uploader
import cloudinary.api

import scipy.misc
import datetime
import numpy as np

import matplotlib.pyplot as plt
from sentinelhub import WmsRequest, WcsRequest, MimeType, CRS, BBox
from owslib.wms import WebMapService


import matlab.engine


######### Data for geo computations
# ang_width defines the angular width used to define the bounding boxes
ang_width = 0.05
deg_test = ang_width
###### LANCE - FIRMS api KEY 
app_key = "LANCE api key"

####### GIBS WMS Definition
wms = WebMapService('https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi', version='1.3.0')
layers_GIBS = list(wms.contents)


#### User Agent for download
#print('Beginning file download with urllib2...')
USERAGENT = 'tis/download.py_1.0--' + sys.version.replace('\n','').replace('\r','')

############ Cloudinary configuration ##############
cloudinary.config( 
  cloud_name = "cloudname", 
  api_key = "api_key", 
  api_secret = "api_secret" 
)

########## Firebase configuration
#Initialize directory to find account key JSON
pathwork = os.getcwd()
dir_path = os.chdir(pathwork)
# Fetch the service account key JSON file contents
cred = credentials.Certificate('firebase-adminsdk.json')
# Initialize the app with a service account, granting admin privileges
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://firebase_app.firebaseio.com/'
})


##################### Starting the MATLAB Engine
eng = matlab.engine.start_matlab()
print('MATLAB Engine started')

############### GMAIL Configuration
send_credentials = ["mail@gmail.com","password"]
receiving_mail = "mail@gmail.com"


#### Global value for debugging
test = ""

##### demo definition
ref = db.reference('NASA1')
#ref.update({'demo_lat':42.005 ,'demo_long':12.715 })
ref.update({'demo_lat':30.366 ,'demo_long':47.61})
print('Demo data updated')

####### Cloudinary upload function
def upload_cloudinary(file):
    data = cloudinary.uploader.upload(file)
    return data['url']
####### HTTP download part
def geturl(url, token=None, out=None):
    #### Based on https://ltdr.modaps.eosdis.nasa.gov/ltdr/ldope_lads.py
    headers = { 'user-agent' : USERAGENT }
    if not token is None:
        headers['Authorization'] = 'Bearer ' + token
    CTX = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    fh = urlopen(Request(url, headers=headers), context=CTX, timeout=5)
    if out is None:
        return fh.read().decode('utf-8')
    else:
        with open(out, 'wb') as out_file:
            shutil.copyfileobj(fh, out_file)
    return None

def return_fires(app_key):
    # Download the data from C6 (MODIS) and VIIRS from the current day and the day before
    # Concatenate them in a dataframe and export them
    # Uses them later to check if the spotted fire has been spotted by a satellite
    url_firms = "https://nrt3.modaps.eosdis.nasa.gov/api/v2/content/details/FIRMS/viirs/Global?fields=all&format=json"
    output = "firms_json.json"
    geturl(url_firms, app_key, output)

    with open(output) as f:
        data = json.load(f)
        
    data_firms = data['content']
    url_file = data_firms[-1]['self']
    url_file = url_file.split("/")
    url_file[4] = "archives"
    joiner = "/"
    url_file = joiner.join(url_file)
    txt_url = "https://nrt3.modaps.eosdis.nasa.gov" + url_file

    output_txt_viirs_today = "fires_viirs_today.txt"
    geturl(txt_url, app_key, output_txt_viirs_today)
    fires_viirs_today = pandas.DataFrame()
    fires_viirs_today = pandas.read_csv(output_txt_viirs_today)
    
    url_file = data_firms[-2]['self']
    url_file = url_file.split("/")
    url_file[4] = "archives"
    joiner = "/"
    url_file = joiner.join(url_file)
    txt_url = "https://nrt3.modaps.eosdis.nasa.gov" + url_file

    output_txt_viirs_24 = "fires_viirs_24.txt"
    geturl(txt_url, app_key, output_txt_viirs_24)
    fires_viirs_24 = pandas.DataFrame()
    fires_viirs_24 = pandas.read_csv(output_txt_viirs_24)
    
    url_firms = "https://nrt3.modaps.eosdis.nasa.gov/api/v2/content/details/FIRMS/c6/Global?fields=all&format=json"
    output = "firms_json.json"
    geturl(url_firms, app_key, output)

    with open(output) as f:
        data = json.load(f)
        
    data_firms = data['content']
    url_file = data_firms[-1]['self']
    url_file = url_file.split("/")
    url_file[4] = "archives"
    joiner = "/"
    url_file = joiner.join(url_file)
    txt_url = "https://nrt3.modaps.eosdis.nasa.gov" + url_file

    output_txt_c6_today = "fires_c6_today.txt"
    geturl(txt_url, app_key, output_txt_c6_today)
    fires_c6_today = pandas.DataFrame()
    fires_c6_today = pandas.read_csv(output_txt_c6_today)
    
    
    url_file = data_firms[-2]['self']
    url_file = url_file.split("/")
    url_file[4] = "archives"
    joiner = "/"
    url_file = joiner.join(url_file)
    txt_url = "https://nrt3.modaps.eosdis.nasa.gov" + url_file

    output_txt_c6_24 = "fires_c6_24.txt"
    geturl(txt_url, app_key, output_txt_c6_24)
    fires_c6_24 = pandas.DataFrame()
    fires_c6_24 = pandas.read_csv(output_txt_c6_24)
    
    
    fires = pandas.concat([fires_c6_today,fires_viirs_today,fires_viirs_24,fires_c6_24])
    fires.to_csv('fires_all.csv')
    return fires


def check_fires(lat,long,fires):
    # Query the FIRMS dataframe to know if the fire has been already been spotted by a satellite
    query_make = str('latitude < ' + str(lat+ang_width) + ' and latitude > ' + str(lat-ang_width) + ' and ')
    query_make = str(query_make + 'longitude < '+ str(long+ang_width) + ' and longitude > '+ str(long-ang_width))
    res = fires.query(query_make)
    return res

#lat = 42.005
#long = 12.715
#l_fire = return_fires(app_key)
#res_fire = check_fires(lat,long,l_fire)



######################################################################

def plot_image(image, plot_arg, factor=1):
    """
    Utility function for plotting RGB images.
    Function by Sentinel Hub
    """
    fig = plt.subplots(nrows=1, ncols=1, figsize=(15, 7))

    if np.issubdtype(image.dtype, np.floating):
        plt.imshow(np.minimum(image * factor, 1))
        plt.savefig('sat_image.png')
    else:
        plt.imshow(image)
        plt.savefig('sat_image.png')
        
        
INSTANCE_ID = 'Sentinel HUB instance ID'

def bbox_coord_SENTINEL(lat,long,ang_width):
    # Define a Bounding Box for sentinel hub
    coords_wgs84 = [long-ang_width,lat - ang_width,long+ang_width,lat+ang_width]
    bound_box = BBox(bbox=coords_wgs84, crs=CRS.WGS84)
    return bound_box

def bbox_coord_OWS(lat,long,ang_width):
    # Define a Bounding Box for OWSlib for WMS request
    coords_wgs84 = (long-ang_width,lat - ang_width,long+ang_width,lat+ang_width)
    return coords_wgs84


def pic_request_GIBS(lat,long,layer_n,ang_width):
    # Ask a WMS database (GIBS) to send the layers at the given coordinates 
    img = wms.getmap(   layers=[ layers_GIBS[layer_n] ],
                        styles=['visual_bright'],
                        srs='EPSG:4326',
                        bbox=bbox_coord_OWS(lat,long,ang_width),
                        size=(1024, 1024),
                         format='image/jpeg',
                         transparent=True
                         )
    last_time = wms[layers_GIBS[layer_n]].dimensions['time']['default']
    out = open('GIBS_Image.jpg', 'wb')
    out.write(img.read())
    out.close()
    return last_time


def pic_request_SENTINEL(lat,long,ang_width):
    bound_box = bbox_coord_SENTINEL(lat,long,ang_width)
    wms_true_color_request = WmsRequest(layer='TRUE-COLOR-S2-L1C',
                                        bbox=bound_box,
                                        time='latest',
                                        width=1024, height=1024,
                                        maxcc=0.1,
                                        instance_id=INSTANCE_ID)
    wms_dates = wms_true_color_request.get_dates()
    wms_true_color_img = wms_true_color_request.get_data()
    return wms_dates, wms_true_color_img


#ang_width = 0.05
#lat_duomo = 45.4740395
#lon_duomo = 9.1892143
#wms_dates, wms_true_color_img = pic_request_SENTINEL(lat,long,ang_width)
#wms_dates = pic_request_GIBS(lat,long,632,ang_width)
#
#plot_image(wms_true_color_img[-1])




###################################################################



port = 465  # For SSL
# Create a secure SSL context
context = ssl.create_default_context()


def send_pos(message_text, message_html, email):
    global send_credentials
    with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
        server.login(send_credentials[0], send_credentials[1])
        sender_email = send_credentials[0]
        receiver_email = email
        message = MIMEMultipart("alternative")
        message["Subject"] = "multipart test"
        message["From"] = "Fire Tester"
        message["To"] = receiver_email
        message_t = """\
        Subject: Hi there   
        """ + message_text + """   
        This message is sent from Python."""
        print(message_t)
        part1 = MIMEText(message_t, "plain")
        part2 = MIMEText(message_html, "html")
        message.attach(part1)
        message.attach(part2)
        server.sendmail(sender_email, receiver_email, message.as_string())
        print("Mail Envoyée")


init_mail = True
def db(event):
    # Action launched after an event is detected
    
    # Defining the global variables
    global test
    global init_mail
    global img
    global app_key
    global receiving_mail
    print('Firebase event detected: ')
    
    # Getting the new data linked to the event
    res = ref.get()
    pos = res["test"]
    photo = res["photo"]
    print(pos)
    print(photo)
    pos = pos.replace("[", '').replace("]", '').split(',')
    photo_clean = photo.replace("\\", '')
    photo_clean = photo_clean.replace("\n", '')
    photo_clean = photo_clean.replace('"', '')
    print(photo_clean)
    test = photo_clean
    
    # Clock time
    print(time.clock())
    print(limit_time)
    
    ### Download the taken picture and using the Neural Network (AlexNet)
    ## Linked to MATLAB for the AlexNet computations
    score_AlexNet = 0
    if not(photo_clean == ""):
        print('DL begining')
        myfile = requests.get(photo_clean)
        open('photo.jpg', 'wb').write(myfile.content)
    ######## MATLAB AlexNet
        print('AlexNet Running')
        score_AlexNet = eng.FireRecognition(os.getcwd() +"\\photo.jpg")
        print('AlexNet Done')
    #######################
    ## If No photo then demo so use fire photo
    else:
        ref.update({'photo' : 'https://res.cloudinary.com/cloudname/image/upload/v1571505087/img.jpg'})
    
    
    print("DL done")
    
    # Extracting position
    lat = float(pos[0])
    long = float(pos[1])
    
    # Getting FIRMS Data and if error use backups FIRMS data
    try:
        l_fire = return_fires(app_key)
        print('FIRMS Get OK')
    except:
        l_fire = pandas.read_csv('fires_all.csv')
        print('FIRMS Get Error : Using backup')
    res_fire = check_fires(lat,long,l_fire)
    fire_on_spot_FIRMS = not(res_fire.empty)
    print('FIRMS Treatment done')
    
    # Getting the pictures from MODIS and Sentinel 2 satellites
    wms_dates, wms_true_color_img = pic_request_SENTINEL(lat,long,ang_width)
    date_pic = wms_dates[-1]
    str_date = date_pic.strftime("%m/%d/%Y, %H:%M:%S")
    wms_dates_GIBS = pic_request_GIBS(lat,long,632,ang_width)
    
    scipy.misc.imsave('sentinel_image.jpg', wms_true_color_img[-1])
    print('Sat_image Sentinel done')
    
    # Upload to Cloudinary for mailing purpose
    url_image = upload_cloudinary('sentinel_image.jpg')
    
    # Sending an e-mail containing all the Data
    # Avoid sending an e-mail if only launch (connection is an event)
    if init_mail:
        email = receiving_mail
        message = "Pointed position : " + res["test"]
        message_html = """\
<html>
  <body>
"""
        message_html = "<p> Pointed position : " + res["test"] + "</p>"
        if fire_on_spot_FIRMS:
            message_html = message_html + "<p> The NASA FIRMS system has spotted a fire on the designated position </p>"
            message_html = message_html + res_fire.to_html()
        
        if ".jpg" in photo_clean:
            message_html = message_html + "<p> The User took a picture of the fire, you can find at the following link : </p>"
            message_html = message_html + "<a href=" + photo_clean + "> Photo Link </a>"
            message_html = message_html + '<img src="'+ photo_clean +'">'
        if score_AlexNet > 0.1:
            message_html = message_html + "<p> The Neural Network is confident in that there is a fire in the picture sent </p>"
        
        message_html = message_html + "<p> Sentinel 2 satellites have produced images at "+ str_date +" : </p>"
        message_html = message_html + "<a href=" + url_image + "> Photo Link </a>"
        message_html = message_html + '<img src="'+ url_image +'">'
            
        
        message_html = message_html + """
  </body>
</html>
"""
        send_pos(message,message_html, email)
    else:
        init_mail = True


if __name__ == "__main__":
    # Initializing the environment
    loc_path = 'NASA1'
    ref = firebase_admin.db.reference(loc_path)
    listener = ref.listen(db)
    time_on = time.clock()
    limit_time = time_on + 10
    try:
        if time.clock() < limit_time:
            pass
        else:
            listener.close()
    except KeyboardInterrupt:
        listener.close()