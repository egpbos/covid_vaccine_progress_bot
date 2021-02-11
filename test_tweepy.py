import io
from collections import defaultdict
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

bar = tqdm(initial=percentage, total=100., bar_format='|{bar:15}| {percentage:3.1f}%', ascii=False)

bar_string = bar.__str__()
print("bar_string:\n", bar_string)
bar.close()
tweet_string = bar_string[:-5].replace(' ', '\u3000') + bar_string[-5:]

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
    continent = continent_from_iso_country_code(iso_code)
    continent_totals[continent] += number


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

    bar = tqdm(initial=continent_percentages[continent],
               total=100., bar_format='|{bar:12}| C: {percentage:3.1f}%',
               ascii=False)
    bar_string = bar.__str__()
    bar.close()
    tweet_string_add = bar_string[:-8].replace(' ', '\u3000') + bar_string[-8:] 
    tweet_string_add = tweet_string_add.replace('C', continent)
    strings[continent] = tweet_string_add
    tweet_string = tweet_string + "\n" + tweet_string_add


print("final string:")
print(tweet_string)

# and update on twitter
api.update_status(tweet_string)
