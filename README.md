# Crime Trends Dashboard for a City Client

A dashboard that shows which crime types and areas in Los Angeles are rising or falling month to month, built from 1,000,197 reported incidents for city planners and public agency teams.

**[Open the live dashboard](https://pc-crime-trends-dashboard-for-a-city-client-2uen7v5wuq-uc.a.run.app)**

## The business problem

A city agency needs to know where to focus resources, and raw incident files are too large for a non-technical team to read. This project asks which crime types and areas in the City of Los Angeles are rising or falling, and where the largest changes happen from Jan 2020 to Nov 2024.

## Question

> Which crime types and neighborhoods in the City of Los Angeles are rising or falling month to month, and where do the largest changes happen?

## Key findings

- Citywide reported incidents fell 38.8% in the last 12 full months, from 232,829 to 142,422.
- 77th Street had the largest area change, down 6,319 incidents (-45.0%). Foothill fell 2,754 (-38.2%).
- TRESPASSING was the crime type that rose most, up 1,927 incidents (+46.7%). BATTERY - SIMPLE ASSAULT fell most, down 11,853 (-63.3%).
- Unusual spikes are rare. The pipeline flagged 48 months in total, with the largest in THEFT OF IDENTITY in Mar 2022 at 1,820 incidents against a usual 1,042.
- In Nov 2024, there were 7,179 incidents, which is -8.2% compared with the month before.

## How it was done

- SQL-style aggregation (counting rows by group): Each incident is one row, so counting by month, area and crime type turns the file into small tables that a dashboard can read quickly.
- Geographic analysis: Each area gets one map point, the median of its incident coordinates, plus a 12-month change. This shows where counts move without needing boundary files, which the data does not include.
- Anomaly detection with a trailing baseline: A month is flagged only when it is at least 3 standard deviations (a measure of how unusual a value is) above the prior 12-month average, and also has 20 or more incidents and is 20% or more above that average. This is simple to explain and ignores tiny counts.
- Simple methods on purpose: Seasonal forecasting models could handle seasons better, but they are harder to explain and add little value for this question.

Methods used: SQL-style aggregation, geographic analysis, anomaly detection.

## Data source and license

- **Dataset:** [Crime Data from 2020 to 2024 (City of Los Angeles)](https://data.lacity.org/Public-Safety/Crime-Data-from-2020-to-2024/2nrs-mtv8)
- **Publisher:** Los Angeles Police Department via City of Los Angeles open data portal (data.lacity.org)
- **License:** Creative Commons 1.0 Universal (Public Domain Dedication)
- The data is public and unmodified in `data/raw/` (too large for the repo - run `python download_data.py` to fetch it).
- This is an independent portfolio project. It is not endorsed by the data publisher.

## Limits of this analysis

- These are reported incidents, not all crime. Changes can come from reporting habits as well as real changes in crime.
- Counts are by the date the incident happened. Recent months may be incomplete if incidents are reported late.
- The data has no population figures, so counts are not rates per resident. Larger areas will have more incidents.
- The data only has area names, not finer neighborhood names, so 'neighborhood' here means the named area.
- 2,240 rows had a coordinate of 0. They are counted but have no place on the map.
- 0 repeated record numbers were removed. 4,697 rows from partly covered months were left out.
- Some crime type descriptions are cut off in the source file, so a few names look shortened.
- A spike flag needs 12 earlier months, so no flags exist before Jan 2021.
- The data shows what changed, not why. Causes need local knowledge.

## Data dictionary

What each column and code means, in plain English. Where the data source does not explain something, it says so instead of guessing.

| Column | What it means | Unit |
|---|---|---|
| Month | The first day of the month in which the incidents happened, taken from the occurrence date. It is the time axis for every trend. | date |
| Area name | The name of the area the incident is recorded under in the data file. It is used to compare places across the city. | - |
| Crime type | The text description of the crime type recorded for the incident. Some descriptions are cut off in the source file. | - |
| Incidents | The number of reported incidents counted in that row. It is the main measure used in every chart. | incidents |
| Latitude | The middle latitude of all incidents recorded in the area. It places the area on the map. | degrees |
| Longitude | The middle longitude of all incidents recorded in the area. It places the area on the map. | degrees |
| Total incidents | All incidents counted for the area across every month analyzed. It shows the overall size of the area's caseload. | incidents |
| Incidents in last 12 months | Incidents counted in the most recent 12 full months. It is the current period in the comparison. | incidents |
| Incidents in prior 12 months | Incidents counted in the 12 full months before the latest 12. It is the comparison period. | incidents |
| Change over 12 months | Incidents in the last 12 months minus incidents in the 12 months before. A positive number means a rise. | incidents |
| Percent change over 12 months | The 12-month change as a percent of the earlier 12 months. It is empty when the earlier period had no incidents. | percent |
| Series level | Says whether a row counts the whole city, one area or one crime type. It lets the dashboard filter the long table. | - |
| Series name | The name of the city, area or crime type that the row counts. It goes with the level column. | - |
| Incidents in previous month | The incident count of the same series in the month before. It is empty for the first month. | incidents |
| Change from previous month | Incidents this month minus incidents last month. A positive number means a rise. | incidents |
| Percent change from previous month | The month-to-month change as a percent of last month's count. It is empty when last month had no incidents. | percent |
| Usual level | The average monthly count over the 12 months before this one. It shows what is normal for that series. | incidents |
| Usual variation | How much the monthly count normally moves around the usual level, over the prior 12 months. A larger value means a noisier series. | incidents |
| Spike score | How many standard deviations this month sits above its usual level. Higher values mean a more unusual month. | standard deviations |
| Spike flag | Marks months that are far above the usual level by score, size and percent. Other months are marked as within the usual range. | - |

## What I would do next

- Check the 48 flagged months before acting on them. Each one needs a look for a real event, a change in how incidents are reported, or a batch data entry problem.
- Add population figures for each area. Without them, the counts show size as well as risk, so larger areas will look worse than they are.
- Use local knowledge to explain the causes. The data shows what changed and where, but not why. Also note that the source counts reported incidents, not all crime, and recent months may fill in later as reports arrive.

## Run it yourself

```bash
pip install -r requirements.txt
python download_data.py
python analysis.py        # cleans the data and builds data/processed/
streamlit run app.py      # opens the dashboard
```

## Project layout

```
analysis.py        cleaning + analysis, writes data/processed/
app.py             Streamlit dashboard (reads data/processed/ only)
credits.py         shows the data source and license on the dashboard
data/raw/          the public source data
data/processed/    small tables the dashboard uses
tests/             smoke test: the dashboard opens without errors
Dockerfile         how the dashboard is packaged for Google Cloud Run
```

## Redeploying

The dashboard runs on Google Cloud Run. To redeploy after a change, open the **Actions** tab, choose **Redeploy to Cloud Run**, and press **Run workflow**. It needs a repository secret named `GCP_SA_KEY` (a Google Cloud service account key that can deploy to Cloud Run).
