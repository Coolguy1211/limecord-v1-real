import requests
import zipfile
import os
import shutil

GITHUB_REPO = "Coolguy1211/limecord-v1-real"
VERSION_FILE = "version.txt"

def get_latest_release_info():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def get_current_version():
    if not os.path.exists(VERSION_FILE):
        return "v0.0.0" # Should be a very old version
    with open(VERSION_FILE, 'r') as f:
        return f.read().strip()

def update_application():
    print("Checking for updates...")
    try:
        latest_release = get_latest_release_info()
        latest_version = latest_release['tag_name']
        current_version = get_current_version()

        print(f"Current version: {current_version}, Latest version: {latest_version}")

        if latest_version > current_version:
            print("New version available. Downloading...")
            zip_url = latest_release['zipball_url']
            response = requests.get(zip_url, stream=True)
            response.raise_for_status()

            with open("update.zip", "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print("Download complete. Extracting...")
            with zipfile.ZipFile("update.zip", 'r') as zip_ref:
                zip_ref.extractall("update_temp")

            # The extracted files are in a sub-directory, let's find it
            extracted_folder = os.path.join("update_temp", os.listdir("update_temp")[0])

            print("Replacing files...")
            for item in os.listdir(extracted_folder):
                s = os.path.join(extracted_folder, item)
                d = item
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

            with open(VERSION_FILE, 'w') as f:
                f.write(latest_version)

            print("Update complete. Please restart the application.")

        else:
            print("Application is up to date.")

    except Exception as e:
        print(f"An error occurred during update: {e}")
    finally:
        if os.path.exists("update.zip"):
            os.remove("update.zip")
        if os.path.exists("update_temp"):
            shutil.rmtree("update_temp")

if __name__ == "__main__":
    update_application()
