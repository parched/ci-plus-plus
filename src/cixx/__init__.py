import argparse

__version__ = "0.1.0"


def main():
    parser = argparse.ArgumentParser(description="Compile to GitHub Actions workflow.")
    parser.add_argument("input file", help="Input CI++ YAML file")
    parser.add_argument("output file", help="GitHub Actions workflow YAML file")
