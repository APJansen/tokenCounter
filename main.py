import requests
import zipfile
import tempfile
import os
import shutil
from pygments.lexers import get_lexer_for_filename, guess_lexer_for_filename
from pygments.util import ClassNotFound
from pygments.lexer import Lexer
import tiktoken
from typing import Optional, Callable, Dict, Tuple
import json
from contextlib import contextmanager
import re
from tqdm import tqdm
import sys


def process_files_in_directory(directory_path: str, process_file_func: Callable[[str], int]) -> Dict[str, int]:
    """
    Process source code files in a directory using a given function, grouped by language.

    Args:
        directory_path (str): The path to the directory containing the source code files.
        process_file_func (Callable[[str], int]): A function that takes a file's content as input, and returns a value to be accumulated for each language.

    Returns:
        Dict[str, int]: A dictionary mapping programming languages to the accumulated results.
    """
    results_by_language = {}

    # Get the total number of files
    total_files = sum([len(files) for _, _, files in os.walk(directory_path)])

    # Use tqdm to create a progress bar
    with tqdm(total=total_files, desc="Processing files", unit="file", ncols=100) as progress_bar:
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

                language = get_language_from_content(file_path, content)

                if language:
                    count = process_file_func(content)
                    if language not in results_by_language:
                        results_by_language[language] = 0

                    results_by_language[language] += count

                # Update progress bar
                progress_bar.update(1)

    return results_by_language

def count_tokens_in_directory(directory_path: str) -> Dict[str, int]:
    """
    Count tokens in each source code file in a directory, grouped by language.

    Args:
        directory_path (str): The path to the directory containing the source code files.

    Returns:
        Dict[str, int]: A dictionary mapping programming languages to the total number of tokens.
    """

    def count_tokens(text: str) -> int:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        tokens = encoding.encode(text)
        return len(tokens)

    return process_files_in_directory(directory_path, count_tokens)

def count_lines_of_code_in_directory(directory_path: str) -> Dict[str, int]:
    """
    Count lines of code in each source code file in a directory, grouped by language.

    Args:
        directory_path (str): The path to the directory containing the source code files.

    Returns:
        Dict[str, int]: A dictionary mapping programming languages to the total number of lines of code.
    """
    def process_file_lines(content: str) -> int:
        return content.count('\n')

    return process_files_in_directory(directory_path, process_file_lines)

def get_language_from_content(file_path: str, content: str) -> Optional[str]:
    """
    Get the programming language name for a given file path and content.

    Args:
        file_path (str): The path to the file.
        content (str): The content of the file.

    Returns:
        Optional[str]: The programming language name or None if the language couldn't be determined.
    """
    try:
        lexer = get_lexer_for_filename(file_path, content)
    except ClassNotFound:
        try:
            lexer = guess_lexer_for_filename(file_path, content)
        except ClassNotFound:
            return None

    return lexer.name

def extract_zip_to_temp_dir(zip_path: str, temp_dir: str) -> None:
    """
    Extract a zip file to a specified directory.

    Args:
        zip_path (str): The path to the zip file.
        temp_dir (str): The path to the directory where the zip file should be extracted.
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

def download_repo_zip(url: str, target_path: str):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    with open(target_path, "wb") as f:
        with tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading", ncols=100) as progress_bar:
            progress_bar.set_postfix(file_size=f"{total_size / (1024 * 1024):.2f} MB", refresh=False)
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress_bar.update(len(chunk))


def get_zip_url(repo_url: str) -> str:
    """
    Get the URL of the zip file for a GitHub repository.

    Args:
        repo_url (str): The GitHub repository URL.

    Returns:
        str: The URL of the zip file to download.
    """
    # Check if the URL contains a branch name
    branch_pattern = r"https://github.com/([^/]+)/([^/]+)/(?:tree|blob)/([^/]+)"
    match = re.match(branch_pattern, repo_url)

    if match:
        owner, repo_name, branch_name = match.groups()
    else:
        # Extract the repository owner and name from the URL
        repo_parts = repo_url.rstrip('/').split('/')[-2:]
        if len(repo_parts) != 2:
            raise ValueError("Invalid GitHub repository URL")

        owner, repo_name = repo_parts

        # Fetch the repository information from the GitHub API
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
        response = requests.get(api_url)
        response.raise_for_status()

        # Extract the default branch name
        repo_info = json.loads(response.text)
        branch_name = repo_info["default_branch"]

    return f"https://github.com/{owner}/{repo_name}/archive/refs/heads/{branch_name}.zip"

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

@contextmanager
def TemporaryDirectoryWithZip(zip_url: str):
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "repo.zip")

    try:
        download_repo_zip(zip_url, zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

def print_analysis_results(analysis_results: Dict[str, Dict[str, float]]):
    """
    Print the analysis results as a table, sorted by lines of code.

    Args:
        analysis_results (Dict[str, Dict[str, float]]): A dictionary containing the analysis results.
    """
    # Sort languages by lines of code
    sorted_results = sorted(analysis_results.items(), key=lambda x: x[1]['lines_of_code'], reverse=True)

    # Compute totals
    total_loc = sum(result['lines_of_code'] for _, result in sorted_results)
    total_tokens = sum(result['tokens'] for _, result in sorted_results)
    total_tokens_per_line = total_tokens / total_loc if total_loc > 0 else 0
    sorted_results.insert(0, ('Total', {'lines_of_code': total_loc, 'tokens': total_tokens, 'tokens_per_line': total_tokens_per_line}))

    # Print header
    print("\nResults:")
    print(f"{'Language':<20} {'Lines of code':<15} {'Tokens':<15} {'Tokens per line':<15}")

    # Print rows
    for language, result in sorted_results:
        loc = result['lines_of_code']
        tokens = result['tokens']
        tokens_per_line = result['tokens_per_line']
        print(f"{language:<20} {loc:<15} {tokens:<15} {tokens_per_line:<15.2f}")



def main():
    """
    Main function for the script. Takes a GitHub repository URL as a command line argument,
    downloads the repository, analyzes the lines of code and tokens in the source code files,
    and displays the results.
    """
    if len(sys.argv) < 2:
        print("Usage: python main.py <GitHub_repository_URL>")
        sys.exit(1)

    repo_url = sys.argv[1].strip()
    zip_url = get_zip_url(repo_url)

    print("Downloading and extracting repository...")
    with TemporaryDirectoryWithZip(zip_url) as temp_dir:
        print("Analyzing repository...")
        analysis_results = analyze_repository(temp_dir)

        print_analysis_results(analysis_results)

if __name__ == "__main__":
    main()

