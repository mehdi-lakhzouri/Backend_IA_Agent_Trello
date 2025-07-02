import requests

def get_trello_user_info(api_key, token):
    url = "https://api.trello.com/1/members/me"
    params = {
        "key": api_key,
        "token": token
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return {"error": "Token invalide ou accès refusé"}
        data = resp.json()
        return {
            "id": data.get("id"),
            "username": data.get("username"),
            "fullName": data.get("fullName")
        }
    except Exception as e:
        return {"error": str(e)} 