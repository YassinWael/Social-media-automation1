import requests

api_key = "80275c193b02b280cd4c26139e63a4f0"
url = "https://api.imgbb.com/1/upload"
with open("output.png","rb") as f:
    response = requests.post(url,params={"key":api_key,"name":"output.png"},files={"image":f})
    print(response.json())