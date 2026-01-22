import requests

def query_deezer_metadata(query: str):
    """
    Vraća metapodatke o pjesmi dohvaćene s Deezer API-ja.
    """
    try:
        url = f"https://api.deezer.com/search?q={query}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if data.get("data") and len(data["data"]) > 0:
            result = data["data"][0]
            return {
                "status": "ok",
                "found": True,
                "artist": result["artist"]["name"],
                "title": result["title"],
                "album": result["album"]["title"],
                "preview": result["preview"]
            }

        return {"status": "ok", "found": False}

    except Exception as e:
        print("Deezer API Error:", e)
        return {"status": "ok", "found": False}