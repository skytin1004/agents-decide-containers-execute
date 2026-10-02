"""Read the committed worker report without invoking another model turn."""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
from docops.azure_io import AzureStore

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
parser = argparse.ArgumentParser()
parser.add_argument("request_id")
args = parser.parse_args()
print(json.dumps(AzureStore().status(args.request_id), indent=2))
