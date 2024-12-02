from fantasyfootball.connectors.requests_connector import RequestsConnector
from fantasyfootball.parsers.profootballreference_parser import PFRGbgParser
import pandas as pd

# Initialize connectors and parser
CONFIG_PATH = "fantasy-football/config.json"
connector = RequestsConnector("path/to/config.json")
parser = PFRGbgParser(connector)

# Process data
df_list = []
for year in range(2019, 2023 + 1):
    df_list.append(parser.process_year(year))

final_df = pd.concat(df_list, ignore_index=True)
final_df.to_csv("path/to/output.csv", index=False)