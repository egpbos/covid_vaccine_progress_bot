from collections import defaultdict
import datetime

import configargparse as cap
import tweepy
from tqdm import tqdm
import pandas as pd
import pycountry_convert as pc

argparser = cap.ArgParser(default_config_files=['keys.yml'])
argparser.add('-c', is_config_file=True, help='config file path')
argparser.add('--api', env_var='BOT_API')
argparser.add('--api-secret', env_var='BOT_API_SECRET')
argparser.add('--access', env_var='BOT_ACCESS')
argparser.add('--access-secret', env_var='BOT_ACCESS_SECRET')

args = argparser.parse_args()

# Authenticate to Twitter
auth = tweepy.OAuthHandler(args.api, args.api_secret)
auth.set_access_token(args.access, args.access_secret)

api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

try:
    api.verify_credentials()
    print("Authentication OK")
except:
    print("Error during authentication")

# get current percentage
data = pd.read_csv('https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv', parse_dates=['date'])

data_filtered = data[data.location == 'World']
data_filtered = data_filtered[data_filtered.date == data_filtered.date.max()]

# take last item in case dataset contains multiple items this day:
percentage = data_filtered.iloc[-1].people_vaccinated_per_hundred

# cycle world emojis each day:
world_today = "🌎🌏🌍"[datetime.datetime.now().timetuple().tm_yday % 3]


def tweet_bar_string_from_percentage(percentage, continent, bar_format='|{bar:12}| {percentage:.2g}% CONTINENT'):
    bar = tqdm(initial=percentage, total=100., bar_format=bar_format, ascii=False)
    bar_string = str(bar)
    bar.close()
    bar_separator_ix = bar_string.rfind('|')
    tweet_string = bar_string[:bar_separator_ix].replace(' ', '\u3000') + bar_string[bar_separator_ix:]
    tweet_string = tweet_string.replace('CONTINENT', continent)
    return tweet_string


tweet_string = tweet_bar_string_from_percentage(percentage, world_today) + '\n'

# add continent bars

def continent_from_iso_country_code(alpha3_country_code):
    alpha2_country_code = pc.country_alpha3_to_country_alpha2(alpha3_country_code)
    continent_code = pc.country_alpha2_to_continent_code(alpha2_country_code)
    return pc.convert_continent_code_to_continent_name(continent_code)


data_filtered = data[data.location != 'World']
data_filtered = data_filtered.dropna(subset=['iso_code', 'people_vaccinated'])
data_filtered = data_filtered.loc[data_filtered.groupby('iso_code').date.idxmax()]
data_filtered = data_filtered.set_index('iso_code')

continent_totals = defaultdict(int)

for iso_code, number in data_filtered.people_vaccinated.iteritems():
    try:
        continent = continent_from_iso_country_code(iso_code)
        continent_totals[continent] += number
    except KeyError:
        print("iso code", iso_code, "not a valid country code, skipping")


total_pop = pd.read_csv('https://raw.githubusercontent.com/owid/covid-19-data/master/scripts/input/un/population_2020.csv')

# recalculate; the totals for continents are already in total_pop, but we put
# each contry in one continent, whereas the total_pop continent numbers probably
# take into account that some contries span multiple continents.
total_pop_continents = defaultdict(int)
for index, row in total_pop.iterrows():
    try:
        continent = continent_from_iso_country_code(row.iso_code)
        total_pop_continents[continent] += row.population
    except:
        continue

continent_percentages = {}
strings = {}
for continent, total in continent_totals.items():
    continent_percentages[continent] = total / total_pop_continents[continent] * 100
    short_continent = continent.replace('orth', '.').replace('outh', '.')
    tweet_string_add = tweet_bar_string_from_percentage(continent_percentages[continent], short_continent)
    strings[continent] = tweet_string_add
    tweet_string = tweet_string + "\n" + tweet_string_add


print("final string:")
print(tweet_string)
print("tweet length:", len(tweet_string))

# and update on twitter
api.update_status(tweet_string)
