import requests
import zipfile
import tempfile
import os
from pygments.lexers import get_lexer_for_filename, guess_lexer_for_filename
from pygments.util import ClassNotFound

def count_lines_of_code(file_path: str) -> int:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        return 0

    try:
        lexer = get_lexer_for_filename(file_path, content)
    except ClassNotFound:
        try:
            lexer = guess_lexer_for_filename(file_path, content)
        except ClassNotFound:
            return 0

    return sum(1 for _ in lexer.get_lines(content))

def count_lines_of_code_in_directory(directory_path: str) -> dict[str, int]:
    loc_by_language = {}

    for root, _, files in os.walk(directory_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)

            if not os.path.isfile(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                continue

            try:
                lexer = get_lexer_for_filename(file_path, content)
            except ClassNotFound:
                try:
                    lexer = guess_lexer_for_filename(file_path, content)
                except ClassNotFound:
                    continue

            language = lexer.name
            lines_of_code = sum(1 for _ in lexer.get_lines(content))

            if language not in loc_by_language:
                loc_by_language[language] = 0

            loc_by_language[language] += lines_of_code

    return loc_by_language


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

