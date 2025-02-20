import requests

def check_website_status(url):
    try:
        response = requests.get(url)
        # A status code of 200 means the website is up.
        if response.status_code == 200:
            return True, "Website is up!"
        else:
            return False, f"Website is down or inaccessible. Status code: {response.status_code}"
    except requests.ConnectionError:
        return False, "Failed to connect. The website might be down or the URL is incorrect."

# Example usage
url = "https://www.empower.com/"     
is_up, message = check_website_status(url)
print(message)
