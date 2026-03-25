import json
import urllib.request
import urllib.error
import urllib.parse
import math
 

# function to get latitude and longitude from postcode
def coordinates(postcode):
    try:
        # first clean postcode, remove whitspaces and convert to upper case
        postcode = postcode.strip().replace("\n","").replace("\r", "").upper()
        
        # encode post code for the url
        encoded_postcode = urllib.parse.quote(postcode)
        
        url = f"https://api.postcodes.io/postcodes/{encoded_postcode}"
        print("calling url", url, flush=True)
        
        # http get request to api
        with urllib.request.urlopen(url) as response:
            # read and parse json response
            data = json.loads(response.read()) 
            
            if data["status"] == 200:
                result = data["result"]
                print("coords for", postcode, ":", result["latitude"], result["longitude"])
                return result["latitude"], result["longitude"]
            else:
                print("api error", data)
            
    except urllib.error.HTTPError as e: 
        print("httperror", e)    
    except Exception as e:
        print("genral error", e) 
    return None, None


# function to calculate the great circle distance between two points
def havershine(latitude1, longitude1, latitude2, longitude2):
    
    # convert differences in latitude and longittude to radians
    dLat = (latitude2 - latitude1) * math.pi / 180.0
    dLon = (longitude2 - longitude1) * math.pi / 180.0
    
    # convert original latitudes to radians
    latitude1 = latitude1 * math.pi / 180.0
    latitude2 = latitude2 * math.pi / 180.0
    
    # havershine formula to calculate the distance
    a = (
        math.sin(dLat / 2) ** 2 +
        math.sin(dLon / 2) ** 2 * math.cos(latitude1) * math.cos(latitude2)
    
    )
    
    c = 2 * math.asin(math.sqrt(a))
    
    # radius of the earth
    R = 6371
    # distance in km
    return R * c

def food_miles(postcode1, postcode2):
    # get coordinates for postcodes
    latitude1, longitude1 = coordinates(postcode1)
    latitude2, longitude2 = coordinates(postcode2)
    
    if latitude1 is None or latitude2 is None:
        print("one of the coords is not valid")
        return None
    
    # calculate distance in km first
    distance_km = havershine(latitude1, longitude1, latitude2, longitude2)
    # then covert to miles
    miles = distance_km * 0.621371
    
    print("cord1", latitude1, longitude1)
    print("cord2", latitude2, longitude2)
    
    print("farm miles", miles)
    
    # round distance to 2 decimal places
    return round(miles, 2)
