from google import genai

client = genai.Client(api_key="AIzaSyCsJ9xHmpk-_fGs71W3I53xGb0mHYRtlis")

for model in client.models.list():
    print(model.name)