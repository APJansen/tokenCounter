import requests
import zipfile
import tempfile
import os


def extract_zip_to_temp_dir(zip_path: str) -> str:
    temp_dir = tempfile.mkdtemp()

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    return temp_dir


def download_repo_zip(url: str, target_path: str):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(target_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


if __name__ == "__main__":
    print("GitHub Token Analyzer")

