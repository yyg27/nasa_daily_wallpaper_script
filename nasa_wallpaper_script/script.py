import ctypes #for windows
import requests
import os
from datetime import datetime

#API key from https://api.nasa.gov/
api_key = "YOUR API KEY"

#NASA APOD API url from https://api.nasa.gov/
nasa_api_url =f"https://api.nasa.gov/planetary/apod?api_key={api_key}"

#os.path.expanduser makes user specific pathway
photos_path = os.path.expanduser("~/Resimler/NasaPhotos")
#create the path, if it already exists it returns true
os.makedirs(photos_path,exist_ok=True)

#Function to download image
def download_image():
    res = requests.get(nasa_api_url)
    data = res.json() #to get photo data

    if "url" not in data:
        print("Photo URL is not found")
        return -1

    image_url = data["hdurl"]
    image_name = f"nasaWP_{datetime.now().strftime('%Y-%m-%d')}.jpg" #to save photo named like "nasaWP_1947-01-08"
    image_path = os.path.join(photos_path,image_name) #photo saving path

    image_data = requests.get(image_url).content #get the content //meaning PHOTO
    with open(image_path,"wb") as f: #"wb" is used for writing with BINARY //with autocloses
        f.write(image_data)#write the photo

    print(f"Photo downloaded as {image_path}")
    return image_path


#function to set wallpaper
def set_wallpaper(image_path):
    ctypes.windll.user32.SystemParametersInfoW(20, 0, image_path, 3)
    print("Wallpaper is set")

#to run the script
image_path = download_image()
if image_path:
    set_wallpaper(image_path)



