import requests
import zipfile
import tempfile
import os
import shutil
from pygments.lexers import get_lexer_for_filename, guess_lexer_for_filename
from pygments.util import ClassNotFound
import tiktoken


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a given text using the GPT-3.5 tokenizer.

    Args:
        text (str): The text to tokenize and count.

    Returns:
        int: The total number of tokens in the text.
    """
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = encoding.encode(text)
    return len(tokens)

def count_tokens_in_directory(directory_path: str) -> dict[str, int]:
    """
    Count tokens in each source code file in a directory, grouped by language.

    Args:
        directory_path (str): The path to the directory containing the source code files.

    Returns:
        dict[str, int]: A dictionary mapping programming languages to the total number of tokens.
    """
    tokens_by_language = {}

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
            token_count = count_tokens(content)

            if language not in tokens_by_language:
                tokens_by_language[language] = 0

            tokens_by_language[language] += token_count

    return tokens_by_language

def count_lines_of_code(file_path: str) -> int:
    """
    Count the number of lines of code in a source code file.

    Args:
        file_path (str): The path to the source code file.

    Returns:
        int: The total number of lines of code in the file.
    """
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
    """
    Count lines of code in each source code file in a directory, grouped by language.

    Args:
        directory_path (str): The path to the directory containing the source code files.

    Returns:
        dict[str, int]: A dictionary mapping programming languages to the total number of lines of code.
    """
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
            lines_of_code = content.count('\n')

            if language not in loc_by_language:
                loc_by_language[language] = 0

            loc_by_language[language] += lines_of_code

    return loc_by_language

def extract_zip_to_temp_dir(zip_path: str) -> str:
    """
    Extract a zip file to a temporary directory.

    Args:
        zip_path (str): The path to the zip file.

    Returns:
        str: The path to the temporary directory containing the extracted files.
    """
    temp_dir = tempfile.mkdtemp()

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    return temp_dir

def download_repo_zip(url: str, target_path: str):
    """
    Download a GitHub repository's zip file and save it to a specified path.

    Args:
        url (str): The URL of the zip file to download.
        target_path (str): The path where the zip file should be saved.
    """
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(target_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def get_zip_url(repo_url: str) -> str:
    """
    Get the URL of the zip file for a GitHub repository.

    Args:
        repo_url (str): The GitHub repository URL.

    Returns:
        str: The URL of the zip file to download.
    """
    return f"{repo_url}/archive/refs/heads/main.zip"


def analyze_repository(directory_path: str) -> dict[str, dict[str, float]]:
    """
    Analyze a repository and return the results.

    Args:
        directory_path (str): The path to the repository directory.

    Returns:
        dict[str, dict[str, float]]: A dictionary containing the analysis results.
    """
    loc_by_language = count_lines_of_code_in_directory(directory_path)
    tokens_by_language = count_tokens_in_directory(directory_path)

    analysis_results = {}
    for language in loc_by_language:
        loc = loc_by_language[language]
        tokens = tokens_by_language.get(language, 0)
        tokens_per_line = tokens / loc if loc > 0 else 0

        analysis_results[language] = {
            "lines_of_code": loc,
            "tokens": tokens,
            "tokens_per_line": tokens_per_line
        }

    return analysis_results

def print_analysis_results(analysis_results: dict[str, dict[str, float]]):
    """
    Print the analysis results as a table, sorted by lines of code.

    Args:
        analysis_results (dict[str, dict[str, float]]): A dictionary containing the analysis results.
    """
    # Sort languages by lines of code
    sorted_results = sorted(analysis_results.items(), key=lambda x: x[1]['lines_of_code'], reverse=True)

    # Print header
    print("\nResults:")
    print("{:<20} {:<15} {:<15} {:<15}".format("Language", "Lines of code", "Tokens", "Tokens per line"))

    # Print rows
    for language, result in sorted_results:
        print("{:<20} {:<15} {:<15} {:<15.2f}".format(language, result['lines_of_code'], result['tokens'], result['tokens_per_line']))


def main():
    """
    Main function for the script. Prompts the user for a GitHub repository URL,
    downloads the repository, analyzes the lines of code and tokens in the source code files,
    and displays the results.
    """
    repo_url = input("Enter the GitHub repository URL (e.g., https://github.com/user/repo): ").strip()
    zip_url = get_zip_url(repo_url)
    zip_path = "repo.zip"

    print("Downloading repository...")
    download_repo_zip(zip_url, zip_path)

    print("Extracting repository...")
    temp_dir = extract_zip_to_temp_dir(zip_path)

    print("Analyzing repository...")
    analysis_results = analyze_repository(temp_dir)

    print_analysis_results(analysis_results)

    os.remove(zip_path)
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()

