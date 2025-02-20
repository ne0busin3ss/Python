import requests

def check_website_status(url):
    try:
        # Set a timeout for the request
        response = requests.get(url, timeout=10)
        # A status code of 200 means the website is up.
        if response.status_code == 200:
            return True, "Website is up!"
        else:
            return False, f"Website is down or inaccessible. Status code: {response.status_code}"
    except requests.Timeout:
        return False, "The request timed out. Website might be slow or down."
    except requests.RequestException as e:
        return False, f"An error occurred: {str(e)}"